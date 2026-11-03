import { describe, expect, it } from 'vitest';
import { validateEnvironment } from '@app/core-server';

const validEnvironment = {
  APP_ENV: 'test',
  DATABASE_URL: 'postgresql://postgres:test-password@localhost:5432/starter_test',
  APP_ORIGIN: 'http://127.0.0.1:3000',
  PORT: 3000,
};

describe('APP_COMPANIES configuration', () => {
  it('defaults to many and accepts one or many', () => {
    expect(validateEnvironment(validEnvironment).APP_COMPANIES).toBe('many');
    for (const companies of ['one', 'many']) {
      expect(validateEnvironment({ ...validEnvironment, APP_COMPANIES: companies }).APP_COMPANIES)
        .toBe(companies);
    }
  });

  it('rejects an unsupported value', () => {
    expect(() => validateEnvironment({ ...validEnvironment, APP_COMPANIES: 'some' }))
      .toThrow('APP_COMPANIES must be one or many.');
  });
});

describe('LOG_LEVEL configuration', () => {
  // Test audit:
  // 1. Protects the validated default and the four accepted levels.
  // 2. Fails if the default changes or a supported level is rejected or mapped incorrectly.
  // 3. Existing config tests cover APP_COMPANIES only; none covers LOG_LEVEL.
  // 4. Calls the environment validator directly and needs no production test seam.
  it('LOG_LEVEL defaults to info and accepts debug, info, warn or error', () => {
    try {
      expect(validateEnvironment(validEnvironment).LOG_LEVEL).toBe('info');
      for (const level of ['debug', 'info', 'warn', 'error']) {
        expect(validateEnvironment({ ...validEnvironment, LOG_LEVEL: level }).LOG_LEVEL).toBe(level);
      }
    } finally {
      validateEnvironment({ ...validEnvironment, LOG_LEVEL: 'info' });
    }
  });

  // Test audit:
  // 1. Protects startup rejection of an unsupported log level with a clear message.
  // 2. Fails if an unknown value is accepted or startup gives no useful configuration error.
  // 3. Existing config tests reject bad APP_COMPANIES values, not bad LOG_LEVEL values.
  // 4. Calls the environment validator directly and needs no production test seam.
  it('LOG_LEVEL refuses an unsupported value', () => {
    try {
      expect(() => validateEnvironment({ ...validEnvironment, LOG_LEVEL: 'trace' }))
        .toThrow('LOG_LEVEL must be debug, info, warn or error.');
    } finally {
      validateEnvironment({ ...validEnvironment, LOG_LEVEL: 'info' });
    }
  });
});
