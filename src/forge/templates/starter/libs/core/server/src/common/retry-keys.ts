import { Injectable } from '@nestjs/common';
import { Prisma } from '@prisma/client';
import { z } from 'zod';
import type { AccountPrincipal } from './account-principal';
import { PrismaService } from '../prisma/prisma.service';

export const retryKeySchema = z.string().min(1).max(200);

type Create = (afterCreate: (tx: Prisma.TransactionClient, id: string) => Promise<void>) => Promise<string>;

@Injectable()
export class RetryKeys {
  constructor(private readonly prisma: PrismaService) {}

  async once(account: AccountPrincipal, action: string, key: string, create: Create): Promise<string> {
    const where = { accountId_tool_key: { accountId: account.id, tool: action, key } };
    const existing = await this.prisma.idempotencyKey.findUnique({ where });
    if (existing) return existing.itemId;

    try {
      return await create((tx, itemId) => tx.idempotencyKey.create({
        data: { accountId: account.id, organisationId: account.organisationId, tool: action, key, itemId },
      }).then(() => undefined));
    } catch (error) {
      if (!(error instanceof Prisma.PrismaClientKnownRequestError) || error.code !== 'P2002') throw error;
      const winner = await this.prisma.idempotencyKey.findUnique({ where });
      if (!winner) throw error;
      return winner.itemId;
    }
  }
}
