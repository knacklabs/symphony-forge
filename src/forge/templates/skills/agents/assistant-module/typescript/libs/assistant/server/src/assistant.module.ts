import { Module } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PostgresSaver } from '@langchain/langgraph-checkpoint-postgres';
import { AssistantChatsController } from './assistant.chats.controller';
import { AssistantChatsService } from './assistant.chats.service';
import { AssistantCleanup } from './assistant.cleanup';
import { AssistantAgent } from './assistant.agent';
import { AssistantModel } from './assistant.model';
import { AssistantUsage } from './assistant.usage';
import { AssistantTurn } from './assistant.turn';
import { AssistantTurnRepository } from './assistant-turn.repository';
import { AssistantTurnController } from './assistant.turn.controller';

@Module({
  controllers: [AssistantChatsController, AssistantTurnController],
  providers: [AssistantChatsService, AssistantCleanup, AssistantAgent, AssistantModel,
    AssistantUsage, AssistantTurn, AssistantTurnRepository, {
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
