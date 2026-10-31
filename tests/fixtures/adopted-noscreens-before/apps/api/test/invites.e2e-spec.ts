import { createHash, randomUUID } from 'node:crypto';
import request from 'supertest';
import { describe, expect, it } from 'vitest';
import { apiBaseUrl, credentials, csrfToken, invite, logEvents, productionApiBaseUrl, psql } from './helpers';

describe('organisation invites and roles', () => {
  it('an admin invites a person by email who joins the organisation', async () => {
    const admin = credentials();
    const invited = credentials();
    const adminClient = request.agent(apiBaseUrl);
    const signUp = await adminClient.post('/api/v1/auth/sign-up').send(admin).expect(201);
    const csrf = csrfToken(signUp);

    await adminClient
      .post('/api/v1/projects')
      .set('x-csrf-token', csrf)
      .send({ name: 'Shared project', status: 'active' })
      .expect(201);

    const token = await invite(adminClient, csrf, invited.email);
    await adminClient
      .post('/api/v1/invites')
      .set('x-csrf-token', csrf)
      .send({ email: 'not-an-email' })
      .expect(400)
      .expect(({ body }) => expect(body.error.details.fieldErrors).toEqual(
        expect.arrayContaining([expect.objectContaining({ field: 'email' })]),
      ));
    const memberClient = request.agent(apiBaseUrl);
    const joined = await memberClient
      .post('/api/v1/auth/accept-invite')
      .send({ email: invited.email, password: invited.password, token })
      .expect(201);
    expect(joined.body.data).toMatchObject({ email: invited.email, role: 'member' });

    const memberCsrf = csrfToken(joined);
    // A member may view, create and edit projects, but not delete or restore them.
    const permissions = (await memberClient.get('/api/v1/auth/me').expect(200)).body.data.permissions as string[];
    expect(permissions).not.toContain('projects.delete');
    const members = await memberClient.get('/api/v1/members?page=1&limit=20').expect(200);
    expect(members.body.data.items).toEqual(expect.arrayContaining([
      expect.objectContaining({ email: admin.email, role: 'admin' }),
      expect.objectContaining({ email: invited.email, role: 'member' }),
    ]));

    const memberProject = await memberClient
      .post('/api/v1/projects')
      .set('x-csrf-token', memberCsrf)
      .send({ name: 'Member project', status: 'active' })
      .expect(201);
    await memberClient
      .put(`/api/v1/projects/${memberProject.body.data.id}`)
      .set('x-csrf-token', memberCsrf)
      .send({ name: 'Updated member project', status: 'archived' })
      .expect(200);
    await memberClient
      .delete(`/api/v1/projects/${memberProject.body.data.id}`)
      .set('x-csrf-token', memberCsrf)
      .expect(403)
      .expect(({ body }) => expect(body.error.code).toBe('PERMISSION_DENIED'));

    const projects = await memberClient.get('/api/v1/projects?limit=20').expect(200);
    expect(projects.body.data.items).toEqual(expect.arrayContaining([
      expect.objectContaining({ name: 'Shared project' }),
      expect.objectContaining({ name: 'Updated member project' }),
    ]));
  });

  it('an invite sent again with the same Idempotency-Key sends one email and makes one invitation', async () => {
    const adminClient = request.agent(apiBaseUrl);
    const signUp = await adminClient.post('/api/v1/auth/sign-up').send(credentials()).expect(201);
    const csrf = csrfToken(signUp);
    const invited = credentials();
    const previousLogCount = logEvents('api').length;
    const sendInvite = (email: string, idempotencyKey: string) => adminClient.post('/api/v1/invites')
      .set('x-csrf-token', csrf)
      .set('Idempotency-Key', idempotencyKey)
      .send({ email });

    const key = randomUUID();
    const first = await sendInvite(invited.email, key).expect(201);
    const replay = await sendInvite(invited.email, key).expect(201);
    expect(replay.body).toEqual(first.body);

    const inviteEvents = (from: number) => logEvents('api').slice(from)
      .filter(({ context }) => typeof context?.inviteUrl === 'string');
    const firstLinks = inviteEvents(previousLogCount);
    expect(firstLinks).toHaveLength(1);
    const firstToken = new URL(String(firstLinks[0].context?.inviteUrl)).searchParams.get('token');
    if (!firstToken) throw new Error('The API did not log a test invite token.');

    const accountId = signUp.body.data.id as string;
    const storedInvite = psql(`
      SELECT COUNT(*) FROM core."Invite"
      WHERE "organisationId" = (
        SELECT "organisationId" FROM core."Membership" WHERE "accountId" = '${accountId}'
      ) AND "email" = '${invited.email}'
    `);
    expect(storedInvite.status).toBe(0);
    expect(storedInvite.output).toMatch(/\n\s*1\s*\n/);

    await request(apiBaseUrl)
      .post('/api/v1/auth/accept-invite')
      .send({ email: invited.email, password: invited.password, token: firstToken })
      .expect(201);

    const reInvited = credentials();
    const reInviteLogCount = logEvents('api').length;
    await sendInvite(reInvited.email, randomUUID()).expect(201);
    await sendInvite(reInvited.email, randomUUID()).expect(201);
    const replacementLinks = inviteEvents(reInviteLogCount);
    expect(replacementLinks).toHaveLength(2);
    const replacementToken = new URL(String(replacementLinks[1].context?.inviteUrl)).searchParams.get('token');
    if (!replacementToken) throw new Error('The API did not log a test invite token.');

    const currentInviteCount = psql(`
      SELECT COUNT(*) FROM core."Invite"
      WHERE "organisationId" = (
        SELECT "organisationId" FROM core."Membership" WHERE "accountId" = '${accountId}'
      ) AND "email" = '${reInvited.email}'
    `);
    expect(currentInviteCount.status).toBe(0);
    expect(currentInviteCount.output).toMatch(/\n\s*1\s*\n/);

    await request(apiBaseUrl)
      .post('/api/v1/auth/accept-invite')
      .send({ email: reInvited.email, password: reInvited.password, token: replacementToken })
      .expect(201);
  });

  it('a member cannot invite people or change roles', async () => {
    const adminClient = request.agent(apiBaseUrl);
    const adminSignUp = await adminClient.post('/api/v1/auth/sign-up').send(credentials()).expect(201);
    const invited = credentials();
    const token = await invite(adminClient, csrfToken(adminSignUp), invited.email);

    const memberClient = request.agent(apiBaseUrl);
    const joined = await memberClient
      .post('/api/v1/auth/accept-invite')
      .send({ email: invited.email, password: invited.password, token })
      .expect(201);
    const csrf = csrfToken(joined);

    await memberClient
      .post('/api/v1/invites')
      .set('x-csrf-token', csrf)
      .send({ email: credentials().email })
      .expect(403)
      .expect(({ body }) => expect(body.error.code).toBe('ADMIN_ONLY'));
    await memberClient
      .patch(`/api/v1/members/${joined.body.data.id}`)
      .set('x-csrf-token', csrf)
      .send({ role: 'admin' })
      .expect(403)
      .expect(({ body }) => expect(body.error.code).toBe('ADMIN_ONLY'));
  });

  it('an admin changes another member\'s role but not their own', async () => {
    const adminClient = request.agent(apiBaseUrl);
    const admin = credentials();
    const adminSignUp = await adminClient.post('/api/v1/auth/sign-up').send(admin).expect(201);
    const adminCsrf = csrfToken(adminSignUp);
    const invited = credentials();
    const token = await invite(adminClient, adminCsrf, invited.email);
    const memberClient = request.agent(apiBaseUrl);
    const joined = await memberClient
      .post('/api/v1/auth/accept-invite')
      .send({ email: invited.email, password: invited.password, token })
      .expect(201);

    await adminClient
      .patch(`/api/v1/members/${joined.body.data.id}`)
      .set('x-csrf-token', adminCsrf)
      .send({ role: 'admin' })
      .expect(200);
    await adminClient
      .patch(`/api/v1/members/${adminSignUp.body.data.id}`)
      .set('x-csrf-token', adminCsrf)
      .send({ role: 'member' })
      .expect(403)
      .expect(({ body }) => expect(body.error.code).toBe('CANNOT_CHANGE_OWN_ROLE'));

    const members = await adminClient.get('/api/v1/members?page=1&limit=20').expect(200);
    expect(members.body.data.items).toEqual(expect.arrayContaining([
      expect.objectContaining({ accountId: adminSignUp.body.data.id, role: 'admin' }),
      expect.objectContaining({ accountId: joined.body.data.id, role: 'admin' }),
    ]));
  });

  it('an admin cannot change the role of another organisation\'s account', async () => {
    const firstClient = request.agent(apiBaseUrl);
    const first = await firstClient.post('/api/v1/auth/sign-up').send(credentials()).expect(201);
    const secondClient = request.agent(apiBaseUrl);
    const second = await secondClient.post('/api/v1/auth/sign-up').send(credentials()).expect(201);

    await secondClient
      .patch(`/api/v1/members/${first.body.data.id}`)
      .set('x-csrf-token', csrfToken(second))
      .send({ role: 'member' })
      .expect(404)
      .expect(({ body }) => expect(body.error.code).toBe('MEMBER_NOT_FOUND'));

    const members = await firstClient.get('/api/v1/members?page=1&limit=20').expect(200);
    expect(members.body.data.items).toEqual([expect.objectContaining({ accountId: first.body.data.id, role: 'admin' })]);
  });

  it('an invite link works once and only for its email', async () => {
    const adminClient = request.agent(apiBaseUrl);
    const signUp = await adminClient.post('/api/v1/auth/sign-up').send(credentials()).expect(201);
    const invited = credentials();
    const token = await invite(adminClient, csrfToken(signUp), invited.email);
    const csrf = csrfToken(signUp);
    const wrongEmail = credentials();

    await request(apiBaseUrl)
      .post('/api/v1/auth/accept-invite')
      .send({ email: wrongEmail.email, password: wrongEmail.password, token })
      .expect(400)
      .expect(({ body }) => expect(body.error.code).toBe('INVITE_INVALID'));

    const replacementToken = await invite(adminClient, csrf, invited.email);
    await request(apiBaseUrl)
      .post('/api/v1/auth/accept-invite')
      .send({ email: invited.email, password: invited.password, token })
      .expect(400)
      .expect(({ body }) => expect(body.error.code).toBe('INVITE_INVALID'));

    await request(apiBaseUrl)
      .post('/api/v1/auth/accept-invite')
      .send({ email: invited.email, password: invited.password, token: replacementToken })
      .expect(201);

    await request(apiBaseUrl)
      .post('/api/v1/auth/accept-invite')
      .send({ email: invited.email, password: invited.password, token: replacementToken })
      .expect(400)
      .expect(({ body }) => expect(body.error.code).toBe('INVITE_INVALID'));

    const existing = credentials();
    await request(apiBaseUrl).post('/api/v1/auth/sign-up').send(existing).expect(201);
    await adminClient
      .post('/api/v1/invites')
      .set('x-csrf-token', csrf)
      .send({ email: existing.email })
      .expect(409)
      .expect(({ body }) => expect(body.error.code).toBe('EMAIL_ALREADY_REGISTERED'));

    const signsUpBeforeAccept = credentials();
    const conflictToken = await invite(adminClient, csrf, signsUpBeforeAccept.email);
    await request(apiBaseUrl).post('/api/v1/auth/sign-up').send(signsUpBeforeAccept).expect(201);
    await request(apiBaseUrl)
      .post('/api/v1/auth/accept-invite')
      .send({ email: signsUpBeforeAccept.email, password: signsUpBeforeAccept.password, token: conflictToken })
      .expect(409)
      .expect(({ body }) => expect(body.error).toMatchObject({
        code: 'EMAIL_ALREADY_REGISTERED',
        message: 'An account already uses that email, so it cannot join this organisation.',
      }));

    const expired = credentials();
    const expiredToken = await invite(adminClient, csrf, expired.email);
    const expiredTokenHash = createHash('sha256').update(expiredToken).digest('hex');
    const expiry = psql(
      `UPDATE core."Invite" SET "expiresAtUtc" = NOW() - INTERVAL '1 second' WHERE "tokenHash" = '${expiredTokenHash}'`,
    );
    expect(expiry.status).toBe(0);
    expect(expiry.output).toContain('UPDATE 1');
    await request(apiBaseUrl)
      .post('/api/v1/auth/accept-invite')
      .send({ email: expired.email, password: expired.password, token: expiredToken })
      .expect(400)
      .expect(({ body }) => expect(body.error.code).toBe('INVITE_INVALID'));
  });

  it('production refuses an invite without a mail provider', async () => {
    const client = request.agent(productionApiBaseUrl);
    const signUp = await client.post('/api/v1/auth/sign-up').send(credentials()).expect(201);

    await client
      .post('/api/v1/invites')
      .set('Cookie', (signUp.get('Set-Cookie') ?? []).map((cookie) => cookie.split(';')[0]).join('; '))
      .set('x-csrf-token', csrfToken(signUp))
      .send({ email: credentials().email })
      .expect(422)
      .expect(({ body }) => expect(body.error).toMatchObject({
        code: 'MAIL_NOT_CONFIGURED',
        message: 'Email is not set up for this app yet.',
      }));
  });
});
