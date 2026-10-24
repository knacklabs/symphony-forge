import request from 'supertest';
import { describe, expect, it } from 'vitest';
import { apiBaseUrl, credentials, csrfToken } from './helpers';

const PROJECTS_HEADER = 'Name,Status,Created (UTC),Updated (UTC)';

describe('organisations', () => {
  it('organisation isolation: another organisation gets 404 and the project stays unchanged', async () => {
    const owner = credentials();
    const ownerClient = request.agent(apiBaseUrl);
    const ownerSignUp = await ownerClient.post('/api/v1/auth/sign-up').send(owner).expect(201);
    const csrf = csrfToken(ownerSignUp);
    const created = await ownerClient
      .post('/api/v1/projects')
      .set('x-csrf-token', csrf)
      .send({ name: 'Private project', status: 'active' })
      .expect(201);
    const projectId = created.body.data.id as string;

    const otherClient = request.agent(apiBaseUrl);
    const otherSignUp = await otherClient.post('/api/v1/auth/sign-up').send(credentials()).expect(201);
    const otherCsrf = csrfToken(otherSignUp);

    const otherProjects = await otherClient.get('/api/v1/projects').expect(200);
    expect(otherProjects.body.data.items).toEqual([]);
    expect(otherProjects.body.data.pagination.totalItems).toBe(0);
    const otherExport = await otherClient.get('/api/v1/projects/export').expect(200);
    expect(otherExport.text).toBe(`${PROJECTS_HEADER}\r\n`);

    await otherClient.get(`/api/v1/projects/${projectId}`).expect(404);
    await otherClient
      .put(`/api/v1/projects/${projectId}`)
      .set('x-csrf-token', otherCsrf)
      .send({ name: 'Changed by another organisation', status: 'archived' })
      .expect(404);
    await otherClient.delete(`/api/v1/projects/${projectId}`).set('x-csrf-token', otherCsrf).expect(404);

    await ownerClient.get(`/api/v1/projects/${projectId}`).expect(200).expect(({ body }) => {
      expect(body.data).toMatchObject({ name: 'Private project', status: 'active' });
    });
  });

  it('a new account is the only admin of its own organisation', async () => {
    const account = credentials();
    const client = request.agent(apiBaseUrl);
    const signUp = await client.post('/api/v1/auth/sign-up').send(account).expect(201);
    expect(signUp.body.data).toMatchObject({ email: account.email, role: 'admin' });

    const signIn = await request(apiBaseUrl).post('/api/v1/auth/sign-in').send(account).expect(200);
    expect(signIn.body.data).toMatchObject({ email: account.email, role: 'admin' });

    await client.get('/api/v1/auth/me').expect(200).expect(({ body }) => {
      expect(body.data).toMatchObject({ email: account.email, role: 'admin' });
    });

    const members = await client.get('/api/v1/members?page=1&limit=20').expect(200);
    expect(members.body.data.items).toHaveLength(1);
    expect(members.body.data.items[0]).toMatchObject({ email: account.email, role: 'admin' });
    expect(members.body.data.items[0].createdAtUtc).toEqual(expect.any(String));
    expect(members.body.data.pagination).toMatchObject({ page: 1, limit: 20, totalItems: 1 });
  });
});
