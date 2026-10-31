import { Controller, Delete, HttpCode, Param, ParseUUIDPipe } from '@nestjs/common';
import { ApiCookieAuth, ApiOperation, ApiParam, ApiResponse, ApiTags } from '@nestjs/swagger';
import { AdminOnly, ApiErrors, CurrentAccount, type AccountPrincipal } from '@app/core-server';
import { AuthService } from './auth.service';

@ApiTags('Organisations')
@ApiCookieAuth('session')
@Controller('members')
export class MembersController {
  constructor(private readonly auth: AuthService) {}

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
