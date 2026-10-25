import { Controller, Get, Res } from '@nestjs/common';
import { ApiCookieAuth, ApiExtraModels, ApiOkResponse, ApiOperation, ApiResponse, ApiTags, getSchemaPath } from '@nestjs/swagger';
import type { Response } from 'express';
import { AdminOnly, ApiErrors, CurrentAccount, sendCsv, type AccountPrincipal, type CsvColumn } from '@app/core';
import { formatDateTime, type HistoryEntry } from '@app/shared';
import { ChangeRecordResponseDto } from './history.dto';
import { HistoryService } from './history.service';

const HISTORY_CSV_COLUMNS: CsvColumn<HistoryEntry>[] = [
  { header: 'When (UTC)', value: (record) => formatDateTime(record.createdAtUtc, 'UTC') },
  { header: 'Who', value: (record) => record.actorEmail },
  { header: 'What', value: (record) => record.summary },
];

@ApiTags('History')
@ApiCookieAuth('session')
@AdminOnly()
@Controller('history')
export class HistoryController {
  constructor(private readonly history: HistoryService) {}

  @Get()
  @ApiOperation({ summary: 'List your organisation’s newest 100 changes.', description: 'Only admins can read change history. Changes are returned newest first.' })
  @ApiExtraModels(ChangeRecordResponseDto)
  @ApiOkResponse({ schema: {
    type: 'object', required: ['success', 'data', 'error'], properties: {
      success: { type: 'boolean', example: true },
      data: { type: 'array', items: { $ref: getSchemaPath(ChangeRecordResponseDto) } },
      error: { type: 'object', nullable: true, example: null },
    },
  } })
  @ApiErrors(401, 403)
  list(@CurrentAccount() account: AccountPrincipal): Promise<ChangeRecordResponseDto[]> {
    return this.history.list(account);
  }

  @Get('export')
  @ApiOperation({ summary: 'Download every change in your organisation.', description: 'Only admins can export change history. The file includes all changes, newest first.' })
  @ApiResponse({ status: 200, description: 'The history.csv file: When (UTC), Who and What.' })
  @ApiErrors(401, 403)
  async export(@CurrentAccount() account: AccountPrincipal, @Res() response: Response): Promise<void> {
    sendCsv(response, 'history.csv', HISTORY_CSV_COLUMNS, await this.history.list(account, null));
  }
}
