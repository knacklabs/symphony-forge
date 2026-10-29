import { Body, Controller, Headers, Post } from '@nestjs/common';
import { ApiCookieAuth, ApiHeader, ApiOperation, ApiTags } from '@nestjs/swagger';
import { AdminOnly, ApiEnvelope, ApiErrors, ApiZodBody, CurrentAccount, RetryKeys, retryKeySchema, ZodValidationPipe, type AccountPrincipal } from '@app/core-server';
import { inviteSchema, type InviteInput } from '@app/auth-contracts';
import { AuthService } from './auth.service';
import { MessageResponseDto } from './auth.dto';

@ApiTags('Organisations')
@ApiCookieAuth('session')
@Controller('invites')
export class InvitesController {
  constructor(private readonly auth: AuthService, private readonly retryKeys: RetryKeys) {}

  @Post()
  @AdminOnly()
  @ApiZodBody(inviteSchema)
  @ApiOperation({ summary: 'Invite a person to your organisation.', description: 'Admins can invite an email without an account. A new invite replaces the previous link and works for seven days. Production requires a mail provider.' })
  @ApiEnvelope(MessageResponseDto, 201)
  @ApiErrors(400, 401, 403, 409, 422)
  @ApiHeader({ name: 'Idempotency-Key', required: false, description: 'Send the same key to retry this invite. A repeat sends no second email and makes no second invitation.' })
  async invite(
    @CurrentAccount() account: AccountPrincipal,
    @Body(new ZodValidationPipe(inviteSchema)) input: InviteInput,
    @Headers('idempotency-key') idempotencyKey?: string,
  ): Promise<MessageResponseDto> {
    const key = new ZodValidationPipe(retryKeySchema.optional(), 'Idempotency-Key').transform(idempotencyKey);
    if (key) {
      await this.retryKeys.once(account, 'members_invite', key,
        (afterCreate) => this.auth.invite(input.email, account, { afterCreate }));
    } else {
      await this.auth.invite(input.email, account);
    }
    return { message: 'Invite sent.' };
  }
}
