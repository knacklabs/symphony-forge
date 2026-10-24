import { Controller, Get, Query, Res } from '@nestjs/common';
import { ApiCookieAuth, ApiOperation, ApiResponse, ApiTags } from '@nestjs/swagger';
import type { Response } from 'express';
import { ApiEnvelope, ApiErrors, ApiZodQuery, CurrentAccount, sendCsv, ZodValidationPipe, type AccountPrincipal, type CsvColumn } from '@app/core';
import { formatDateTime, memberListQuerySchema, type Member, type MemberListQuery } from '@app/shared';
import { OrganisationsService } from './organisations.service';
import { MemberListResponseDto } from './organisations.dto';

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
