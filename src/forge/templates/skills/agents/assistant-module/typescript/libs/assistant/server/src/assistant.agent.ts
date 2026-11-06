import { Injectable } from '@nestjs/common';
import { isAIMessage, ToolMessage } from '@langchain/core/messages';
import { DynamicStructuredTool, type ToolRunnableConfig } from '@langchain/core/tools';
import { createReactAgent } from '@langchain/langgraph/prebuilt';
import { interrupt, MessagesAnnotation } from '@langchain/langgraph';
import { PostgresSaver } from '@langchain/langgraph-checkpoint-postgres';
import { z } from 'zod';
import { callTool, listTools, permissionsFor, RetryKeys, type AccountPrincipal, type ToolContext } from '@app/core-server';
import { AssistantModel } from './assistant.model';
import { ASSISTANT_PROMPT } from './assistant.prompt';

const CONFIRM_MILLISECONDS = 15 * 60 * 1000;
const DEFERRED_ACTION = 'This action has not run. Request it separately after the first action finishes.';
const failedArtifactSchema = z.object({ result: z.object({ isError: z.boolean().optional() }).optional() });
const decisionSchema = z.object({
  confirmId: z.string(), decision: z.enum(['confirm', 'cancel']), expiresAt: z.iso.datetime(),
});

@Injectable()
export class AssistantAgent {
  constructor(private readonly model: AssistantModel, private readonly checkpoints: PostgresSaver,
    private readonly retryKeys: RetryKeys) {}

  create(account: AccountPrincipal, chatId: string, called: string[]) {
    const principal = { ...account, viaAgent: 'the assistant' };
    const context: ToolContext = {
      account: principal,
      // A person's own role still checks each action. Agent-key switches apply
      // to team agents, not to the person confirming an action in their chat.
      deleteAndRestore: permissionsFor(account.role).map((permission) => permission.split('.')[0]),
      createOnce: (feature, key, create) => this.retryKeys.once(principal, feature, key, create),
    };
    const available = listTools(context);
    const descriptions = available.slice(0, 15);
    const tools = descriptions.map((description) => new DynamicStructuredTool({
      name: description.name, description: description.description ?? description.name,
      schema: description.inputSchema,
      responseFormat: 'content_and_artifact',
      func: async (input, _manager, config) => {
        const callId = (config as ToolRunnableConfig | undefined)?.toolCall?.id;
        if (!callId) throw new Error('The assistant tool call needs an identifier.');
        let decision: z.infer<typeof decisionSchema> | undefined;
        if (!description.annotations?.readOnlyHint) {
          // interrupt throws to pause the prebuilt agent. It must stay outside
          // any error handler; the node runs again from here on resume.
          decision = decisionSchema.parse(interrupt({
            title: description.annotations?.title ?? 'Confirm this change',
            lines: Object.entries(z.record(z.string(), z.unknown()).parse(input))
              .filter(([field]) => !['response_format', 'idempotency_key'].includes(field))
              .map(([field, value]) => `${field.replace(/_/g, ' ')}: ${typeof value === 'object' ? JSON.stringify(value) : String(value)}`),
            expiresAt: new Date(Date.now() + CONFIRM_MILLISECONDS).toISOString(),
          }));
          if (decision.decision === 'cancel' || Date.parse(decision.expiresAt) <= Date.now()) {
            return ['The person cancelled this change. Do not run it again without a new request.',
              { confirmId: decision.confirmId }];
          }
        }
        const key = `${chatId}:${callId}`;
        const args = z.record(z.string(), z.unknown()).parse(input);
        if ('idempotency_key' in (description.inputSchema.properties ?? {})) args.idempotency_key = key;
        const toolContext: ToolContext = { ...context,
          createOnce: (feature, _key, create) => this.retryKeys.once(principal, feature, key, create),
        };
        called.push(description.name);
        const result = await callTool(description.name, args, toolContext);
        const summary = result.content.filter((part) => part.type === 'text').map((part) => part.text).join('\n');
        return [JSON.stringify({ summary, data: result.structuredContent, isError: result.isError ?? false }),
          { result, ...(decision ? { confirmId: decision.confirmId } : {}) }];
      },
    }));
    return createReactAgent({
      llm: this.model.client.bindTools(tools, { parallel_tool_calls: false }),
      tools, checkpointer: this.checkpoints, prompt: ASSISTANT_PROMPT,
      preModelHook: (state: typeof MessagesAnnotation.State) => {
        // ToolNode catches tool exceptions. Stop in a separate graph node,
        // before another model call, using the failures saved in this turn.
        const failures = new Map<string, number>();
        for (let index = state.messages.length - 1; index >= 0; index -= 1) {
          const message = state.messages[index];
          if (message.getType() === 'human') break;
          if (!(message instanceof ToolMessage) || !message.name || message.content === DEFERRED_ACTION) continue;
          const artifact = failedArtifactSchema.safeParse(message.artifact);
          if (message.status !== 'error' && !(artifact.success && artifact.data.result?.isError)) continue;
          const count = (failures.get(message.name) ?? 0) + 1;
          if (count >= 2) throw new Error('The assistant could not complete this action.');
          failures.set(message.name, count);
        }
        return {};
      },
      postModelHook: async (state: typeof MessagesAnnotation.State) => {
        const last = state.messages.at(-1);
        if (!last || !isAIMessage(last)) return {};
        const messages: ToolMessage[] = [];
        let pending = false;
        for (const call of last.tool_calls ?? []) {
          if (!call.id) throw new Error('The assistant tool call needs an identifier.');
          if (!descriptions.some((item) => item.name === call.name)) {
            // Even a hallucinated call reaches the app's permission boundary.
            // A role refusal stays the same as it is through MCP.
            let content: string;
            try {
              if (available.some((item) => item.name === call.name)) {
                content = 'This tool is not available in this chat. Use one of the supplied tools.';
              } else {
                const result = await callTool(call.name, call.args, context);
                content = result.content.filter((part) => part.type === 'text').map((part) => part.text).join('\n');
              }
            } catch { content = 'This tool is not available. Use one of the supplied tools.'; }
            messages.push(new ToolMessage({ content, name: call.name, tool_call_id: call.id, status: 'error' }));
          } else if (pending) {
            messages.push(new ToolMessage({ content: DEFERRED_ACTION,
              name: call.name, tool_call_id: call.id, status: 'error' }));
          } else pending = true;
        }
        return { messages };
      },
    });
  }
}
