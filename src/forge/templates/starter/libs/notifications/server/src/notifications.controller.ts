import { Controller, Get } from '@nestjs/common';
import { ApiCookieAuth, ApiOperation, ApiTags } from '@nestjs/swagger';
import { ApiEnvelope, ApiErrors, CurrentAccount, type AccountPrincipal } from '@app/core-server';
import { NotificationsResponseDto } from './notifications.dto';
import { NotificationsService } from './notifications.service';

@ApiTags('Notifications')
@ApiCookieAuth('session')
@Controller('notifications')
export class NotificationsController {
  constructor(private readonly notifications: NotificationsService) {}

  @Get()
  @ApiOperation({ summary: 'List the records that wait for you.',
    description: 'Returns your open entries in your organisation, newest first, with the full count.' })
  @ApiEnvelope(NotificationsResponseDto, 200)
  @ApiErrors(401)
  list(@CurrentAccount() account: AccountPrincipal): Promise<NotificationsResponseDto> {
    return this.notifications.list(account);
  }
}
