import { Injectable, type LoggerService } from '@nestjs/common';
import { correlationStorage } from './correlation.middleware';
import { getAppEnvironment, getLogLevel } from '../config/environment';

const LEVELS = { debug: 0, info: 1, warn: 2, error: 3, fatal: 4 };

function removeSecrets(key: string, value: unknown): unknown {
  return /password|token|secret|key|authorization/.test(key.toLowerCase().replace(/[_-]/g, ''))
    ? '[removed]' : value;
}

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

  private write(level: keyof typeof LEVELS, message: unknown, parameters: unknown[]): void {
    if (LEVELS[level] < LEVELS[getLogLevel()]) return;
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
      }, removeSecrets)}\n`,
    );
  }
}
