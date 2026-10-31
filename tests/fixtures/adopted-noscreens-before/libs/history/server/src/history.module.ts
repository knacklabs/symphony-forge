import { Global, Module } from '@nestjs/common';
import { HISTORY_API } from '@app/history-contracts';
import { HistoryController } from './history.controller';
import { HistoryService } from './history.service';

@Global()
@Module({
  controllers: [HistoryController],
  providers: [HistoryService, { provide: HISTORY_API, useExisting: HistoryService }],
  exports: [HISTORY_API],
})
export class HistoryModule {}
