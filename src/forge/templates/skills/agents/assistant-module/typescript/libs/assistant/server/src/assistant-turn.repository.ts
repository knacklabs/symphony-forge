import { ConflictException, Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Client } from 'pg';

@Injectable()
export class AssistantTurnRepository {
  constructor(private readonly config: ConfigService) {}

  async locked<T>(chatId: string, run: () => Promise<T>): Promise<T> {
    // Keep the lock off the application pool: the running turn needs that pool
    // for permissions, tools and billing. Ending this session releases its lock.
    const client = new Client({ connectionString: this.config.getOrThrow<string>('DATABASE_URL'),
      connectionTimeoutMillis: 5_000 });
    try {
      await client.connect();
      const result = await client.query<{ locked: boolean }>(
        'SELECT pg_try_advisory_lock(hashtextextended($1, 0)) AS locked', [chatId],
      );
      if (!result.rows[0].locked) throw new ConflictException({ code: 'TURN_RUNNING',
        message: 'An answer is still running. Wait for it to finish.' });
      return await run();
    } finally { await client.end(); }
  }
}
