import { createHash } from 'node:crypto';
import { BadRequestException, ConflictException, Injectable } from '@nestjs/common';
import { BaseMessage, HumanMessage, isAIMessage, ToolMessage } from '@langchain/core/messages';
import { Command } from '@langchain/langgraph';
import { z } from 'zod';
import { confirmPropsSchema, streamEventSchema, type ConfirmDecision, type StreamEvent } from '@app/assistant-contracts';
import { JsonLogger, type AccountPrincipal } from '@app/core-server';
import { AssistantAgent } from './assistant.agent';
import { AssistantChatsService } from './assistant.chats.service';
import { containsSecret } from './assistant.guard';
import { displayResult } from './assistant.display';
import { ASSISTANT_PROMPT, PROMPT_VERSION } from './assistant.prompt';
import { AssistantTurnRepository } from './assistant-turn.repository';
import { AssistantUsage } from './assistant.usage';

type Emit = (event: StreamEvent) => void;
const MAX_CONTEXT_CHARACTERS = 48_000;
const artifactSchema = z.object({
  confirmId: z.string().optional(),
  result: z.object({
    isError: z.boolean().optional(), structuredContent: z.record(z.string(), z.unknown()).optional(),
    content: z.array(z.object({ type: z.string(), text: z.string().optional() })),
  }).optional(),
});
const hash = (value: string) => createHash('sha256').update(value).digest('hex');

function messagesFrom(value: unknown): BaseMessage[] {
  return Array.isArray(value) ? value.filter((message): message is BaseMessage => BaseMessage.isInstance(message)) : [];
}

function confirmReceipt(message: BaseMessage): string | undefined {
  if (!(message instanceof ToolMessage)) return undefined;
  const artifact = artifactSchema.safeParse(message.artifact);
  return artifact.success ? artifact.data.confirmId : undefined;
}

function refusal(text: string): string {
  try { return z.object({ error: z.object({ message: z.string() }) }).parse(JSON.parse(text)).error.message; }
  catch { return text; }
}

function toolEvents(message: ToolMessage, emit: Emit): void {
  const parsed = artifactSchema.safeParse(message.artifact);
  const result = parsed.success ? parsed.data.result : undefined;
  if (!result) {
    if (typeof message.content === 'string') emit({ event: 'text', data: {
      delta: message.status === 'error' ? refusal(message.content) : message.content,
    } });
    return;
  }
  const blocks = !result.isError && result.structuredContent
    ? displayResult(message.name ?? '', result.structuredContent) : [];
  for (const block of blocks) emit({ event: 'block', data: block });
  if (!blocks.length) for (const part of result.content) {
    if (part.type === 'text' && part.text) emit({ event: 'text', data: { delta: result.isError ? refusal(part.text) : part.text } });
  }
}

@Injectable()
export class AssistantTurn {
  constructor(private readonly agents: AssistantAgent, private readonly chats: AssistantChatsService,
    private readonly turns: AssistantTurnRepository, private readonly usage: AssistantUsage,
    private readonly logger: JsonLogger) {}

  async message(account: AccountPrincipal, id: string, text: string, key: string, emit: Emit): Promise<void> {
    await this.chats.ownChat(account, id);
    if (containsSecret(text)) throw new BadRequestException({ code: 'VALIDATION_ERROR',
      message: 'Do not send passwords, codes or card numbers here. Use the app’s secure form.' });
    await this.run(account, id, { text, requestId: `request:${hash(key)}` }, emit);
  }

  async confirm(account: AccountPrincipal, id: string, input: ConfirmDecision, emit: Emit): Promise<void> {
    await this.chats.ownChat(account, id);
    await this.run(account, id, input, emit);
  }

  private async run(account: AccountPrincipal, id: string,
    input: { text: string; requestId: string } | ConfirmDecision, emit: Emit): Promise<void> {
    const started = performance.now();
    await this.turns.locked(id, async () => {
      const called: string[] = [];
      const trace = (firstReplyMs: number | null) => this.logger.log('Assistant turn', 'AssistantTurn', {
        promptVersion: PROMPT_VERSION, promptHash: hash(ASSISTANT_PROMPT), accountHash: hash(account.id),
        tools: called, durationMs: Math.round(performance.now() - started), firstReplyMs,
      });
      const graph = this.agents.create(account, id, called);
      const config = { configurable: { thread_id: id }, recursionLimit: 16,
        signal: AbortSignal.timeout(120_000) };
      const state = await graph.getState(config);
      const saved = messagesFrom(state.values.messages);
      const cardFrom = (tasks: typeof state.tasks) => {
        const open = tasks.flatMap((task) => task.interrupts ?? [])[0];
        return open ? confirmPropsSchema.parse({
          ...confirmPropsSchema.omit({ confirmId: true }).parse(open.value), confirmId: open.id,
        }) : null;
      };
      const card = cardFrom(state.tasks);
      const replay = 'text' in input
        ? saved.some((message) => message.id === input.requestId)
        : saved.some((message) => confirmReceipt(message) === input.confirmId);
      if (replay) {
        // A checkpointed message id and the tool's saved receipt survive an API
        // restart, so a lost response never starts a second model turn or write.
        let response = state;
        if (!('text' in input)) {
          const belongsToDecision = (messages: BaseMessage[]) => {
            const receipt = messages.findIndex((message) => confirmReceipt(message) === input.confirmId);
            return receipt >= 0 && !messages.slice(receipt + 1).some((message) =>
              message instanceof HumanMessage || confirmReceipt(message) !== undefined);
          };
          if (!belongsToDecision(saved)) {
            // A later decision or message must not leak into this response.
            // The newest checkpoint before it holds the original answer/card.
            let found = false;
            for await (const previous of graph.getStateHistory(config)) {
              if (!belongsToDecision(messagesFrom(previous.values.messages))) continue;
              response = previous;
              found = true;
              break;
            }
            if (!found) throw new Error('The saved assistant answer is not available.');
          }
        }
        const messages = messagesFrom(response.values.messages);
        const start = 'text' in input ? messages.findIndex((message) => message.id === input.requestId) + 1
          : messages.findIndex((message) => confirmReceipt(message) === input.confirmId);
        const next = messages.findIndex((message, index) => index >= start && message instanceof HumanMessage);
        for (const message of messages.slice(start, next < 0 ? undefined : next)) {
          if (message instanceof ToolMessage) toolEvents(message, emit);
          if (isAIMessage(message) && typeof message.content === 'string' && message.content) {
            emit({ event: 'text', data: { delta: message.content } });
          }
        }
        const responseCard = cardFrom(response.tasks);
        if (responseCard && next < 0) emit({ event: 'confirm', data: responseCard });
        emit({ event: 'done', data: {} });
        return;
      }
      if ('text' in input && card) throw new ConflictException({ code: 'CONFIRM_PENDING',
        message: 'Confirm or cancel the open change before you send another message.' });
      if (!('text' in input) && (!card || card.confirmId !== input.confirmId)) {
        throw new ConflictException({ code: 'CONFIRM_CHANGED', message: 'This is not the open change. Load the chat again.' });
      }
      if (!('text' in input) && card && Date.parse(card.expiresAt) <= Date.now()) {
        throw new ConflictException({ code: 'CONFIRM_EXPIRED', message: 'This change has expired. Start a new chat to ask again.' });
      }
      if (!await this.usage.canStart()) {
        emit({ event: 'limit', data: { message: 'The assistant has reached its spending limit. Try again next month.' } });
        trace(Math.round(performance.now() - started));
        emit({ event: 'done', data: {} });
        return;
      }
      if ('text' in input && JSON.stringify(saved).length + input.text.length > MAX_CONTEXT_CHARACTERS) {
        emit({ event: 'limit', data: { message: 'This chat is too long. Start a new chat to continue.' } });
        trace(Math.round(performance.now() - started));
        emit({ event: 'done', data: {} });
        return;
      }
      await this.chats.touch(account, id);
      let firstReplyMs: number | null = null;
      let inputTokens = 0;
      let outputTokens = 0;
      let modelCalls = 0;
      const send: Emit = (event) => {
        if (firstReplyMs === null && (event.event === 'block' || event.event === 'confirm'
          || (event.event === 'text' && event.data.delta))) firstReplyMs = Math.round(performance.now() - started);
        emit(streamEventSchema.parse(event));
      };
      // Open the response before the provider runs, including for slow calls.
      send({ event: 'text', data: { delta: '' } });
      try {
        const value = 'text' in input ? { messages: [new HumanMessage({ content: input.text, id: input.requestId })] }
          : new Command({ resume: { ...input, expiresAt: card?.expiresAt } });
        const stream = await graph.stream(value, { ...config, streamMode: ['messages', 'updates'] });
        for await (const [mode, chunk] of stream) {
          if (mode === 'messages') {
            const [message] = chunk;
            if (message.getType() === 'ai' && typeof message.content === 'string' && message.content) {
              send({ event: 'text', data: { delta: message.content } });
            }
          } else {
            for (const [node, update] of Object.entries(chunk)) {
              if (node === '__interrupt__') {
                const interruptions = z.array(z.object({ id: z.string(), value: confirmPropsSchema.omit({ confirmId: true }) })).parse(update);
                for (const item of interruptions) send({ event: 'confirm', data: { ...item.value, confirmId: item.id } });
                continue;
              }
              if (!update || typeof update !== 'object' || !('messages' in update)) continue;
              for (const message of messagesFrom(update.messages)) {
                if (message instanceof ToolMessage) toolEvents(message, send);
                if (isAIMessage(message) && node === 'agent') {
                  modelCalls += 1;
                  inputTokens += message.usage_metadata?.input_tokens ?? 0;
                  outputTokens += message.usage_metadata?.output_tokens ?? 0;
                }
              }
            }
          }
        }
      } finally {
        try { if (modelCalls) await this.usage.record(account.id, id, inputTokens, outputTokens); }
        finally { trace(firstReplyMs); }
      }
      send({ event: 'done', data: {} });
    });
  }
}
