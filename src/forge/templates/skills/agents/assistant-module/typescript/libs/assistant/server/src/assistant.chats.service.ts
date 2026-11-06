import { Injectable, NotFoundException } from '@nestjs/common';
import { PostgresSaver } from '@langchain/langgraph-checkpoint-postgres';
import { PrismaService, type AccountPrincipal } from '@app/core-server';

const RETENTION_MILLISECONDS = 30 * 24 * 60 * 60 * 1000;

@Injectable()
export class AssistantChatsService {
  constructor(private readonly prisma: PrismaService, private readonly checkpoints: PostgresSaver) {}

  create(account: AccountPrincipal, now = new Date()) {
    return this.prisma.assistantChat.create({ data: {
      organisationId: account.organisationId,
      createdByAccountId: account.id,
      modifiedByAccountId: account.id,
      lastMessageAtUtc: now,
    } });
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
