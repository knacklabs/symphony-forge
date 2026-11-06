import { ConflictException, Injectable } from '@nestjs/common';
import { PrismaService } from '@app/core-server';

@Injectable()
export class AssistantTurnRepository {
  constructor(private readonly prisma: PrismaService) {}

  async locked<T>(chatId: string, run: () => Promise<T>): Promise<T> {
    // A transaction-scoped advisory lock works across API processes and is
    // released on every exit, including an interrupt or a broken connection.
    return this.prisma.$transaction(async (transaction) => {
      const [row] = await transaction.$queryRaw<{ locked: boolean }[]>`
        SELECT pg_try_advisory_xact_lock(hashtextextended(${chatId}, 0)) AS locked
      `;
      if (!row.locked) throw new ConflictException({ code: 'TURN_RUNNING',
        message: 'An answer is still running. Wait for it to finish.' });
      return run();
    }, { timeout: 150_000 });
  }
}
