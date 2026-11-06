import { z } from 'zod';

const valueSchema = z.union([z.string(), z.number(), z.null()]);
const columnSchema = z.object({ key: z.string(), label: z.string() }).strict();
export const tablePropsSchema = z.object({
  columns: z.array(columnSchema), rows: z.array(z.record(z.string(), valueSchema)),
  total: z.number().int().nonnegative().optional(),
}).strict();
export const chartPropsSchema = z.object({
  type: z.enum(['bar', 'line']), xKey: z.string(), series: z.array(columnSchema),
  rows: z.array(z.record(z.string(), z.union([z.string(), z.number()]))), unit: z.string().optional(),
}).strict();
export const statsPropsSchema = z.object({ tiles: z.array(z.object({
  label: z.string(), value: z.union([z.string(), z.number()]), unit: z.string().optional(),
}).strict()) }).strict();
export const detailPropsSchema = z.object({ title: z.string(), fields: z.array(z.object({
  label: z.string(), value: valueSchema,
}).strict()) }).strict();
export const confirmPropsSchema = z.object({
  confirmId: z.string(), title: z.string(), lines: z.array(z.string()), expiresAt: z.iso.datetime(),
}).strict();
export const blockSchema = z.discriminatedUnion('kind', [
  z.object({ kind: z.literal('table'), props: tablePropsSchema }).strict(),
  z.object({ kind: z.literal('chart'), props: chartPropsSchema }).strict(),
  z.object({ kind: z.literal('stats'), props: statsPropsSchema }).strict(),
  z.object({ kind: z.literal('detail'), props: detailPropsSchema }).strict(),
  z.object({ kind: z.literal('confirm'), props: confirmPropsSchema }).strict(),
]);
export const streamEventSchema = z.discriminatedUnion('event', [
  z.object({ event: z.literal('text'), data: z.object({ delta: z.string() }).strict() }).strict(),
  z.object({ event: z.literal('block'), data: blockSchema }).strict(),
  z.object({ event: z.literal('confirm'), data: confirmPropsSchema }).strict(),
  z.object({ event: z.literal('limit'), data: z.object({ message: z.string() }).strict() }).strict(),
  z.object({ event: z.literal('error'), data: z.object({ message: z.string() }).strict() }).strict(),
  z.object({ event: z.literal('done'), data: z.object({}).strict() }).strict(),
]);
export type Block = z.infer<typeof blockSchema>;
export type StreamEvent = z.infer<typeof streamEventSchema>;
export type ConfirmProps = z.infer<typeof confirmPropsSchema>;
export type TableProps = z.infer<typeof tablePropsSchema>;
export type ChartProps = z.infer<typeof chartPropsSchema>;
export type StatsProps = z.infer<typeof statsPropsSchema>;
export type DetailProps = z.infer<typeof detailPropsSchema>;

export const createChatSchema = z.object({}).strict();
const cursorSchema = z.string().max(2048).regex(/^[\w-]+$/);
export const chatListQuerySchema = z.object({
  limit: z.coerce.number().int().min(1).max(100).default(20)
    .meta({ description: 'The number of chats to return, up to 100.', example: 20 }),
  after: cursorSchema.optional().meta({ description: 'The next cursor of the previous list.', example: 'WyIyMDI2LTExLTA2VDAwOjAwOjAwLjAwMFoiLCJiM2UxZDM0OS0xZDhlLTQ4MWMtOGM2OS05OWVhNTc2Zjk0YzciXQ' }),
  before: cursorSchema.optional().meta({ description: 'The previous cursor of the next list.', example: 'WyIyMDI2LTExLTA2VDAwOjAwOjAwLjAwMFoiLCJiM2UxZDM0OS0xZDhlLTQ4MWMtOGM2OS05OWVhNTc2Zjk0YzciXQ' }),
}).strict().refine((query) => !(query.after && query.before), { path: ['before'], message: 'Use after or before, not both.' });
export type ChatListQuery = z.infer<typeof chatListQuerySchema>;
export const chatSummarySchema = z.object({
  id: z.uuid(), createdAtUtc: z.iso.datetime(), lastMessageAtUtc: z.iso.datetime(),
}).strict();
export const chatSchema = chatSummarySchema.extend({
  messages: z.array(z.object({ role: z.enum(['user', 'assistant']), text: z.string() }).strict()),
  confirm: confirmPropsSchema.nullable(),
}).strict();
export const chatListSchema = z.object({
  items: z.array(chatSummarySchema),
  paging: z.object({ limit: z.number(), nextCursor: z.string().nullable(), previousCursor: z.string().nullable(), total: z.number(), totalCapped: z.boolean() }).strict(),
}).strict();
export type Chat = z.infer<typeof chatSchema>;
export type ChatSummary = z.infer<typeof chatSummarySchema>;

export const assistantMessageSchema = z.object({
  text: z.string().min(1).max(4000).meta({ description: 'Your message, up to 4000 characters.', example: 'Show my projects.' }),
}).strict();
export const confirmDecisionSchema = z.object({
  confirmId: z.string().min(1).max(200).meta({ description: 'The open card identifier returned by the stream.', example: 'open-change' }),
  decision: z.enum(['confirm', 'cancel']).meta({ description: 'Confirm saves the change; cancel leaves it unchanged.', example: 'confirm' }),
}).strict();
export type ConfirmDecision = z.infer<typeof confirmDecisionSchema>;
