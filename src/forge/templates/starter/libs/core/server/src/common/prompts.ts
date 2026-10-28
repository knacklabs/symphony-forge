import { ErrorCode, McpError, type GetPromptResult, type Prompt } from '@modelcontextprotocol/sdk/types.js';
import { z } from 'zod';
import { hasPermission } from './permissions';
import type { ToolContext } from './tools';

type Definition = { description: Prompt; permission: string; render: (args: unknown) => string };
const PROMPTS: Definition[] = [];

/** Call definePrompt(...) in a feature's tools file only for a repeated task in the constitution. */
export function definePrompt<S extends Record<string, z.ZodType>>(config: {
  name: string; description: string; permission: string; arguments: z.ZodObject<S>;
  render: (args: z.infer<z.ZodObject<S>>) => string;
}): void {
  if (PROMPTS.some((entry) => entry.description.name === config.name)) throw new Error(`Duplicate prompt: ${config.name}`);
  const schema = config.arguments.strict();
  const document = z.toJSONSchema(schema, { io: 'input' });
  PROMPTS.push({
    permission: config.permission,
    description: { name: config.name, description: config.description,
      arguments: Object.entries(config.arguments.shape).map(([name, field]) => ({
        name, description: field.meta()?.description, required: document.required?.includes(name) ?? false,
      })),
    },
    render: (args) => {
      const parsed = schema.safeParse(args);
      if (!parsed.success) throw new McpError(ErrorCode.InvalidParams, 'The prompt inputs are invalid. Check its required inputs and try again.');
      return config.render(parsed.data);
    },
  });
}

export function listPrompts(context: ToolContext): Prompt[] {
  return PROMPTS.filter((entry) => hasPermission(context.account, entry.permission)).map((entry) => entry.description);
}

export function getPrompt(name: string, args: unknown, context: ToolContext): GetPromptResult {
  const prompt = PROMPTS.find((entry) => entry.description.name === name);
  if (!prompt) throw new McpError(ErrorCode.InvalidParams, 'Unknown prompt. Use prompts/list to find a prompt.');
  if (!hasPermission(context.account, prompt.permission)) throw new McpError(ErrorCode.InvalidParams,
    "Your agent account's role cannot use this prompt. An admin can change its role on the Members screen.");
  return { messages: [{ role: 'user', content: { type: 'text', text: prompt.render(args) } }] };
}
