import { describe, expect, it, vi } from 'vitest';
import { JsonLogger } from './json-logger';
import { validateEnvironment } from '../config/environment';

const validEnvironment = {
  APP_ENV: 'test',
  DATABASE_URL: 'postgresql://postgres:test-password@localhost:5432/starter_test',
  APP_ORIGIN: 'http://127.0.0.1:3000',
  PORT: 3000,
};

describe('JSON logger', () => {
  // Test audit:
  // 1. Protects the observable output threshold for each Nest logger level.
  // 2. Fails if debug or info is emitted at warn, or warn, error or fatal is suppressed.
  // 3. Existing tests cover API responses and config validation, not logger output filtering.
  // 4. Uses the public logger and captures stdout; it needs no production test seam.
  it('the logger writes nothing below LOG_LEVEL', () => {
    const write = vi.spyOn(process.stdout, 'write').mockImplementation(() => true);
    try {
      validateEnvironment({ ...validEnvironment, LOG_LEVEL: 'warn' });
      const logger = new JsonLogger();

      logger.debug('below debug');
      logger.log('below info');
      expect(write).not.toHaveBeenCalled();

      logger.warn('warning');
      logger.error('failure');
      logger.fatal('cannot continue');
      const levels = write.mock.calls.map(([line]) => {
        const event: unknown = JSON.parse(String(line));
        if (typeof event !== 'object' || event === null || !('level' in event)) {
          throw new Error('The logger wrote a line without a level.');
        }
        return event.level;
      });
      expect(levels).toEqual(['warn', 'error', 'fatal']);
    } finally {
      validateEnvironment({ ...validEnvironment, LOG_LEVEL: 'info' });
    }
  });

  // Test audit:
  // 1. Protects recursive removal of sensitive context values while keeping ordinary details.
  // 2. Fails if a sensitive field name or nested array value bypasses removal.
  // 3. Existing API tests do not supply arbitrary nested log details or inspect logger output.
  // 4. Uses the public logger and captures its written JSON; it needs no production test seam.
  it('the logger removes password, token, secret, key and authorization values', () => {
    const write = vi.spyOn(process.stdout, 'write').mockImplementation(() => true);
    const context = {
      password: 'p',
      resetToken: 't',
      client_secret: 's',
      apiKey: 'k',
      Authorization: 'a',
      nested: [{ newPassword: 'n' }],
      projectId: 'x',
    };
    const secretValues = [
      context.password,
      context.resetToken,
      context.client_secret,
      context.apiKey,
      context.Authorization,
      context.nested[0].newPassword,
    ];

    try {
      validateEnvironment({ ...validEnvironment, LOG_LEVEL: 'info' });
      new JsonLogger().log('Project details', context);

      expect(write).toHaveBeenCalledTimes(1);
      const output = String(write.mock.calls[0]?.[0] ?? '');
      const event: unknown = JSON.parse(output);
      if (typeof event !== 'object' || event === null || !('context' in event)) {
        throw new Error('The logger wrote a line without context.');
      }
      expect(event.context).toEqual({
        password: '[removed]',
        resetToken: '[removed]',
        client_secret: '[removed]',
        apiKey: '[removed]',
        Authorization: '[removed]',
        nested: [{ newPassword: '[removed]' }],
        projectId: context.projectId,
      });
      for (const secretValue of secretValues) {
        expect(output).not.toContain(JSON.stringify(secretValue));
      }
    } finally {
      validateEnvironment({ ...validEnvironment, LOG_LEVEL: 'info' });
    }
  });
});
