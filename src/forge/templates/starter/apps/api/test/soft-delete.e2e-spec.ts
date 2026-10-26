import request from 'supertest';
import { describe, expect, it } from 'vitest';
import { apiBaseUrl, credentials, csrfToken, psql } from './helpers';

describe('soft delete', () => {
  it('the database refuses a hard delete of a project', async () => {
    const client = request.agent(apiBaseUrl);
    const csrf = csrfToken(await client.post('/api/v1/auth/sign-up').send(credentials()).expect(201));
    const created = await client
      .post('/api/v1/projects')
      .set('x-csrf-token', csrf)
      .send({ name: 'Protected project', status: 'active' })
      .expect(201);
    const projectId = created.body.data.id as string;

    const hardDelete = psql(`DELETE FROM projects."Project" WHERE id = '${projectId}'`);
    expect(hardDelete.status).not.toBe(0);
    expect(hardDelete.output).toContain('are soft deleted');
    await client.get(`/api/v1/projects/${projectId}`).expect(200);

    await client.delete(`/api/v1/projects/${projectId}`).set('x-csrf-token', csrf).expect(200);
    await client.get(`/api/v1/projects/${projectId}`).expect(404);
    const retained = psql(
      `SELECT CASE WHEN EXISTS (SELECT 1 FROM projects."Project" WHERE id = '${projectId}' AND "deletedAtUtc" IS NOT NULL) THEN 'retained' ELSE 'missing' END`,
    );
    expect(retained.status).toBe(0);
    expect(retained.output).toContain('retained');
  });
});
