import { Injectable } from '@nestjs/common';
import type { Prisma } from '@prisma/client';
import { PrismaService } from '@app/core-server';
import type { NotificationsApi, NotificationsPrincipal, NotificationsList } from '@app/notifications-contracts';
import { NotificationResponseDto } from './notifications.dto';

@Injectable()
export class NotificationsService implements NotificationsApi {
  constructor(private readonly prisma: PrismaService) {}

  async notify(principal: NotificationsPrincipal, recipientAccountId: string, subjectId: string,
    subjectName: string, message: string, tx?: unknown): Promise<void> {
    // Keep Prisma out of the public contract, as the history module does.
    const db = (tx as Prisma.TransactionClient | undefined) ?? this.prisma;
    await db.notification.create({ data: {
      organisationId: principal.organisationId, recipientAccountId, subjectId, subjectName, message,
    } });
  }

  async resolve(principal: NotificationsPrincipal, subjectId: string, tx?: unknown): Promise<void> {
    const db = (tx as Prisma.TransactionClient | undefined) ?? this.prisma;
    await db.notification.updateMany({
      where: { organisationId: principal.organisationId, subjectId, resolvedAtUtc: null },
      data: { resolvedAtUtc: new Date() },
    });
  }

  async list(principal: NotificationsPrincipal): Promise<NotificationsList> {
    const where = { organisationId: principal.organisationId, recipientAccountId: principal.id, resolvedAtUtc: null };
    const [count, records] = await this.prisma.$transaction([
      this.prisma.notification.count({ where }),
      this.prisma.notification.findMany({ where, orderBy: [{ createdAtUtc: 'desc' }, { id: 'desc' }], take: 100 }),
    ]);
    return { count, items: records.map(NotificationResponseDto.from) };
  }
}
