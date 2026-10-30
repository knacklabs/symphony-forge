import { randomUUID } from 'node:crypto';
import request from 'supertest';
import { describe, expect, it } from 'vitest';
import { apiBaseUrl, credentials, logEvents, psql } from './helpers';

describe('error reports', () => {
  it('accepts a public report without its page query or fragment', async () => {
    const token = `private-${randomUUID()}`;
    const response = await request(apiBaseUrl)
      .post('/api/v1/error-reports')
      .send({ name: 'TypeError', path: `/projects?token=${token}#private-fragment` })
      .expect(201);

    const errorId = response.body.data.errorId as string;
    expect(response.body).toMatchObject({ success: true, data: { errorId }, error: null });
    expect(errorId).toEqual(expect.any(String));

    const reports = logEvents('api').filter(({ message, context }) =>
      message === 'Error report' && context?.errorId === errorId);
    expect(reports).toHaveLength(1);
    expect(reports[0].context).toMatchObject({ errorId, source: 'web', path: '/projects' });
    expect(JSON.stringify(reports[0])).not.toContain(token);
    expect(JSON.stringify(reports[0])).not.toContain('private-fragment');

    const invalid = await request(apiBaseUrl)
      .post('/api/v1/error-reports')
      .send({ name: 'TypeError', path: '/projects', token })
      .expect(400);
    expect(invalid.body.error.code).toBe('VALIDATION_ERROR');
    expect(invalid.body.error.details.fieldErrors).toEqual(
      expect.arrayContaining([expect.objectContaining({ field: 'token', reason: 'Remove this field.' })]),
    );
    expect(JSON.stringify(invalid.body)).not.toContain(token);
  });

  it('an API crash writes one error report', async () => {
    const account = credentials();
    const constraintName = `crash_${randomUUID().replaceAll('-', '')}`;
    const added = psql(
      `ALTER TABLE core."Account" ADD CONSTRAINT "${constraintName}" CHECK (email <> '${account.email}') NOT VALID;`,
    );
    expect(added.status, added.output).toBe(0);

    try {
      const response = await request(apiBaseUrl)
        .post('/api/v1/auth/sign-up')
        .send(account)
        .expect(500);
      const errorId = response.body.error.errorId as string;
      expect(errorId).toEqual(expect.any(String));

      const reports = logEvents('api').filter(({ message, context }) =>
        message === 'Error report' && context?.errorId === errorId);
      expect(reports).toHaveLength(1);
      expect(reports[0].context).toMatchObject({
        errorId,
        source: 'api',
        method: 'POST',
        path: '/api/v1/auth/sign-up',
        status: 500,
      });
      expect(reports[0].context?.name).toEqual(expect.any(String));
      expect(reports[0].context).not.toHaveProperty('message');
      expect(reports[0].context).not.toHaveProperty('stack');
      expect(JSON.stringify(reports[0])).not.toContain(account.email);
      expect(JSON.stringify(reports[0])).not.toContain('violates check constraint');
    } finally {
      const dropped = psql(`ALTER TABLE core."Account" DROP CONSTRAINT IF EXISTS "${constraintName}";`);
      expect(dropped.status, dropped.output).toBe(0);
    }
  });
});
