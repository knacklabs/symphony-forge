import { Global, Module } from '@nestjs/common';
import { JsonLogger } from './json-logger';
import { ErrorReportController, ErrorReporter } from './error-report';

@Global()
@Module({ controllers: [ErrorReportController], providers: [JsonLogger, ErrorReporter], exports: [JsonLogger, ErrorReporter] })
export class CommonModule {}
