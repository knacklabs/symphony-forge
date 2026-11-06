import { Module } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PostgresSaver } from '@langchain/langgraph-checkpoint-postgres';
import { AssistantChatsController } from './assistant.chats.controller';
import { AssistantChatsService } from './assistant.chats.service';
import { AssistantCleanup } from './assistant.cleanup';

@Module({
  controllers: [AssistantChatsController],
  providers: [AssistantChatsService, AssistantCleanup, {
    provide: PostgresSaver,
    inject: [ConfigService],
    useFactory: (config: ConfigService) => {
      const saver = PostgresSaver.fromConnString(config.getOrThrow<string>('DATABASE_URL'), { schema: 'assistant' });
      return Object.assign(saver, { onModuleDestroy: () => saver.end() });
    },
  }],
  exports: [AssistantChatsService, AssistantCleanup, PostgresSaver],
})
export class AssistantModule {}
