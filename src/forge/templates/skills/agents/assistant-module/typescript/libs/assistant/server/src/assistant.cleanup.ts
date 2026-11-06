import { Injectable, OnModuleDestroy, OnModuleInit } from '@nestjs/common';
import { JsonLogger } from '@app/core-server';
import { AssistantChatsService } from './assistant.chats.service';

const CLEANUP_INTERVAL_MILLISECONDS = 60 * 60 * 1000;

@Injectable()
export class AssistantCleanup implements OnModuleInit, OnModuleDestroy {
  private timer?: ReturnType<typeof setInterval>;
  private running?: Promise<void>;

  constructor(private readonly chats: AssistantChatsService, private readonly logger: JsonLogger) {}

  async onModuleInit(): Promise<void> {
    await this.deleteExpired(new Date());
    this.timer = setInterval(() => {
      if (this.running) return;
      this.running = this.deleteExpired(new Date())
        .then(() => undefined)
        .catch(() => this.logger.error('Assistant chat clean-up failed', 'AssistantCleanup'))
        .finally(() => { this.running = undefined; });
    }, CLEANUP_INTERVAL_MILLISECONDS);
    this.timer.unref();
  }

  deleteExpired(now: Date): Promise<number> {
    return this.chats.deleteExpired(now);
  }

  async onModuleDestroy(): Promise<void> {
    clearInterval(this.timer);
    await this.running;
  }
}
