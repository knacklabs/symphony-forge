import { Injectable } from '@nestjs/common';
import { PrismaService, type AccountPrincipal } from '@app/core-server';
import { type HistoryApi, type HistoryPrincipal } from '@app/history-contracts';
import { ChangeRecordResponseDto } from './history.dto';

@Injectable()
export class HistoryService implements HistoryApi {
  constructor(private readonly prisma: PrismaService) {}

  async record(principal: HistoryPrincipal, action: 'member.invited' | 'member.role_changed', summary: string): Promise<void> {
    await this.prisma.changeRecord.create({ data: {
      organisationId: principal.organisationId, actorAccountId: principal.id,
      actorEmail: principal.email, action, summary,
    } });
  }

  // A null limit is for the export, which includes every change.
  async list(principal: AccountPrincipal, limit: number | null = 100): Promise<ChangeRecordResponseDto[]> {
    const records = await this.prisma.changeRecord.findMany({
      where: { organisationId: principal.organisationId },
      orderBy: [{ createdAtUtc: 'desc' }, { id: 'desc' }], take: limit ?? undefined,
    });
    return records.map(ChangeRecordResponseDto.from);
  }
}
