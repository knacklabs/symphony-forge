import { Global, Module } from '@nestjs/common';
import { NOTIFICATIONS_API } from '@app/notifications-contracts';
import { NotificationsController } from './notifications.controller';
import { NotificationsService } from './notifications.service';

@Global()
@Module({
  controllers: [NotificationsController],
  providers: [NotificationsService, { provide: NOTIFICATIONS_API, useExisting: NotificationsService }],
  exports: [NOTIFICATIONS_API],
})
export class NotificationsModule {}
