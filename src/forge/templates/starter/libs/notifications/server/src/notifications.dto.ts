import { ApiProperty } from '@nestjs/swagger';
import type { Notification } from '@prisma/client';
import type { NotificationEntry, NotificationsList } from '@app/notifications-contracts';

export class NotificationResponseDto implements NotificationEntry {
  @ApiProperty({ description: 'The waiting entry identifier.', example: '019a3500-0000-7000-8000-000000000001' })
  id!: string;
  @ApiProperty({ description: 'The record that needs an action.', example: '019a3500-0000-7000-8000-000000000002' })
  subjectId!: string;
  @ApiProperty({ description: 'The record name.', example: 'October budget' })
  subjectName!: string;
  @ApiProperty({ description: 'The action that waits for you.', example: 'Approve the budget.' })
  message!: string;
  @ApiProperty({ description: 'When the entry was created, in UTC.', example: '2026-10-31T10:00:00.000Z' })
  createdAtUtc!: string;

  static from(record: Notification): NotificationResponseDto {
    return { id: record.id, subjectId: record.subjectId, subjectName: record.subjectName,
      message: record.message, createdAtUtc: record.createdAtUtc.toISOString() };
  }
}

export class NotificationsResponseDto implements NotificationsList {
  @ApiProperty({ description: 'The number of all records that wait for you.', example: 2 })
  count!: number;
  @ApiProperty({ description: 'Up to 100 open entries, newest first.', type: [NotificationResponseDto] })
  items!: NotificationResponseDto[];
}
