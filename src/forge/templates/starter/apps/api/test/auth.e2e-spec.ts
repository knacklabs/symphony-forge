import { createHash, randomUUID } from 'node:crypto';
import { performance } from 'node:perf_hooks';
import request from 'supertest';
import { describe, expect, it } from 'vitest';
import { apiBaseUrl, credentials, csrfToken, invite, productionApiBaseUrl, psql } from './helpers';

const invalidCredentials = {
  code: 'INVALID_CREDENTIALS',
  message: 'The email or password is incorrect.',
};

function signIn(email: string, password: string) {
  return request(apiBaseUrl).post('/api/v1/auth/sign-in').send({ email, password });
}

function expectInvalidCredentials(response: request.Response): void {
  expect(response.status).toBe(401);
  expect(response.body.error).toMatchObject(invalidCredentials);
}

function tokenFromUrl(value: unknown, linkName: string): string {
  if (typeof value !== 'string') throw new Error(`The API did not return the ${linkName}.`);
  const token = new URL(value).searchParams.get('token');
  if (!token) throw new Error(`The ${linkName} has no token.`);
  return token;
}

function median(samples: number[]): number {
  const middle = [...samples].sort((left, right) => left - right)[Math.floor(samples.length / 2)];
  if (middle === undefined) throw new Error('The sign-in timing samples are empty.');
  return middle;
}

async function failedSignInDuration(email: string, password: string): Promise<number> {
  const startedAt = performance.now();
  const response = await signIn(email, password);
  const duration = performance.now() - startedAt;
  expectInvalidCredentials(response);
  return duration;
}

type ApiClient = ReturnType<typeof request.agent>;

async function createMember(
  adminClient: ApiClient,
  adminCsrf: string,
): Promise<{ email: string; password: string; accountId: string; csrf: string; client: ApiClient }> {
  const member = credentials();
  const token = await invite(adminClient, adminCsrf, member.email);
  const client = request.agent(apiBaseUrl);
  const joined = await client
    .post('/api/v1/auth/accept-invite')
    .send({ ...member, token })
    .expect(201);
  return {
    ...member,
    accountId: joined.body.data.id as string,
    csrf: csrfToken(joined),
    client,
  };
}

// Audit: these live API tests own lockout, account-enumeration timing, and invite/reset link access.
// Existing coverage did not test these paths; missing counters, exposed retry links, expired links,
// or weak reset-link permissions fail here. SQL only shifts expiry on rows created through HTTP.
describe('authentication security', () => {
  it('five failed sign-ins lock the email for 15 minutes', async () => {
    const account = credentials();
    await request(apiBaseUrl).post('/api/v1/auth/sign-up').send(account).expect(201);

    for (let attempt = 0; attempt < 5; attempt += 1) {
      expectInvalidCredentials(await signIn(account.email, 'wrong-password'));
    }
    expectInvalidCredentials(await signIn(account.email, account.password));

    const nearExpiry = psql(`
      UPDATE core."SignInAttempt"
      SET "expiresAtUtc" = "expiresAtUtc" - INTERVAL '14 minutes 30 seconds'
      WHERE "email" = '${account.email.toLowerCase()}'
    `);
    expect(nearExpiry.status).toBe(0);
    expect(nearExpiry.output).toContain('UPDATE 1');
    expectInvalidCredentials(await signIn(account.email, account.password));

    const expired = psql(`
      UPDATE core."SignInAttempt"
      SET "expiresAtUtc" = "expiresAtUtc" - INTERVAL '1 minute'
      WHERE "email" = '${account.email.toLowerCase()}'
    `);
    expect(expired.status).toBe(0);
    expect(expired.output).toContain('UPDATE 1');
    await signIn(account.email, account.password).expect(200);
  });

  it('an unknown email is counted and locked the same way', async () => {
    const account = credentials();
    for (let attempt = 0; attempt < 5; attempt += 1) {
      expectInvalidCredentials(await signIn(account.email, 'wrong-password'));
    }

    await request(apiBaseUrl).post('/api/v1/auth/sign-up').send(account).expect(201);
    expectInvalidCredentials(await signIn(account.email, account.password));
  });

  it('a good sign-in clears the count', async () => {
    const account = credentials();
    await request(apiBaseUrl).post('/api/v1/auth/sign-up').send(account).expect(201);

    for (let attempt = 0; attempt < 4; attempt += 1) {
      expectInvalidCredentials(await signIn(account.email, 'wrong-password'));
    }
    await signIn(account.email, account.password).expect(200);
    expectInvalidCredentials(await signIn(account.email, 'wrong-password'));
    await signIn(account.email, account.password).expect(200);
    for (let attempt = 0; attempt < 5; attempt += 1) {
      expectInvalidCredentials(await signIn(account.email, 'wrong-password'));
    }
    expectInvalidCredentials(await signIn(account.email, account.password));
  });

  it('an unknown email takes about as long to refuse as a wrong password', async () => {
    const account = credentials();
    await request(apiBaseUrl).post('/api/v1/auth/sign-up').send(account).expect(201);
    const unknownEmail = credentials().email;
    const wrongPasswordDurations: number[] = [];
    const unknownEmailDurations: number[] = [];

    for (let attempt = 0; attempt < 3; attempt += 1) {
      wrongPasswordDurations.push(await failedSignInDuration(account.email, 'wrong-password'));
      unknownEmailDurations.push(await failedSignInDuration(unknownEmail, 'wrong-password'));
    }

    expect(median(unknownEmailDurations)).toBeGreaterThanOrEqual(median(wrongPasswordDurations) / 2);
  });

  it('an invite answers its link and the link opens once', async () => {
    const adminClient = request.agent(apiBaseUrl);
    const admin = await adminClient.post('/api/v1/auth/sign-up').send(credentials()).expect(201);
    const invited = credentials();
    const inviteResponse = await adminClient
      .post('/api/v1/invites')
      .set('x-csrf-token', csrfToken(admin))
      .send({ email: invited.email })
      .expect(201);
    const token = tokenFromUrl(inviteResponse.body.data.inviteUrl, 'invite link');
    const memberDetails = { ...invited, token };

    await request(apiBaseUrl).post('/api/v1/auth/accept-invite').send(memberDetails).expect(201);
    await request(apiBaseUrl)
      .post('/api/v1/auth/accept-invite')
      .send(memberDetails)
      .expect(400)
      .expect(({ body }) => expect(body.error.code).toBe('INVITE_INVALID'));
  });

  it('an expired invite link is refused', async () => {
    const adminClient = request.agent(apiBaseUrl);
    const admin = await adminClient.post('/api/v1/auth/sign-up').send(credentials()).expect(201);
    const invited = credentials();
    const inviteResponse = await adminClient
      .post('/api/v1/invites')
      .set('x-csrf-token', csrfToken(admin))
      .send({ email: invited.email })
      .expect(201);
    const token = tokenFromUrl(inviteResponse.body.data.inviteUrl, 'invite link');
    const tokenHash = createHash('sha256').update(token).digest('hex');
    const expiry = psql(
      `UPDATE core."Invite" SET "expiresAtUtc" = NOW() - INTERVAL '1 second' WHERE "tokenHash" = '${tokenHash}'`,
    );
    expect(expiry.status).toBe(0);
    expect(expiry.output).toContain('UPDATE 1');

    await request(apiBaseUrl)
      .post('/api/v1/auth/accept-invite')
      .send({ ...invited, token })
      .expect(400)
      .expect(({ body }) => expect(body.error.code).toBe('INVITE_INVALID'));
  });

  it('an admin makes a reset link that works once', async () => {
    const adminClient = request.agent(apiBaseUrl);
    const admin = await adminClient.post('/api/v1/auth/sign-up').send(credentials()).expect(201);
    const member = await createMember(adminClient, csrfToken(admin));
    const resetKey = randomUUID();
    const sendResetLink = () => adminClient
      .post(`/api/v1/members/${member.accountId}/reset-link`)
      .set('x-csrf-token', csrfToken(admin))
      .set('Idempotency-Key', resetKey);
    const firstResetLink = await sendResetLink().expect(201);
    const replay = await sendResetLink().expect(201);
    expect(replay.body.data).not.toHaveProperty('resetUrl');
    const token = tokenFromUrl(firstResetLink.body.data.resetUrl, 'reset link');
    const newPassword = 'different-correct-horse-password';

    await request(apiBaseUrl).post('/api/v1/auth/reset-password').send({ token, password: newPassword }).expect(200);
    await request(apiBaseUrl)
      .post('/api/v1/auth/reset-password')
      .send({ token, password: member.password })
      .expect(400)
      .expect(({ body }) => expect(body.error.code).toBe('RESET_TOKEN_INVALID'));
    await signIn(member.email, newPassword).expect(200);
  });

  it('an expired reset link is refused', async () => {
    const adminClient = request.agent(apiBaseUrl);
    const admin = await adminClient.post('/api/v1/auth/sign-up').send(credentials()).expect(201);
    const member = await createMember(adminClient, csrfToken(admin));
    const resetLink = await adminClient
      .post(`/api/v1/members/${member.accountId}/reset-link`)
      .set('x-csrf-token', csrfToken(admin))
      .expect(201);
    const token = tokenFromUrl(resetLink.body.data.resetUrl, 'reset link');
    const tokenHash = createHash('sha256').update(token).digest('hex');
    const expiry = psql(
      `UPDATE core."PasswordResetToken" SET "expiresAtUtc" = NOW() - INTERVAL '1 second' WHERE "tokenHash" = '${tokenHash}'`,
    );
    expect(expiry.status).toBe(0);
    expect(expiry.output).toContain('UPDATE 1');

    await request(apiBaseUrl)
      .post('/api/v1/auth/reset-password')
      .send({ token, password: 'different-correct-horse-password' })
      .expect(400)
      .expect(({ body }) => expect(body.error.code).toBe('RESET_TOKEN_INVALID'));
  });

  it('a member cannot make a reset link', async () => {
    const adminClient = request.agent(apiBaseUrl);
    const admin = await adminClient.post('/api/v1/auth/sign-up').send(credentials()).expect(201);
    const member = await createMember(adminClient, csrfToken(admin));

    await member.client
      .post(`/api/v1/members/${member.accountId}/reset-link`)
      .set('x-csrf-token', member.csrf)
      .expect(403)
      .expect(({ body }) => expect(body.error.code).toBe('ADMIN_ONLY'));
  });

  it('an admin cannot make a reset link for another organisation\'s member', async () => {
    const firstClient = request.agent(apiBaseUrl);
    const first = await firstClient.post('/api/v1/auth/sign-up').send(credentials()).expect(201);
    const secondClient = request.agent(apiBaseUrl);
    const second = await secondClient.post('/api/v1/auth/sign-up').send(credentials()).expect(201);

    await secondClient
      .post(`/api/v1/members/${first.body.data.id}/reset-link`)
      .set('x-csrf-token', csrfToken(second))
      .expect(404)
      .expect(({ body }) => expect(body.error.code).toBe('MEMBER_NOT_FOUND'));
  });

  it('production admin can create and use a reset link without a mail provider', async () => {
    const adminClient = request.agent(productionApiBaseUrl);
    const admin = await adminClient.post('/api/v1/auth/sign-up').send(credentials()).expect(201);
    const member = credentials();
    const inviteResponse = await adminClient
      .post('/api/v1/invites')
      .set('Cookie', (admin.get('Set-Cookie') ?? []).map((cookie) => cookie.split(';')[0]).join('; '))
      .set('x-csrf-token', csrfToken(admin))
      .send({ email: member.email })
      .expect(201);
    const inviteToken = tokenFromUrl(inviteResponse.body.data.inviteUrl, 'invite link');
    const memberClient = request.agent(productionApiBaseUrl);
    const joined = await memberClient
      .post('/api/v1/auth/accept-invite')
      .send({ ...member, token: inviteToken })
      .expect(201);
    const resetLink = await adminClient
      .post(`/api/v1/members/${joined.body.data.id}/reset-link`)
      .set('Cookie', (admin.get('Set-Cookie') ?? []).map((cookie) => cookie.split(';')[0]).join('; '))
      .set('x-csrf-token', csrfToken(admin))
      .expect(201);
    const resetToken = tokenFromUrl(resetLink.body.data.resetUrl, 'reset link');
    const newPassword = 'different-correct-horse-password';

    await memberClient
      .post('/api/v1/auth/reset-password')
      .send({ token: resetToken, password: newPassword })
      .expect(200);
    // Both servers share the database. Verify the saved password without consuming
    // the production sign-in quota owned by api.e2e-spec.ts.
    await request(apiBaseUrl)
      .post('/api/v1/auth/sign-in')
      .send({ email: member.email, password: newPassword })
      .expect(200);
  });
});
