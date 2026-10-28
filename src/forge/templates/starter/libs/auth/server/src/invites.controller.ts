import { Body, Controller, Post } from '@nestjs/common';
import { ApiCookieAuth, ApiOperation, ApiTags } from '@nestjs/swagger';
import { AdminOnly, ApiEnvelope, ApiErrors, ApiZodBody, CurrentAccount, ZodValidationPipe, type AccountPrincipal } from '@app/core-server';
import { inviteSchema, type InviteInput } from '@app/auth-contracts';
import { AuthService } from './auth.service';
import { MessageResponseDto } from './auth.dto';

@ApiTags('Organisations')
@ApiCookieAuth('session')
@Controller('invites')
export class InvitesController {
  constructor(private readonly auth: AuthService) {}

  @Post()
  @AdminOnly()
  @ApiZodBody(inviteSchema)
  @ApiOperation({ summary: 'Invite a person to your organisation.', description: 'Admins can invite an email without an account. A new invite replaces the previous link and works for seven days. Production requires a mail provider.' })
  @ApiEnvelope(MessageResponseDto, 201)
  @ApiErrors(400, 401, 403, 409, 422)
  invite(@CurrentAccount() account: AccountPrincipal, @Body(new ZodValidationPipe(inviteSchema)) input: InviteInput): Promise<MessageResponseDto> {
    return this.auth.invite(input.email, account);
  }
}
