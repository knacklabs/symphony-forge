import { ApiProperty } from '@nestjs/swagger';
import type { ChangeRecord } from '@prisma/client';
import type { HistoryEntry } from '@app/shared';

export class ChangeRecordResponseDto implements HistoryEntry {
  @ApiProperty({ description: 'The change identifier.', example: 'b3e1d349-1d8e-481c-8c69-99ea576f94c7' })
  id!: string;
  @ApiProperty({ description: 'The email of the admin who made the change.', example: 'ada@example.com' })
  actorEmail!: string;
  @ApiProperty({ description: 'What changed.', example: 'Invited grace@example.com' })
  summary!: string;
  @ApiProperty({ description: 'When the change happened, in UTC.', example: '2026-10-24T11:30:00.000Z' })
  createdAtUtc!: string;

  static from(record: ChangeRecord): ChangeRecordResponseDto {
    return { id: record.id, actorEmail: record.actorEmail, summary: record.summary, createdAtUtc: record.createdAtUtc.toISOString() };
  }
}
