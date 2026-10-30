import request from 'supertest';
import { describe, expect, it } from 'vitest';
import { apiBaseUrl, credentials, csrfToken, invite, logEvents } from './helpers';

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
    expect(otherProjects.body.data.paging.total).toBe(0);
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

  it('an admin removes a member, who is signed out at once', async () => {
    // Audit:
    // 1. Protects the member-removal HTTP contract, including its effects on sessions, reset tokens, invites, history and agent keys.
    // 2. It fails if removal is missing or leaves a membership, session, reset token, sent invite or agent key usable.
    // 3. No current API case removes a member or covers these effects, and a UI cannot cover every request boundary.
    // 4. This test uses the running API, database, and test mail log, with no production test seam.
    const admin = credentials();
    const invited = credentials();
    const adminClient = request.agent(apiBaseUrl);
    const signUp = await adminClient.post('/api/v1/auth/sign-up').send(admin).expect(201);
    const adminCsrf = csrfToken(signUp);
    const adminId = signUp.body.data.id as string;
    const token = await invite(adminClient, adminCsrf, invited.email);

    const memberClient = request.agent(apiBaseUrl);
    const joined = await memberClient
      .post('/api/v1/auth/accept-invite')
      .send({ ...invited, token })
      .expect(201);
    const memberId = joined.body.data.id as string;
    const memberCsrf = csrfToken(joined);
    const secondMemberClient = request.agent(apiBaseUrl);
    await secondMemberClient.post('/api/v1/auth/sign-in').send(invited).expect(200);

    await memberClient
      .delete(`/api/v1/members/${adminId}`)
      .set('x-csrf-token', memberCsrf)
      .expect(403)
      .expect(({ body }) => expect(body.error.code).toBe('ADMIN_ONLY'));

    await adminClient
      .delete(`/api/v1/members/${adminId}`)
      .set('x-csrf-token', adminCsrf)
      .expect(403)
      .expect(({ body }) => expect(body.error.code).toBe('CANNOT_REMOVE_SELF'));

    await adminClient
      .patch(`/api/v1/members/${memberId}`)
      .set('x-csrf-token', adminCsrf)
      .send({ role: 'admin' })
      .expect(200);

    const sentInvitee = credentials();
    const sentInviteToken = await invite(memberClient, memberCsrf, sentInvitee.email);
    const resetLogCount = logEvents('api').length;
    await request(apiBaseUrl)
      .post('/api/v1/auth/forgot-password')
      .send({ email: invited.email })
      .expect(200);
    const resetEvent = logEvents('api').slice(resetLogCount).reverse()
      .find(({ context }) => typeof context?.resetUrl === 'string');
    if (!resetEvent) throw new Error('The API did not log a test reset link.');
    const resetToken = new URL(String(resetEvent.context?.resetUrl)).searchParams.get('token');
    if (!resetToken) throw new Error('The reset link has no token.');

    const otherClient = request.agent(apiBaseUrl);
    const otherSignUp = await otherClient.post('/api/v1/auth/sign-up').send(credentials()).expect(201);
    const otherMemberId = otherSignUp.body.data.id as string;

    await adminClient
      .delete(`/api/v1/members/${otherMemberId}`)
      .set('x-csrf-token', adminCsrf)
      .expect(404)
      .expect(({ body }) => expect(body.error.code).toBe('MEMBER_NOT_FOUND'));

    await adminClient
      .delete(`/api/v1/members/${memberId}`)
      .set('x-csrf-token', adminCsrf)
      .expect(200);

    await memberClient.get('/api/v1/auth/me').expect(401);
    await secondMemberClient.get('/api/v1/auth/me').expect(401);
    await request(apiBaseUrl).post('/api/v1/auth/sign-in').send(invited).expect(401);
    await request(apiBaseUrl)
      .post('/api/v1/auth/reset-password')
      .send({ token: resetToken, password: 'different-correct-horse-password' })
      .expect(400)
      .expect(({ body }) => expect(body.error.code).toBe('RESET_TOKEN_INVALID'));

    const members = await adminClient.get('/api/v1/members?page=1&limit=20').expect(200);
    expect(members.body.data.items.map((member: { email: string }) => member.email)).not.toContain(invited.email);
    const membersExport = await adminClient.get('/api/v1/members/export').expect(200);
    expect(membersExport.text).not.toContain(invited.email);

    await request(apiBaseUrl)
      .post('/api/v1/auth/accept-invite')
      .send({ ...sentInvitee, token: sentInviteToken })
      .expect(400)
      .expect(({ body }) => expect(body.error.code).toBe('INVITE_INVALID'));
    await adminClient
      .post('/api/v1/invites')
      .set('x-csrf-token', adminCsrf)
      .send({ email: invited.email })
      .expect(409)
      .expect(({ body }) => expect(body.error).toMatchObject({
        code: 'EMAIL_ALREADY_REGISTERED',
        message: 'That person already has an account.',
      }));

    const history = await adminClient.get('/api/v1/history').expect(200);
    expect(history.body.data).toEqual(expect.arrayContaining([
      expect.objectContaining({ actorEmail: admin.email, summary: `Removed ${invited.email}` }),
    ]));
    await adminClient
      .delete(`/api/v1/members/${memberId}`)
      .set('x-csrf-token', adminCsrf)
      .expect(404)
      .expect(({ body }) => expect(body.error.code).toBe('MEMBER_NOT_FOUND'));

    const agent = (await adminClient
      .post('/api/v1/agents')
      .set('x-csrf-token', adminCsrf)
      .send({ name: 'removed-agent', role: 'member' })
      .expect(201)).body.data;
    const agentKey = (await adminClient
      .post(`/api/v1/members/${agent.accountId}/key`)
      .set('x-csrf-token', adminCsrf)
      .expect(201)).body.data.key as string;
    const initializeRequest = {
      jsonrpc: '2.0',
      id: 1,
      method: 'initialize',
      params: {
        protocolVersion: '2025-06-18',
        capabilities: {},
        clientInfo: { name: 'starter-e2e', version: '1.0.0' },
      },
    };
    const initializeAgent = () => request(apiBaseUrl)
      .post('/mcp')
      .set('Accept', 'application/json, text/event-stream')
      .set('Content-Type', 'application/json')
      .set('Authorization', `Bearer ${agentKey}`)
      .send(initializeRequest);
    await initializeAgent().expect(200);
    await adminClient
      .delete(`/api/v1/members/${agent.accountId}`)
      .set('x-csrf-token', adminCsrf)
      .expect(200);
    await initializeAgent()
      .expect(401)
      .expect(({ body }) => expect(body.error.code).toBe('UNAUTHENTICATED'));
  });
});
