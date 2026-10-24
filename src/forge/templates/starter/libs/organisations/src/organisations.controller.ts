import { Body, Controller, Get, Param, ParseUUIDPipe, Patch, Query, Res } from '@nestjs/common';
import { ApiCookieAuth, ApiOperation, ApiParam, ApiResponse, ApiTags } from '@nestjs/swagger';
import type { Response } from 'express';
import { AdminOnly, ApiEnvelope, ApiErrors, ApiZodBody, ApiZodQuery, CurrentAccount, sendCsv, ZodValidationPipe, type AccountPrincipal, type CsvColumn } from '@app/core';
import { changeRoleSchema, formatDateTime, memberListQuerySchema, type ChangeRoleInput, type Member, type MemberListQuery } from '@app/shared';
import { OrganisationsService } from './organisations.service';
import { MemberListResponseDto, MemberResponseDto } from './organisations.dto';

const MEMBER_CSV_COLUMNS: CsvColumn<Member>[] = [
  { header: 'Email', value: (member) => member.email },
  { header: 'Role', value: (member) => member.role },
  { header: 'Joined (UTC)', value: (member) => formatDateTime(member.createdAtUtc, 'UTC') },
];

@ApiTags('Organisations')
@ApiCookieAuth('session')
@Controller('members')
export class OrganisationsController {
  constructor(private readonly organisations: OrganisationsService) {}

  @Patch(':accountId')
  @AdminOnly()
  @ApiZodBody(changeRoleSchema)
  @ApiParam({ name: 'accountId', type: String, format: 'uuid', example: 'b3e1d349-1d8e-481c-8c69-99ea576f94c7', description: 'The account of another member in your organisation.' })
  @ApiOperation({ summary: 'Change another member’s role.', description: 'Only admins can change roles. Your own role cannot change, and the target must belong to your organisation.' })
  @ApiEnvelope(MemberResponseDto, 200)
  @ApiErrors(400, 401, 403, 404)
  changeRole(@CurrentAccount() account: AccountPrincipal, @Param('accountId', ParseUUIDPipe) accountId: string, @Body(new ZodValidationPipe(changeRoleSchema)) input: ChangeRoleInput): Promise<MemberResponseDto> {
    return this.organisations.changeRole(account, accountId, input.role);
  }

  @Get()
  @ApiZodQuery(memberListQuerySchema)
  @ApiOperation({ summary: 'List your organisation’s members, oldest first.' })
  @ApiEnvelope(MemberListResponseDto, 200)
  @ApiErrors(400, 401)
  list(@CurrentAccount() account: AccountPrincipal, @Query(new ZodValidationPipe(memberListQuerySchema)) query: MemberListQuery) {
    return this.organisations.list(account.organisationId, query);
  }

  @Get('export')
  @ApiOperation({ summary: 'Download every member of your organisation, oldest first.' })
  @ApiResponse({ status: 200, description: 'The members.csv file: Email, Role and Joined (UTC).' })
  @ApiErrors(401)
  async export(@CurrentAccount() account: AccountPrincipal, @Res() response: Response): Promise<void> {
    sendCsv(response, 'members.csv', MEMBER_CSV_COLUMNS, await this.organisations.listAll(account.organisationId));
  }
}
