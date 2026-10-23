import { randomUUID } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import request from 'supertest';
import { describe, expect, it } from 'vitest';

const apiBaseUrl = process.env.API_TEST_URL ?? 'http://127.0.0.1:3000';
const productionApiBaseUrl = process.env.PRODUCTION_API_TEST_URL ?? 'http://127.0.0.1:3001';

function credentials() {
  return { email: `starter-${randomUUID()}@example.test`, password: 'correct-horse-battery-staple' };
}

function csrfToken(response: request.Response): string {
  const cookies = response.get('Set-Cookie') ?? [];
  const cookie = cookies.find((value) => value.startsWith('starter_csrf='));
  if (!cookie) throw new Error('The API did not set its CSRF cookie.');
  return cookie.slice('starter_csrf='.length).split(';', 1)[0];
}

function latestResetToken(service: 'api' | 'production-api'): string {
  const logs = execFileSync('docker', ['compose', '-f', 'compose.test.yml', 'logs', '--no-color', service], { encoding: 'utf8' });
  const line = logs.split(/\r?\n/).reverse().find((value) => value.includes('"resetUrl"'));
  if (!line) throw new Error(`The ${service} service did not log a test reset link.`);
  const jsonStart = line.indexOf('{');
  const event: unknown = JSON.parse(line.slice(jsonStart));
  if (typeof event !== 'object' || event === null || !('context' in event)) throw new Error('The reset mail log has an invalid shape.');
  const context: unknown = event.context;
  if (typeof context !== 'object' || context === null || !('resetUrl' in context) || typeof context.resetUrl !== 'string') {
    throw new Error('The reset mail log has no reset URL.');
  }
  const token = new URL(context.resetUrl).searchParams.get('token');
  if (!token) throw new Error('The reset mail log has no reset token.');
  return token;
}

describe('starter API', () => {
  it('signs up, signs in, and signs out with a server session', async () => {
    const account = credentials();
    const client = request.agent(apiBaseUrl);
    const signUp = await client.post('/api/v1/auth/sign-up').send(account).expect(201);

    expect(signUp.body).toMatchObject({ success: true, data: { email: account.email }, error: null });
    expect(signUp.get('Set-Cookie')).toEqual(
      expect.arrayContaining([expect.stringMatching(/starter_session=.*HttpOnly.*SameSite=Lax/)]),
    );
    expect((await client.get('/api/v1/auth/me').expect(200)).body.data.email).toBe(account.email);

    await client
      .post('/api/v1/auth/sign-out')
      .set('x-csrf-token', csrfToken(signUp))
      .expect(200);
    await client.get('/api/v1/auth/me').expect(401);

    const signIn = await client.post('/api/v1/auth/sign-in').send(account).expect(200);
    expect(signIn.body.data.email).toBe(account.email);
    await client.get('/api/v1/auth/me').expect(200);
  });

  it('creates, lists, reads, updates, and deletes a project through the API', async () => {
    const account = credentials();
    const client = request.agent(apiBaseUrl);
    const signUp = await client.post('/api/v1/auth/sign-up').send(account).expect(201);
    const csrf = csrfToken(signUp);

    const created = await client
      .post('/api/v1/projects')
      .set('x-csrf-token', csrf)
      .send({ name: 'First project', status: 'active' })
      .expect(201);
    const projectId = created.body.data.id as string;
    expect(created.body.data).toMatchObject({ name: 'First project', status: 'active' });

    const list = await client.get('/api/v1/projects?page=1&limit=20&sortBy=name&sortOrder=asc').expect(200);
    expect(list.body.data.items).toEqual([expect.objectContaining({ id: projectId, name: 'First project' })]);
    expect(list.body.data.pagination).toMatchObject({ page: 1, limit: 20, totalItems: 1, totalPages: 1 });

    await client.get(`/api/v1/projects/${projectId}`).expect(200).expect(({ body }) => {
      expect(body.data.id).toBe(projectId);
    });
    await client
      .put(`/api/v1/projects/${projectId}`)
      .set('x-csrf-token', csrf)
      .send({ name: 'Renamed project', status: 'archived' })
      .expect(200)
      .expect(({ body }) => expect(body.data).toMatchObject({ name: 'Renamed project', status: 'archived' }));
    await client
      .delete(`/api/v1/projects/${projectId}`)
      .set('x-csrf-token', csrf)
      .expect(200)
      .expect(({ body }) => expect(body).toMatchObject({ success: true, data: null, error: null }));
    await client.get(`/api/v1/projects/${projectId}`).expect(404);
  });

  it('account isolation: returns 404 for another account and leaves the project unchanged', async () => {
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

    await otherClient.get(`/api/v1/projects/${projectId}`).expect(404);
    await otherClient
      .put(`/api/v1/projects/${projectId}`)
      .set('x-csrf-token', otherCsrf)
      .send({ name: 'Changed by another account', status: 'archived' })
      .expect(404);
    await otherClient.delete(`/api/v1/projects/${projectId}`).set('x-csrf-token', otherCsrf).expect(404);

    await ownerClient.get(`/api/v1/projects/${projectId}`).expect(200).expect(({ body }) => {
      expect(body.data).toMatchObject({ name: 'Private project', status: 'active' });
    });
  });

  it('forgot-password gives the same response for known and unknown email addresses', async () => {
    const account = credentials();
    await request(apiBaseUrl).post('/api/v1/auth/sign-up').send(account).expect(201);

    const known = await request(apiBaseUrl).post('/api/v1/auth/forgot-password').send({ email: account.email }).expect(200);
    const unknown = await request(apiBaseUrl)
      .post('/api/v1/auth/forgot-password')
      .send({ email: `missing-${randomUUID()}@example.test` })
      .expect(200);

    expect(known.body).toEqual(unknown.body);
    expect(known.body.data.message).toBe('If an account exists, a reset link has been sent.');
  });

  it('resets a password once, signs out old sessions, and accepts the new password', async () => {
    const account = credentials();
    const client = request.agent(apiBaseUrl);
    await client.post('/api/v1/auth/sign-up').send(account).expect(201);
    await request(apiBaseUrl).post('/api/v1/auth/forgot-password').send({ email: account.email }).expect(200);
    const token = latestResetToken('api');
    const newPassword = 'different-correct-horse-password';

    await request(apiBaseUrl).post('/api/v1/auth/reset-password').send({ token, password: newPassword }).expect(200);
    await client.get('/api/v1/auth/me').expect(401);
    await request(apiBaseUrl).post('/api/v1/auth/sign-in').send(account).expect(401);
    await request(apiBaseUrl).post('/api/v1/auth/sign-in').send({ ...account, password: newPassword }).expect(200);
    await request(apiBaseUrl).post('/api/v1/auth/reset-password').send({ token, password: account.password }).expect(400);
  });

  it('rejects invalid input with field errors in the API envelope', async () => {
    const response = await request(apiBaseUrl)
      .post('/api/v1/auth/sign-up')
      .send({ email: 'not-an-email', password: 'short', unexpected: true })
      .expect(400);

    expect(response.body).toMatchObject({
      success: false,
      data: null,
      error: { code: 'VALIDATION_ERROR', message: 'Check the fields and try again.' },
    });
    expect(response.body.error.details.fieldErrors).toEqual(expect.arrayContaining([
      expect.objectContaining({ field: 'email' }),
      expect.objectContaining({ field: 'password' }),
      expect.objectContaining({ field: 'unexpected' }),
    ]));
  });

  it('rejects a whitespace-only project name after trimming input', async () => {
    const client = request.agent(apiBaseUrl);
    const signUp = await client.post('/api/v1/auth/sign-up').send(credentials()).expect(201);

    const response = await client
      .post('/api/v1/projects')
      .set('x-csrf-token', csrfToken(signUp))
      .send({ name: '   ', status: 'active' })
      .expect(400);
    expect(response.body.error.details.fieldErrors).toEqual(expect.arrayContaining([
      expect.objectContaining({ field: 'name' }),
    ]));
  });

  it('requires a signed-in account and a valid CSRF token before project changes', async () => {
    await request(apiBaseUrl).get('/api/v1/projects').expect(401).expect(({ body }) => {
      expect(body.error.code).toBe('UNAUTHENTICATED');
    });

    const client = request.agent(apiBaseUrl);
    const signUp = await client.post('/api/v1/auth/sign-up').send(credentials()).expect(201);
    const csrf = csrfToken(signUp);
    await client.post('/api/v1/projects').send({ name: 'No token', status: 'active' }).expect(403);
    await client
      .post('/api/v1/projects')
      .set('x-csrf-token', `${csrf}wrong`)
      .send({ name: 'Bad token', status: 'active' })
      .expect(403);
  });

  it('rejects cross-origin sign-in requests before they can change server state', async () => {
    const response = await request(apiBaseUrl)
      .post('/api/v1/auth/sign-up')
      .set('Origin', 'https://attacker.example')
      .send(credentials())
      .expect(403);
    expect(response.body.error.code).toBe('CSRF_CHECK_FAILED');
  });

  it('production forgot-password does not log a reset link', async () => {
    const account = credentials();
    await request(productionApiBaseUrl).post('/api/v1/auth/sign-up').send(account).expect(201);

    const known = await request(productionApiBaseUrl)
      .post('/api/v1/auth/forgot-password')
      .send({ email: account.email })
      .expect(200);
    const unknown = await request(productionApiBaseUrl)
      .post('/api/v1/auth/forgot-password')
      .send({ email: `missing-${randomUUID()}@example.test` })
      .expect(200);
    expect(known.body).toEqual(unknown.body);

    const logs = execFileSync('docker', ['compose', '-f', 'compose.test.yml', 'logs', '--no-color', 'production-api'], { encoding: 'utf8' });
    expect(logs).not.toContain('/reset-password');
    expect(logs).not.toMatch(/[A-Za-z0-9_-]{43}/);
  });
});
