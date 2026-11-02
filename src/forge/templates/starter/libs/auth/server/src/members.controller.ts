import { Controller, Delete, Headers, HttpCode, Param, ParseUUIDPipe, Post } from '@nestjs/common';
import { ApiCookieAuth, ApiHeader, ApiOperation, ApiParam, ApiResponse, ApiTags } from '@nestjs/swagger';
import { AdminOnly, ApiEnvelope, ApiErrors, CurrentAccount, RetryKeys, retryKeySchema, ZodValidationPipe, type AccountPrincipal } from '@app/core-server';
import { AuthService } from './auth.service';
import { ResetLinkResponseDto } from './auth.dto';

@ApiTags('Organisations')
@ApiCookieAuth('session')
@Controller('members')
export class MembersController {
  constructor(private readonly auth: AuthService, private readonly retryKeys: RetryKeys) {}

  @Post(':accountId/reset-link')
  @AdminOnly()
  @ApiParam({ name: 'accountId', type: String, format: 'uuid', description: 'A human member of your organisation.', example: 'b3e1d349-1d8e-481c-8c69-99ea576f94c7' })
  @ApiOperation({ summary: 'Make a password reset link for a member.', description: 'Admins receive a single-use link valid for one hour, with or without email. A new link replaces earlier links. A retry with the same key shows no link.' })
  @ApiEnvelope(ResetLinkResponseDto, 201)
  @ApiErrors(400, 401, 403, 404)
  @ApiHeader({ name: 'Idempotency-Key', required: false, description: 'Reuse this key to avoid making a second link.' })
  async resetLink(
    @CurrentAccount() admin: AccountPrincipal,
    @Param('accountId', ParseUUIDPipe) accountId: string,
    @Headers('idempotency-key') idempotencyKey?: string,
  ): Promise<ResetLinkResponseDto> {
    const key = new ZodValidationPipe(retryKeySchema.optional(), 'Idempotency-Key').transform(idempotencyKey);
    let resetUrl: string | undefined;
    const onLink = (url: string) => { resetUrl = url; };
    if (key) {
      await this.retryKeys.once(admin, 'members_reset-link', key,
        (afterCreate) => this.auth.memberResetLink(admin, accountId, { afterCreate, onLink }));
    } else {
      await this.auth.memberResetLink(admin, accountId, { onLink });
    }
    return resetUrl ? { resetUrl } : {};
  }

  @Delete(':accountId')
  @AdminOnly()
  @HttpCode(200)
  @ApiParam({ name: 'accountId', type: String, format: 'uuid', example: 'b3e1d349-1d8e-481c-8c69-99ea576f94c7', description: 'The account of another member in your organisation.' })
  @ApiOperation({ summary: 'Remove a member from your organisation.', description: 'Only admins can remove members. You cannot remove yourself. Removal ends sessions, cancels the member’s invites and records the change.' })
  @ApiResponse({ status: 200, schema: { example: { success: true, data: null, error: null } } })
  @ApiErrors(400, 401, 403, 404)
  remove(@CurrentAccount() account: AccountPrincipal, @Param('accountId', ParseUUIDPipe) accountId: string): Promise<void> {
    return this.auth.removeMember(account, accountId);
  }
}
