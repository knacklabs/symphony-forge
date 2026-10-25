import { describe, expect, it } from 'vitest';
import { validateEnvironment } from '@app/core';

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
