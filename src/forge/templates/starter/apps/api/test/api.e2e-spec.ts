import { randomUUID } from 'node:crypto';
import { execFileSync, spawnSync } from 'node:child_process';
import request from 'supertest';
import { describe, expect, it } from 'vitest';
import { apiBaseUrl, credentials, csrfToken, logEvents, productionApiBaseUrl } from './helpers';

function latestResetToken(service: 'api' | 'production-api'): string {
  const event = logEvents(service).reverse().find(({ context }) => typeof context?.resetUrl === 'string');
  if (!event) throw new Error(`The ${service} service did not log a test reset link.`);
  const token = new URL(String(event.context?.resetUrl)).searchParams.get('token');
  if (!token) throw new Error('The reset mail log has no reset token.');
  return token;
}

describe('starter API', () => {
  // Audit: inspect the real container user, which a compose override can change even
  // with a non-root Dockerfile. The template check cannot reach that runtime contract.
  // A root-user regression fails here without a production seam or a fake process.
  it('the API container runs as a user that is not root', () => {
    const result = spawnSync('docker', [
      'compose', '-f', 'compose.test.yml', 'exec', '-T', 'api', 'id', '-u',
    ], { encoding: 'utf8', timeout: 20_000, killSignal: 'SIGKILL' });
    expect(result.status, `${result.error?.message ?? ''}${result.stdout}${result.stderr}`).toBe(0);
    expect(result.stdout.trim()).toMatch(/^\d+$/);
    expect(result.stdout.trim()).not.toBe('0');
  });

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

  it('rejects cross-origin sign-in requests before they can change server state', async () => {
    const response = await request(apiBaseUrl)
      .post('/api/v1/auth/sign-up')
      .set('Origin', 'https://attacker.example')
      .send(credentials())
      .expect(403);
    expect(response.body.error.code).toBe('CSRF_CHECK_FAILED');
  });

  it('production keeps the default rate limits on account routes and other routes', async () => {
    // The test api service raises both limits; production-api keeps 30 and 120 a minute.
    const signIns = [];
    for (let attempt = 0; attempt < 31; attempt += 1) {
      signIns.push((await request(productionApiBaseUrl).post('/api/v1/auth/sign-in').send({})).status);
    }
    expect(signIns.slice(0, 30)).not.toContain(429);
    expect(signIns[30]).toBe(429);
    const reads = [];
    for (let attempt = 0; attempt < 121; attempt += 1) {
      reads.push((await request(productionApiBaseUrl).get('/api/v1/auth/options')).status);
    }
    expect(reads.slice(0, 120)).not.toContain(429);
    expect(reads[120]).toBe(429);
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
