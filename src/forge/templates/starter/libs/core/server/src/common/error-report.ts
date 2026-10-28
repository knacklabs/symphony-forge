import { randomUUID } from 'node:crypto';
import { Body, Controller, Injectable, Post } from '@nestjs/common';
import { ApiOperation, ApiProperty, ApiTags } from '@nestjs/swagger';
import { Throttle } from '@nestjs/throttler';
import { errorReportSchema, type ErrorReportInput } from '@app/shared-util';
import { ApiEnvelope, ApiErrors } from './api-envelope.decorator';
import { ApiZodBody } from './api-zod.decorator';
import { JsonLogger } from './json-logger';
import { Public } from './public.decorator';
import { ZodValidationPipe } from './zod-validation.pipe';

@Injectable()
export class ErrorReporter {
  constructor(private readonly logger: JsonLogger) {}

  report(report: ErrorReportInput & { errorId: string; source: 'api' | 'web'; method?: string; status?: number }): void {
    this.logger.error('Error report', 'ErrorReporter', { ...report, path: report.path.split(/[?#]/, 1)[0] });
  }
}

class ErrorReportResponseDto {
  @ApiProperty({ description: 'The reference for this error report.', example: 'd49fe9c4-a93b-4e3d-a20a-1afc37f4d1c0' })
  errorId!: string;
}

@ApiTags('Error reports')
@Controller('error-reports')
export class ErrorReportController {
  constructor(private readonly reporter: ErrorReporter) {}

  @Public()
  @Post()
  @Throttle({ default: { limit: 30, ttl: 60_000 } })
  @ApiZodBody(errorReportSchema)
  @ApiOperation({ summary: 'Report a page crash.', description: 'Logs the error kind and page path without error text or a query string.' })
  @ApiEnvelope(ErrorReportResponseDto, 201)
  @ApiErrors(400, 403, 429)
  report(@Body(new ZodValidationPipe(errorReportSchema)) input: ErrorReportInput): ErrorReportResponseDto {
    const errorId = randomUUID();
    this.reporter.report({ name: input.name, path: input.path, source: 'web', errorId });
    return { errorId };
  }
}
