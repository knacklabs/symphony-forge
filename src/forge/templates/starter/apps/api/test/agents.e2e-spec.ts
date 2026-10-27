import request from 'supertest';
import { describe, expect, it } from 'vitest';
import { apiBaseUrl, credentials, csrfToken, invite } from './helpers';

async function signedUpAdmin() {
  const admin = credentials();
  const client = request.agent(apiBaseUrl);
  const signUp = await client.post('/api/v1/auth/sign-up').send(admin).expect(201);
  return { admin, client, csrf: csrfToken(signUp) };
}

describe('agent accounts', () => {
  it('an admin adds an agent account and creates and revokes its key', async () => {
    const { admin, client, csrf } = await signedUpAdmin();
    const added = await client.post('/api/v1/agents').set('x-csrf-token', csrf).send({ name: 'gantry', role: 'member' }).expect(201);
    const agent = added.body.data;
    expect(agent).toMatchObject({ role: 'member', isAgent: true, hasKey: false });
    expect(agent.email).toMatch(/^gantry-[a-z0-9]{6}@agents\.invalid$/);
    await client.post('/api/v1/agents').set('x-csrf-token', csrf).send({ name: 'Not valid', role: 'member' }).expect(400)
      .expect(({ body }) => expect(body.error.details.fieldErrors).toEqual([expect.objectContaining({ field: 'name' })]));

    const first = await client.post(`/api/v1/members/${agent.accountId}/key`).set('x-csrf-token', csrf).expect(201);
    expect(first.body.data.key).toMatch(/^agent_[A-Za-z0-9_-]{43}$/);
    const second = await client.post(`/api/v1/members/${agent.accountId}/key`).set('x-csrf-token', csrf).expect(201);
    expect(second.body.data.key).toMatch(/^agent_/);
    expect(second.body.data.key).not.toBe(first.body.data.key);

    const listed = await client.get('/api/v1/members?page=1&limit=20').expect(200);
    expect(listed.body.data.items).toEqual(expect.arrayContaining([
      expect.objectContaining({ email: admin.email, isAgent: false, hasKey: false }),
      expect.objectContaining({ email: agent.email, isAgent: true, hasKey: true }),
    ]));
    // The key shows one time only: no list or member read returns it.
    expect(JSON.stringify(listed.body)).not.toContain(second.body.data.key);

    await client.delete(`/api/v1/members/${agent.accountId}/key`).set('x-csrf-token', csrf).expect(200);
    const revoked = await client.get('/api/v1/members?page=1&limit=20').expect(200);
    expect(revoked.body.data.items).toEqual(expect.arrayContaining([expect.objectContaining({ email: agent.email, hasKey: false })]));

    // A person's membership has no key to create.
    const self = listed.body.data.items.find((member: { email: string }) => member.email === admin.email);
    await client.post(`/api/v1/members/${self.accountId}/key`).set('x-csrf-token', csrf).expect(404)
      .expect(({ body }) => expect(body.error.code).toBe('MEMBER_NOT_FOUND'));

    const history = await client.get('/api/v1/history').expect(200);
    expect(history.body.data.map((entry: { actorEmail: string; summary: string }) => [entry.actorEmail, entry.summary])).toEqual([
      [admin.email, `Revoked the key for ${agent.email}`],
      [admin.email, `Created a key for ${agent.email}`],
      [admin.email, `Created a key for ${agent.email}`],
      [admin.email, `Added the agent account ${agent.email} as Member`],
    ]);

    // The agent access list starts empty, and a change to it adds one history row.
    await client.get('/api/v1/agent-tools').expect(200).expect(({ body }) => expect(body.data).toEqual({ deleteAndRestore: [] }));
    await client.put('/api/v1/agent-tools/projects').set('x-csrf-token', csrf).send({ deleteAndRestore: true }).expect(200)
      .expect(({ body }) => expect(body.data).toEqual({ deleteAndRestore: ['projects'] }));
    await client.put('/api/v1/agent-tools/Not%20a%20feature').set('x-csrf-token', csrf).send({ deleteAndRestore: true }).expect(400);
    const changed = await client.get('/api/v1/history').expect(200);
    expect(changed.body.data[0]).toMatchObject({ actorEmail: admin.email, summary: 'Turned on agent delete and restore for projects' });
  });

  it('a member cannot add an agent account or change its key or agent access', async () => {
    const { client, csrf } = await signedUpAdmin();
    const agent = (await client.post('/api/v1/agents').set('x-csrf-token', csrf).send({ name: 'reports-bot', role: 'admin' }).expect(201)).body.data;
    const invited = credentials();
    const token = await invite(client, csrf, invited.email);
    const member = request.agent(apiBaseUrl);
    const memberCsrf = csrfToken(await member.post('/api/v1/auth/accept-invite').send({ ...invited, token }).expect(201));

    for (const call of [
      member.post('/api/v1/agents').set('x-csrf-token', memberCsrf).send({ name: 'sneaky', role: 'admin' }),
      member.post(`/api/v1/members/${agent.accountId}/key`).set('x-csrf-token', memberCsrf),
      member.delete(`/api/v1/members/${agent.accountId}/key`).set('x-csrf-token', memberCsrf),
      member.get('/api/v1/agent-tools'),
      member.put('/api/v1/agent-tools/projects').set('x-csrf-token', memberCsrf).send({ deleteAndRestore: true }),
    ]) {
      await call.expect(403).expect(({ body }) => expect(body.error.code).toBe('ADMIN_ONLY'));
    }

    // Another organisation's admin cannot reach this agent.
    const other = await signedUpAdmin();
    await other.client.post(`/api/v1/members/${agent.accountId}/key`).set('x-csrf-token', other.csrf).expect(404)
      .expect(({ body }) => expect(body.error.code).toBe('MEMBER_NOT_FOUND'));
    await other.client.delete(`/api/v1/members/${agent.accountId}/key`).set('x-csrf-token', other.csrf).expect(404);
  });

  it('an agent account cannot sign in with a password', async () => {
    const { client, csrf } = await signedUpAdmin();
    const agent = (await client.post('/api/v1/agents').set('x-csrf-token', csrf).send({ name: 'gantry', role: 'admin' }).expect(201)).body.data;
    await client.post(`/api/v1/members/${agent.accountId}/key`).set('x-csrf-token', csrf).expect(201);
    for (const password of ['correct-horse-battery-staple', 'x'.repeat(12)]) {
      await request(apiBaseUrl).post('/api/v1/auth/sign-in').send({ email: agent.email, password }).expect(401)
        .expect(({ body }) => expect(body.error.code).toBe('INVALID_CREDENTIALS'));
    }
  });
});
