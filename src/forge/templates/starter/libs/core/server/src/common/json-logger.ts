import { Injectable, type LoggerService } from '@nestjs/common';
import { correlationStorage } from './correlation.middleware';
import { getAppEnvironment } from '../config/environment';

@Injectable()
export class JsonLogger implements LoggerService {
  log(message: unknown, ...parameters: unknown[]): void {
    this.write('info', message, parameters);
  }

  warn(message: unknown, ...parameters: unknown[]): void {
    this.write('warn', message, parameters);
  }

  error(message: unknown, ...parameters: unknown[]): void {
    this.write('error', message, parameters);
  }

  debug(message: unknown, ...parameters: unknown[]): void {
    this.write('debug', message, parameters);
  }

  verbose(message: unknown, ...parameters: unknown[]): void {
    this.write('debug', message, parameters);
  }

  fatal(message: unknown, ...parameters: unknown[]): void {
    this.write('fatal', message, parameters);
  }

  private write(level: string, message: unknown, parameters: unknown[]): void {
    const moduleName = parameters.find((value): value is string => typeof value === 'string') ?? 'api';
    if (moduleName === 'RoutesResolver' || moduleName === 'RouterExplorer') return;
    const contextValue = parameters.find((value) => typeof value === 'object' && value !== null);
    const context = contextValue && typeof contextValue === 'object' ? contextValue : {};
    process.stdout.write(
      `${JSON.stringify({
        timestampUtc: new Date().toISOString(),
        level,
        message: typeof message === 'string' ? message : 'API event',
        context,
        environment: getAppEnvironment(),
        serviceName: 'api',
        module: moduleName,
        correlationId: correlationStorage.getStore() ?? null,
      })}\n`,
    );
  }
}
