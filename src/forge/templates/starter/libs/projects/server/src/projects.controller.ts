import { Body, Controller, Delete, Get, HttpCode, Param, ParseUUIDPipe, Post, Put, Query, Res } from '@nestjs/common';
import { ApiCookieAuth, ApiOperation, ApiParam, ApiResponse, ApiTags } from '@nestjs/swagger';
import type { Response } from 'express';
import { ApiEnvelope, ApiErrors, ApiZodBody, ApiZodQuery, sendCsv, ZodValidationPipe, type CsvColumn } from '@app/core-server';
import { CurrentAccount, type AccountPrincipal } from '@app/core-server';
import { ProjectListResponseDto, ProjectResponseDto } from './projects.dto';
import { ProjectsService } from './projects.service';
import { formatDateTime } from '@app/shared-util';
import { projectListQuerySchema, projectSchema, type Project, type ProjectInput, type ProjectListQuery } from '@app/projects-contracts';

const PROJECT_CSV_COLUMNS: CsvColumn<Project>[] = [
  { header: 'Name', value: (project) => project.name },
  { header: 'Status', value: (project) => project.status },
  { header: 'Created (UTC)', value: (project) => formatDateTime(project.createdAtUtc, 'UTC') },
  { header: 'Updated (UTC)', value: (project) => formatDateTime(project.updatedAtUtc, 'UTC') },
];

@ApiTags('Projects')
@ApiCookieAuth('session')
@Controller('projects')
export class ProjectsController {
  constructor(private readonly projects: ProjectsService) {}

  @Get()
  @ApiZodQuery(projectListQuerySchema)
  @ApiOperation({ summary: 'List your organisation’s projects.' })
  @ApiEnvelope(ProjectListResponseDto, 200)
  @ApiErrors(400, 401)
  list(@CurrentAccount() account: AccountPrincipal, @Query(new ZodValidationPipe(projectListQuerySchema)) query: ProjectListQuery) {
    return this.projects.list(account, query);
  }

  @Post()
  @ApiZodBody(projectSchema)
  @ApiOperation({ summary: 'Create a project in your organisation.' })
  @ApiEnvelope(ProjectResponseDto, 201)
  @ApiErrors(400, 401, 403)
  create(@CurrentAccount() account: AccountPrincipal, @Body(new ZodValidationPipe(projectSchema)) input: ProjectInput) {
    return this.projects.create(account, input);
  }

  // Declared before ':id', so 'export' is not read as a project identifier.
  @Get('export')
  @ApiOperation({ summary: 'Download every project in your organisation as a CSV file, newest first.' })
  @ApiResponse({ status: 200, description: 'The projects.csv file: Name, Status, Created (UTC) and Updated (UTC).' })
  @ApiErrors(401)
  async export(@CurrentAccount() account: AccountPrincipal, @Res() response: Response): Promise<void> {
    sendCsv(response, 'projects.csv', PROJECT_CSV_COLUMNS, await this.projects.listAll(account));
  }

  @Get(':id')
  @ApiParam({ name: 'id', description: 'The project identifier.', example: 'b3e1d349-1d8e-481c-8c69-99ea576f94c7' })
  @ApiOperation({ summary: 'Read one project in your organisation.' })
  @ApiEnvelope(ProjectResponseDto, 200)
  @ApiErrors(400, 401, 404)
  get(@CurrentAccount() account: AccountPrincipal, @Param('id', ParseUUIDPipe) id: string) {
    return this.projects.get(account, id);
  }

  @Put(':id')
  @ApiParam({ name: 'id', description: 'The project identifier.', example: 'b3e1d349-1d8e-481c-8c69-99ea576f94c7' })
  @ApiZodBody(projectSchema)
  @ApiOperation({ summary: 'Replace a project in your organisation.' })
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
  @ApiOperation({ summary: 'Soft-delete a project in your organisation.' })
  @ApiResponse({ status: 200, schema: { example: { success: true, data: null, error: null } } })
  @ApiErrors(401, 403, 404)
  delete(@CurrentAccount() account: AccountPrincipal, @Param('id', ParseUUIDPipe) id: string): Promise<void> {
    return this.projects.delete(account, id);
  }
}
