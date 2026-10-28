import { HttpException } from '@nestjs/common';
import type { Prisma } from '@prisma/client';
import { McpError, ErrorCode, type CallToolResult, type Tool } from '@modelcontextprotocol/sdk/types.js';
import { z } from 'zod';
import { formatNumber } from '@app/shared-util';
import type { AccountPrincipal } from './account-principal';
import { hasPermission, type FeaturePermissions } from './permissions';
import { defineFeatureResources } from './resources';

export type ToolContext = {
  account: AccountPrincipal;
  deleteAndRestore: readonly string[];
  createOnce: (feature: string, key: string, create: (afterCreate: (tx: Prisma.TransactionClient, id: string) => Promise<void>) => Promise<string>) => Promise<string>;
  reportError?: (error: unknown) => void;
};
type Annotations = Required<Pick<NonNullable<Tool['annotations']>, 'title' | 'readOnlyHint' | 'destructiveHint' | 'idempotentHint' | 'openWorldHint'>>;
type Shape = Record<string, z.ZodType>;
type Result = { data: Record<string, unknown>; summary: string };
type Definition = { description: Tool; permission: string; feature: string; switched: boolean; api?: string; label?: string; notFoundMessage?: string; invoke: (args: unknown, context: ToolContext) => Promise<Result> };
const TOOLS: Definition[] = [];
const CALL_LIMIT_MILLISECONDS = 10_000;
export type ToolErrorKind = 'invalid_input' | 'not_found' | 'not_allowed' | 'conflict' | 'rate_limited' | 'unavailable';

export class ToolError extends Error {
  constructor(readonly kind: ToolErrorKind, message: string, readonly retryable = false, readonly retryAfterSeconds?: number, readonly details?: unknown) {
    super(message);
  }
}

export function toolFailure(error: ToolError): CallToolResult {
  return {
    isError: true,
    content: [{ type: 'text', text: JSON.stringify({ error: { kind: error.kind, message: error.message, retryable: error.retryable,
      ...(error.retryAfterSeconds === undefined ? {} : { retry_after_seconds: error.retryAfterSeconds }),
      ...(error.details === undefined ? {} : { details: error.details }),
    } }) }],
  };
}

/** Registers a tool in the feature's one tools file. Duplicate names fail before serving calls. */
export function defineTool<S extends Shape>(config: {
  name: string; feature?: string; permission: string; description: string;
  input: z.ZodObject<S>; output: z.ZodObject<Shape>; annotations: Annotations;
  call: (principal: AccountPrincipal, input: z.infer<z.ZodObject<S>>, context: ToolContext) => Promise<Result>;
  switched?: boolean;
  notFoundMessage?: string;
  api?: string; label?: string;
}): Tool {
  if (TOOLS.some((tool) => tool.description.name === config.name)) throw new Error(`Duplicate tool: ${config.name}`);
  const inputSchema = config.input.strict();
  const outputSchema = config.output.strict();
  const description: Tool = {
    name: config.name, description: config.description, annotations: config.annotations,
    inputSchema: z.toJSONSchema(inputSchema, { io: 'input' }) as Tool['inputSchema'],
    outputSchema: z.toJSONSchema(outputSchema) as Tool['outputSchema'],
  };
  TOOLS.push({ description, permission: config.permission, feature: config.feature ?? config.permission.split('.')[0], switched: config.switched ?? false, api: config.api, label: config.label, notFoundMessage: config.notFoundMessage,
    invoke: async (args, context) => {
      const parsed = inputSchema.safeParse(args);
      if (!parsed.success) {
        const details = parsed.error.issues.map((issue) => ({ field: issue.path.join('.'), reason: issue.message }));
        const examples = Object.fromEntries(Object.entries(config.input.shape).flatMap(([name, schema]) => {
          const example = schema.meta()?.example;
          return example === undefined ? [] : [[name, example]];
        }));
        throw new ToolError('invalid_input', `The tool input has invalid fields. Use the field rules and try again. Example: ${JSON.stringify(examples)}.`, false, undefined, details);
      }
      const result = await config.call(context.account, parsed.data, context);
      return { ...result, data: outputSchema.parse(result.data) as Record<string, unknown> };
    },
  });
  return description;
}

export function listTools(context: ToolContext): Tool[] {
  return TOOLS.filter((tool) => hasPermission(context.account, tool.permission)
    && (!tool.switched || context.deleteAndRestore.includes(tool.feature))).map((tool) => tool.description);
}

/** One permission, validation, deadline and error boundary for default and hand-written tools. */
export async function callTool(name: string, args: unknown, context: ToolContext): Promise<CallToolResult> {
  const tool = TOOLS.find((entry) => entry.description.name === name);
  if (!tool) throw new McpError(ErrorCode.InvalidParams, 'Unknown tool. Use tools/list to find a tool.');
  if (!hasPermission(context.account, tool.permission)) return toolFailure(new ToolError('not_allowed',
    `Your agent account's role cannot use ${name}. An admin can change its role on the Members screen.`));
  if (tool.switched && !context.deleteAndRestore.includes(tool.feature)) return toolFailure(new ToolError('not_allowed',
    `An admin has not turned on delete and restore of ${tool.feature} for agents. Ask an admin to turn it on in Agent access on the ${tool.feature} list.`));
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    const result = await Promise.race([
      tool.invoke(args, context),
      new Promise<never>((_resolve, reject) => { timer = setTimeout(() => reject(new ToolError('unavailable',
        'The app could not finish this call in time. Wait 5 seconds and try again.', true, 5)), CALL_LIMIT_MILLISECONDS); }),
    ]);
    return { content: [{ type: 'text', text: result.summary }], structuredContent: result.data };
  } catch (error) {
    if (error instanceof ToolError) return toolFailure(error);
    if (error instanceof HttpException && error.getStatus() < 500) {
      const body = error.getResponse();
      const details = typeof body === 'object' && 'details' in body ? body.details : undefined;
      const kind = ({ 400: 'invalid_input', 403: 'not_allowed', 404: 'not_found', 409: 'conflict' } as const)[error.getStatus() as 400 | 403 | 404 | 409];
      const suppliedMessage = typeof body === 'object' && 'message' in body && typeof body.message === 'string' ? body.message : undefined;
      return toolFailure(new ToolError(kind ?? 'invalid_input', error.getStatus() === 404
        ? tool.notFoundMessage ?? `No item has this id in your organisation. Use ${snake(tool.feature)}_search to find it.`
        : error.getStatus() === 409 && suppliedMessage ? suppliedMessage
        : 'The app could not accept this change. Check the fields and try again.', false, undefined, details));
    }
    context.reportError?.(error);
    return toolFailure(new ToolError('unavailable', 'The app could not finish this call. Wait 5 seconds and try again.', true, 5));
  } finally {
    if (timer !== undefined) clearTimeout(timer);
  }
}

function snake(value: string): string {
  return value.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`).replace(/-/g, '_');
}
const RESPONSE_FORMAT = z.enum(['concise', 'detailed']).default('concise').meta({ description: 'Use detailed for every field and audit emails.', example: 'concise' });
type Row = { id: string; updatedAtUtc: string; deletedAtUtc: string | null };
type Page<R> = { items: R[]; paging: { total: number; totalCapped: boolean; nextCursor: string | null } };

/** Builds the six tools from a feature's own schemas and service, without another data path. */
export function defineFeatureTools<I extends Record<string, unknown>, R extends Row, Q>(config: {
  feature: string; one: string; permissions: FeaturePermissions; input: z.ZodObject<Shape>; query: z.ZodObject<Shape>;
  concise: readonly string[]; links: Record<string, string>; hide?: readonly string[];
  api: string; label: string;
  resolve?: (token: string) => { get(account: AccountPrincipal, id: string): Promise<object> };
  service: {
    list(account: AccountPrincipal, query: Q): Promise<Page<R>>;
    get(account: AccountPrincipal, id: string): Promise<R>;
    create(account: AccountPrincipal, input: I, options?: { afterCreate: (tx: Prisma.TransactionClient, id: string) => Promise<void> }): Promise<R>;
    update(account: AccountPrincipal, id: string, input: I): Promise<R>;
    delete(account: AccountPrincipal, id: string): Promise<void>;
    restore(account: AccountPrincipal, id: string): Promise<R>;
  };
}): void {
  const feature = snake(config.feature);
  const one = snake(config.one);
  const oneWords = config.one.replace(/-/g, ' ');
  const pluralWords = config.feature.replace(/-/g, ' ');
  const idField = `${one}_id`;
  const title = (text: string) => text.charAt(0).toUpperCase() + text.slice(1).replace(/-/g, ' ');
  const fields = Object.fromEntries(Object.entries(config.input.shape).map(([field, schema]) => [snake(field), schema]));
  const itemShape: Shape = { [idField]: z.string().uuid(), updated_at_utc: z.string() };
  for (const [field, schema] of Object.entries(config.input.shape)) {
    const document = z.toJSONSchema(schema);
    // Omitted optional inputs become null in service responses; booleans keep their false default.
    const nullable = schema.safeParse(undefined).success && document.type !== 'boolean';
    const responseSchema = nullable ? schema.nonoptional().nullable() : schema;
    itemShape[snake(field)] = config.concise.includes(field) ? responseSchema : responseSchema.optional();
    if (document.enum) {
      const labelSchema = nullable ? z.string().nullable() : z.string();
      itemShape[`${snake(field)}_label`] = config.concise.includes(field) ? labelSchema : labelSchema.optional();
    }
  }
  for (const field of Object.keys(config.links)) itemShape[snake(field).replace(/_id$/, '_name')] = z.string().nullable().optional();
  for (const field of ['created_at_utc', 'created_by_email', 'modified_by_email', 'deleted_at_utc', 'deleted_by_email']) itemShape[field] = z.string().nullable().optional();
  const itemOutput = z.object(itemShape).strict();
  defineFeatureResources({
    feature: config.feature, one: config.one, permission: config.permissions.view, input: config.input,
    read: async (id, context) => itemOutput.parse(await item(await config.service.get(context.account, id), true, context, new Map())),
  });
  const inputValue = (args: Record<string, unknown>): I => config.input.parse(Object.fromEntries(
    Object.keys(config.input.shape).map((field) => [field, args[snake(field)]]))) as I;
  async function item(row: R, detailed: boolean, context: ToolContext, names: Map<string, string | null>): Promise<Record<string, unknown>> {
    const source = row as R & Record<string, unknown>;
    const result: Record<string, unknown> = { [idField]: row.id, updated_at_utc: row.updatedAtUtc };
    for (const [field, schema] of Object.entries(config.input.shape)) {
      if (!detailed && !config.concise.includes(field) && !(field in config.links)) continue;
      result[snake(field)] = source[field];
      if (z.toJSONSchema(schema).enum) result[`${snake(field)}_label`] = typeof source[field] === 'string' ? title(source[field]) : null;
    }
    for (const [field, token] of Object.entries(config.links)) {
      const id = source[field];
      const key = `${token}:${String(id)}`;
      // ponytail: one public-service read per linked id; a batch name lookup is the upgrade.
      if (!names.has(key)) {
        if (id === null || id === undefined) names.set(key, null);
        else {
          if (!config.resolve) throw new Error('A linked tool needs the target public service.');
          try {
            const linked = await config.resolve(token).get(context.account, String(id));
            const label = TOOLS.find((tool) => tool.api === token)?.label;
            if (!label || !(label in linked) || typeof (linked as Record<string, unknown>)[label] !== 'string') {
              throw new Error('The linked feature needs its display field in its tools file.');
            }
            names.set(key, String((linked as Record<string, unknown>)[label]));
          } catch (error) {
            if (!(error instanceof HttpException) || ![403, 404].includes(error.getStatus())) throw error;
            // The parent remains readable. Keep the target id without exposing a restricted name.
            names.set(key, null);
          }
        }
      }
      result[snake(field).replace(/_id$/, '_name')] = names.get(key);
    }
    if (detailed) for (const field of ['createdAtUtc', 'createdByEmail', 'modifiedByEmail', 'deletedAtUtc', 'deletedByEmail']) result[snake(field)] = source[field];
    return result;
  }
  const filters = Object.fromEntries(Object.entries(config.query.shape).filter(([field]) => !['search', 'deleted', 'sortBy', 'sortOrder', 'limit', 'after', 'before'].includes(field)).map(([field, schema]) => [snake(field), schema]));
  const sortFields = (z.toJSONSchema(config.query.shape.sortBy).enum ?? []) as string[];
  const searchInput = z.object({ ...filters, query: config.query.shape.search,
    include_deleted: z.boolean().default(false).meta({ description: 'Include deleted items when your role can restore them.', example: false }),
    sort_by: z.enum(sortFields.map(snake)).default('updated_at_utc').meta({ description: 'The field used to sort results.', example: 'updated_at_utc' }),
    sort_order: z.enum(['asc', 'desc']).default('desc').meta({ description: 'The sort direction.', example: 'desc' }),
    limit: z.number().int().min(1).max(100).default(20).meta({ description: 'Results per page, from 1 to 100.', example: 20 }),
    cursor: config.query.shape.after, response_format: RESPONSE_FORMAT }).strict();
  const idInput = z.object({ [idField]: z.string().uuid().meta({ description: `The ${config.one} id returned by ${feature}_search.`, example: 'b3e1d349-1d8e-481c-8c69-99ea576f94c7' }), response_format: RESPONSE_FORMAT }).strict();
  for (const action of ['search', 'get', 'create', 'update', 'delete', 'restore'] as const) {
    if (config.hide?.includes(action)) continue;
    const name = `${feature}_${action}`;
    const input: z.ZodObject<Shape> = action === 'search' ? searchInput : action === 'create'
      ? z.object({ ...fields, idempotency_key: z.string().min(1).max(200).optional().meta({ description: 'Reuse this key to retry a create without a second item.', example: 'create-project-1' }), response_format: RESPONSE_FORMAT }).strict()
      : action === 'update' ? z.object({ ...fields, ...idInput.shape }).strict() : idInput;
    const output: z.ZodObject<Shape> = action === 'search'
      ? z.object({ items: z.array(itemOutput), total: z.number(), total_is_capped: z.boolean(), next_cursor: z.string().nullable() }).strict()
      : action === 'delete' ? z.object({ [idField]: z.string().uuid(), deleted: z.literal(true) }).strict() : itemOutput;
    const descriptions = {
      search: `Find ${pluralWords} in your organisation by text and filters, newest change first. Use it to find a ${idField} before ${feature}_get, ${feature}_update or ${feature}_delete. Returns 20 by default; pass next_cursor as cursor for more.`,
      get: `Read one ${oneWords} with its useful fields, or every field with response_format detailed. Use ${feature}_search first when you do not know the ${idField}.`,
      create: `Create a ${oneWords} in your organisation. Use an idempotency_key to retry safely, then ${feature}_get to read it.`,
      update: `Replace the editable fields of one ${oneWords}. Use ${feature}_get first to read its current fields. A repeated update makes no extra change.`,
      delete: `Soft delete one ${oneWords} and keep its history. Use ${feature}_search to find it and ${feature}_restore to bring it back.`,
      restore: `Restore a deleted ${oneWords}. Use ${feature}_search with include_deleted to find it. A repeated restore makes no extra change.`,
    };
    defineTool({ name, feature: config.feature, description: descriptions[action], permission: config.permissions[action === 'search' || action === 'get' ? 'view' : action === 'update' ? 'edit' : action],
      input, output, switched: action === 'delete' || action === 'restore', api: config.api, label: config.label,
      notFoundMessage: `No ${oneWords} has this ${idField} in your organisation. Use ${feature}_search to find it.`,
      annotations: { title: `${title(action)} ${action === 'search' ? config.feature.replace(/-/g, ' ') : config.one.replace(/-/g, ' ')}`,
        readOnlyHint: action === 'search' || action === 'get', destructiveHint: action === 'delete',
        idempotentHint: ['update', 'delete', 'restore'].includes(action), openWorldHint: false },
      call: async (_principal, args, context) => {
        const account = context.account;
        const detailed = args.response_format === 'detailed';
        const names = new Map<string, string | null>();
        if (action === 'search') {
          const filterValues = Object.fromEntries(Object.keys(config.query.shape).filter((field) => snake(field) in filters).map((field) => [field, args[snake(field)]]));
          const query = config.query.parse({ ...filterValues, search: args.query, deleted: args.include_deleted ? 'yes' : undefined,
            sortBy: sortFields.find((field) => snake(field) === args.sort_by), sortOrder: args.sort_order, limit: args.limit, after: args.cursor }) as Q;
          const page = await config.service.list(account, query);
          const items: Record<string, unknown>[] = [];
          for (const row of page.items) items.push(await item(row, detailed, context, names));
          const data = { items,
            total: page.paging.total, total_is_capped: page.paging.totalCapped, next_cursor: page.paging.nextCursor };
          return { data, summary: `Showing ${formatNumber(data.items.length)} of ${page.paging.totalCapped ? 'more than 10,000' : formatNumber(data.total)} matching ${pluralWords}.`
            + (data.next_cursor ? ` Pass next_cursor as cursor for more, or narrow with query${Object.keys(filters).length ? ` or ${Object.keys(filters).join(', ')}` : ''}.` : '') };
        }
        let row: R;
        const id = String(args[idField]);
        if (action === 'create') {
          const values = inputValue(args);
          row = args.idempotency_key ? await config.service.get(account, await context.createOnce(`${feature}_create`, String(args.idempotency_key),
            async (afterCreate) => (await config.service.create(account, values, { afterCreate })).id)) : await config.service.create(account, values);
        } else if (action === 'update') row = await config.service.update(account, id, inputValue(args));
        else {
          row = await config.service.get(account, id);
          if (action === 'delete' && row.deletedAtUtc === null) await config.service.delete(account, id);
          if (action === 'restore' && row.deletedAtUtc !== null) row = await config.service.restore(account, id);
        }
        const label = String((row as R & Record<string, unknown>)[config.label]);
        const prefix = { get: title(oneWords), create: `Created the ${oneWords}`, update: `Updated the ${oneWords}`, delete: `Deleted the ${oneWords}`, restore: `Restored the ${oneWords}` };
        return { data: action === 'delete' ? { [idField]: row.id, deleted: true } : await item(row, detailed, context, names), summary: `${prefix[action]} ${label}.` };
      },
    });
  }
}
