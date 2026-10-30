import { Injectable } from '@nestjs/common';
import type { Prisma } from '@prisma/client';
import { PrismaService, type AccountPrincipal } from '@app/core-server';
import { type HistoryApi, type HistoryPrincipal, type HistorySubject } from '@app/history-contracts';
import { ChangeRecordResponseDto } from './history.dto';

@Injectable()
export class HistoryService implements HistoryApi {
  constructor(private readonly prisma: PrismaService) {}

  async record(principal: HistoryPrincipal, action: string, summary: string, subject?: HistorySubject, tx?: unknown): Promise<void> {
    // The contract types the caller's transaction as unknown, so it names no Prisma type.
    const db = (tx as Prisma.TransactionClient | undefined) ?? this.prisma;
    await db.changeRecord.create({ data: {
      organisationId: principal.organisationId, actorAccountId: principal.id,
      actorEmail: principal.email, action, summary,
      subjectId: subject?.id, subjectName: subject?.name,
      viaAgent: principal.viaAgent ?? null,
    } });
  }

  // A null limit is for the export, which includes every change.
  async list(principal: AccountPrincipal, limit: number | null = 100): Promise<ChangeRecordResponseDto[]> {
    const records = await this.prisma.changeRecord.findMany({
      where: { organisationId: principal.organisationId },
      orderBy: [{ createdAtUtc: 'desc' }, { id: 'desc' }], take: limit ?? undefined,
    });
    // The organisation-wide list names the changed item, as in "Migration plan: Created the project".
    return records.map((record) => ({
      ...ChangeRecordResponseDto.from(record),
      summary: record.subjectName ? `${record.subjectName}: ${record.summary}` : record.summary,
    }));
  }

  async listForSubject(principal: HistoryPrincipal, subjectId: string, limit: number): Promise<ChangeRecordResponseDto[]> {
    const records = await this.prisma.changeRecord.findMany({
      where: { organisationId: principal.organisationId, subjectId },
      orderBy: [{ createdAtUtc: 'desc' }, { id: 'desc' }], take: limit,
    });
    return records.map(ChangeRecordResponseDto.from);
  }
}
