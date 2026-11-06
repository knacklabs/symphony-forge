import { BadRequestException, Injectable, NotFoundException } from '@nestjs/common';
import type { Prisma } from '@prisma/client';
import { BaseMessage } from '@langchain/core/messages';
import { z } from 'zod';
import { confirmPropsSchema, type Chat, type ChatListQuery } from '@app/assistant-contracts';
import { PostgresSaver } from '@langchain/langgraph-checkpoint-postgres';
import { PrismaService, type AccountPrincipal } from '@app/core-server';

const RETENTION_MILLISECONDS = 30 * 24 * 60 * 60 * 1000;
const TOTAL_CAP = 10_000;
const cursorValueSchema = z.tuple([z.iso.datetime(), z.uuid()]);
const summary = (chat: { id: string; createdAtUtc: Date; lastMessageAtUtc: Date }) => ({
  id: chat.id, createdAtUtc: chat.createdAtUtc.toISOString(), lastMessageAtUtc: chat.lastMessageAtUtc.toISOString(),
});
const cursorFor = (chat: { id: string; lastMessageAtUtc: Date }) =>
  Buffer.from(JSON.stringify([chat.lastMessageAtUtc.toISOString(), chat.id])).toString('base64url');

@Injectable()
export class AssistantChatsService {
  constructor(private readonly prisma: PrismaService, private readonly checkpoints: PostgresSaver) {}

  create(account: AccountPrincipal, now = new Date(), options?: {
    afterCreate: (transaction: Prisma.TransactionClient, id: string) => Promise<void>;
  }) {
    return this.prisma.$transaction(async (transaction) => {
      const chat = await transaction.assistantChat.create({ data: {
        organisationId: account.organisationId,
        createdByAccountId: account.id,
        modifiedByAccountId: account.id,
        lastMessageAtUtc: now,
      } });
      await options?.afterCreate(transaction, chat.id);
      return chat;
    });
  }

  async list(account: AccountPrincipal, query: ChatListQuery) {
    const where: Prisma.AssistantChatWhereInput = {
      organisationId: account.organisationId, createdByAccountId: account.id,
    };
    const cursor = query.before ?? query.after;
    const backward = query.before !== undefined;
    let boundary: Prisma.AssistantChatWhereInput = {};
    if (cursor) {
      let values: z.infer<typeof cursorValueSchema>;
      try { values = cursorValueSchema.parse(JSON.parse(Buffer.from(cursor, 'base64url').toString('utf8'))); }
      catch { throw new BadRequestException({ code: 'VALIDATION_ERROR', message: 'The chat cursor is not valid. Load the list again.',
        details: { fieldErrors: [{ field: backward ? 'before' : 'after', reason: 'Load the list again to get a valid cursor.' }] },
      }); }
      const [date, id] = values;
      const lastMessageAtUtc = new Date(date);
      boundary = backward
        ? { OR: [{ lastMessageAtUtc: { gt: lastMessageAtUtc } }, { lastMessageAtUtc, id: { gt: id } }] }
        : { OR: [{ lastMessageAtUtc: { lt: lastMessageAtUtc } }, { lastMessageAtUtc, id: { lt: id } }] };
    }
    const order = backward ? 'asc' : 'desc';
    const [rows, total] = await Promise.all([
      this.prisma.assistantChat.findMany({ where: { AND: [where, boundary] },
        orderBy: [{ lastMessageAtUtc: order }, { id: order }], take: query.limit + 1 }),
      this.prisma.assistantChat.count({ where, take: TOTAL_CAP + 1 }),
    ]);
    const more = rows.length > query.limit;
    const items = rows.slice(0, query.limit);
    if (backward) items.reverse();
    const first = items.at(0);
    const last = items.at(-1);
    return { items: items.map(summary), paging: {
      limit: query.limit,
      nextCursor: last && (backward || more) ? cursorFor(last) : null,
      previousCursor: first && (backward ? more : !!cursor) ? cursorFor(first) : null,
      total: Math.min(total, TOTAL_CAP), totalCapped: total > TOTAL_CAP,
    } };
  }

  async get(account: AccountPrincipal, id: string): Promise<Chat> {
    const chat = await this.ownChat(account, id);
    const saved = await this.checkpoints.getTuple({ configurable: { thread_id: chat.id } });
    const messages: Chat['messages'] = [];
    const stored: unknown = saved?.checkpoint.channel_values.messages;
    if (Array.isArray(stored)) for (const message of stored) {
      if (!BaseMessage.isInstance(message)) continue;
      const type = message.getType();
      if (type !== 'human' && type !== 'ai') continue;
      const text = typeof message.content === 'string' ? message.content : message.content
        .filter((part) => part.type === 'text' && typeof part.text === 'string')
        .map((part) => part.text).join('');
      messages.push({ role: type === 'human' ? 'user' : 'assistant', text });
    }
    let confirm: Chat['confirm'] = null;
    for (const [, channel, value] of saved?.pendingWrites ?? []) {
      if (channel !== '__interrupt__') continue;
      const parsed = z.object({ id: z.string(), value: z.object(
        confirmPropsSchema.omit({ confirmId: true }).shape,
      ) }).parse(value);
      confirm = { ...parsed.value, confirmId: parsed.id };
    }
    return { ...summary(chat), messages, confirm };
  }

  async ownChat(account: AccountPrincipal, id: string) {
    const chat = await this.prisma.assistantChat.findFirst({ where: {
      id, organisationId: account.organisationId, createdByAccountId: account.id,
    } });
    if (!chat) throw new NotFoundException({
      code: 'NOT_FOUND', message: 'This chat is not available. Start a new chat.',
    });
    return chat;
  }

  async touch(account: AccountPrincipal, id: string, now = new Date()): Promise<void> {
    const result = await this.prisma.assistantChat.updateMany({ where: {
      id, organisationId: account.organisationId, createdByAccountId: account.id,
    }, data: { lastMessageAtUtc: now, modifiedByAccountId: account.id } });
    if (!result.count) throw new NotFoundException({
      code: 'NOT_FOUND', message: 'This chat is not available. Start a new chat.',
    });
  }

  async deleteExpired(now: Date): Promise<number> {
    const lastMessageAtUtc = { lte: new Date(now.getTime() - RETENTION_MILLISECONDS) };
    const expired = await this.prisma.assistantChat.findMany({
      where: { lastMessageAtUtc }, select: { id: true },
    });
    let deleted = 0;
    for (const chat of expired) {
      deleted += await this.prisma.$transaction(async (transaction) => {
        // The conditional delete locks the row and rechecks a message that arrived
        // after the scan. Keep the owner row if checkpoint deletion fails.
        const result = await transaction.assistantChat.deleteMany({
          where: { id: chat.id, lastMessageAtUtc },
        });
        if (result.count) await this.checkpoints.deleteThread(chat.id);
        return result.count;
      });
    }
    return deleted;
  }
}
