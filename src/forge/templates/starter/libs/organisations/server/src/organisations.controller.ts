import { Body, Controller, Delete, Get, HttpCode, Param, ParseUUIDPipe, Patch, Post, Put, Query, Res } from '@nestjs/common';
import { ApiCookieAuth, ApiOperation, ApiParam, ApiResponse, ApiTags } from '@nestjs/swagger';
import type { Response } from 'express';
import { AdminOnly, ApiEnvelope, ApiErrors, ApiZodBody, ApiZodQuery, CurrentAccount, sendCsv, ZodValidationPipe, type AccountPrincipal, type CsvColumn } from '@app/core-server';
import { agentToolsChangeSchema, agentToolsFeatureSchema, changeRoleSchema, memberListQuerySchema, type AgentKey, type AgentTools, type AgentToolsChange, type ChangeRoleInput, type Member, type MemberListQuery } from '@app/organisations-contracts';
import { formatDateTime } from '@app/shared-util';
import { OrganisationsService } from './organisations.service';
import { AgentKeyResponseDto, AgentToolsResponseDto, MemberListResponseDto, MemberResponseDto } from './organisations.dto';

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

  @Post(':accountId/key')
  @AdminOnly()
  @ApiParam({ name: 'accountId', type: String, format: 'uuid', example: 'b3e1d349-1d8e-481c-8c69-99ea576f94c7', description: 'The account of an agent in your organisation.' })
  @ApiOperation({ summary: 'Create a key for an agent account.', description: 'Only admins can create keys. The key shows this one time only. A new key replaces the old one, which stops working at once.' })
  @ApiEnvelope(AgentKeyResponseDto, 201)
  @ApiErrors(401, 403, 404)
  createKey(@CurrentAccount() account: AccountPrincipal, @Param('accountId', ParseUUIDPipe) accountId: string): Promise<AgentKey> {
    return this.organisations.createKey(account, accountId);
  }

  @Delete(':accountId/key')
  @AdminOnly()
  @HttpCode(200)
  @ApiParam({ name: 'accountId', type: String, format: 'uuid', example: 'b3e1d349-1d8e-481c-8c69-99ea576f94c7', description: 'The account of an agent in your organisation.' })
  @ApiOperation({ summary: 'Revoke an agent account’s key.', description: 'Only admins can revoke keys. Agents that use the key stop working at once.' })
  @ApiResponse({ status: 200, schema: { example: { success: true, data: null, error: null } } })
  @ApiErrors(401, 403, 404)
  revokeKey(@CurrentAccount() account: AccountPrincipal, @Param('accountId', ParseUUIDPipe) accountId: string): Promise<void> {
    return this.organisations.revokeKey(account, accountId);
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

@ApiTags('Organisations')
@ApiCookieAuth('session')
@Controller('agent-tools')
export class AgentToolsController {
  constructor(private readonly organisations: OrganisationsService) {}

  @Get()
  @AdminOnly()
  @ApiOperation({ summary: 'List the features whose delete and restore tools agents can use.', description: 'Only admins can read it. Every feature’s search, get, create and update tools are always on.' })
  @ApiEnvelope(AgentToolsResponseDto, 200)
  @ApiErrors(401, 403)
  list(@CurrentAccount() account: AccountPrincipal): Promise<AgentTools> {
    return this.organisations.agentTools(account.organisationId);
  }

  @Put(':feature')
  @AdminOnly()
  @ApiParam({ name: 'feature', type: String, example: 'projects', description: 'The feature’s plural in kebab case.' })
  @ApiZodBody(agentToolsChangeSchema)
  @ApiOperation({ summary: 'Turn agent delete and restore on or off for one feature.', description: 'Only admins can change it. The agent account’s role still applies.' })
  @ApiEnvelope(AgentToolsResponseDto, 200)
  @ApiErrors(400, 401, 403)
  change(
    @CurrentAccount() account: AccountPrincipal,
    @Param('feature', new ZodValidationPipe(agentToolsFeatureSchema)) feature: string,
    @Body(new ZodValidationPipe(agentToolsChangeSchema)) input: AgentToolsChange,
  ): Promise<AgentTools> {
    return this.organisations.setAgentTools(account, feature, input.deleteAndRestore);
  }
}
