import { Body, Controller, Delete, Get, HttpCode, Param, ParseUUIDPipe, Post, Put, Query } from '@nestjs/common';
import { ApiBody, ApiCookieAuth, ApiOperation, ApiParam, ApiResponse, ApiTags } from '@nestjs/swagger';
import { ApiEnvelope, ApiErrors, ZodValidationPipe } from '@app/core';
import { CurrentAccount, type AccountPrincipal } from '@app/auth';
import { ProjectInputDto, ProjectListQueryDto, ProjectListResponseDto, ProjectResponseDto } from './projects.dto';
import { ProjectsService } from './projects.service';
import { projectSchema, type ProjectInput } from '@app/shared';

@ApiTags('Projects')
@ApiCookieAuth('session')
@Controller('projects')
export class ProjectsController {
  constructor(private readonly projects: ProjectsService) {}

  @Get()
  @ApiOperation({ summary: 'List the signed-in account’s projects.' })
  @ApiEnvelope(ProjectListResponseDto, 200)
  @ApiErrors(400, 401)
  list(@CurrentAccount() account: AccountPrincipal, @Query() query: ProjectListQueryDto) {
    return this.projects.list(account, query);
  }

  @Post()
  @ApiBody({ type: ProjectInputDto })
  @ApiOperation({ summary: 'Create a project for the signed-in account.' })
  @ApiEnvelope(ProjectResponseDto, 201)
  @ApiErrors(400, 401, 403)
  create(@CurrentAccount() account: AccountPrincipal, @Body(new ZodValidationPipe(projectSchema)) input: ProjectInput) {
    return this.projects.create(account, input);
  }

  @Get(':id')
  @ApiParam({ name: 'id', description: 'The project identifier.', example: 'b3e1d349-1d8e-481c-8c69-99ea576f94c7' })
  @ApiOperation({ summary: 'Read one project owned by the signed-in account.' })
  @ApiEnvelope(ProjectResponseDto, 200)
  @ApiErrors(400, 401, 404)
  get(@CurrentAccount() account: AccountPrincipal, @Param('id', ParseUUIDPipe) id: string) {
    return this.projects.get(account, id);
  }

  @Put(':id')
  @ApiParam({ name: 'id', description: 'The project identifier.', example: 'b3e1d349-1d8e-481c-8c69-99ea576f94c7' })
  @ApiBody({ type: ProjectInputDto })
  @ApiOperation({ summary: 'Replace a project owned by the signed-in account.' })
  @ApiEnvelope(ProjectResponseDto, 200)
  @ApiErrors(400, 401, 403, 404)
  update(
    @CurrentAccount() account: AccountPrincipal,
    @Param('id', ParseUUIDPipe) id: string,
    @Body(new ZodValidationPipe(projectSchema)) input: ProjectInput,
  ) {
    return this.projects.update(account, id, input);
  }

  @Delete(':id')
  @HttpCode(200)
  @ApiParam({ name: 'id', description: 'The project identifier.', example: 'b3e1d349-1d8e-481c-8c69-99ea576f94c7' })
  @ApiOperation({ summary: 'Soft-delete a project owned by the signed-in account.' })
  @ApiResponse({ status: 200, schema: { example: { success: true, data: null, error: null } } })
  @ApiErrors(401, 403, 404)
  delete(@CurrentAccount() account: AccountPrincipal, @Param('id', ParseUUIDPipe) id: string): Promise<void> {
    return this.projects.delete(account, id);
  }
}
