import request from 'supertest';
import { describe, expect, it } from 'vitest';
import { apiBaseUrl, credentials, csrfToken, invite } from './helpers';

describe('change history', () => {
  it('an invite and a role change write change history', async () => {
    const admin = credentials();
    const invited = credentials();
    const adminClient = request.agent(apiBaseUrl);
    const signUp = await adminClient.post('/api/v1/auth/sign-up').send(admin).expect(201);
    const csrf = csrfToken(signUp);
    const token = await invite(adminClient, csrf, invited.email);

    const memberClient = request.agent(apiBaseUrl);
    const joined = await memberClient
      .post('/api/v1/auth/accept-invite')
      .send({ email: invited.email, password: invited.password, token })
      .expect(201);

    await memberClient
      .get('/api/v1/history')
      .expect(403)
      .expect(({ body }) => expect(body.error.code).toBe('ADMIN_ONLY'));
    await memberClient
      .get('/api/v1/history/export')
      .expect(403)
      .expect(({ body }) => expect(body.error.code).toBe('ADMIN_ONLY'));

    await adminClient
      .patch(`/api/v1/members/${joined.body.data.id}`)
      .set('x-csrf-token', csrf)
      .send({ role: 'admin' })
      .expect(200);

    const history = await adminClient.get('/api/v1/history').expect(200);
    expect(history.body.data).toHaveLength(2);
    expect(history.body.data).toEqual([
      expect.objectContaining({
        actorEmail: admin.email,
        summary: `Changed ${invited.email} from member to admin`,
        createdAtUtc: expect.any(String),
      }),
      expect.objectContaining({
        actorEmail: admin.email,
        summary: `Invited ${invited.email}`,
        createdAtUtc: expect.any(String),
      }),
    ]);
    expect(Date.parse(history.body.data[0].createdAtUtc))
      .toBeGreaterThanOrEqual(Date.parse(history.body.data[1].createdAtUtc));
    for (const entry of history.body.data) {
      expect(Object.keys(entry).sort()).toEqual(['actorEmail', 'createdAtUtc', 'id', 'summary']);
      expect(entry.id).toEqual(expect.any(String));
    }

    const otherClient = request.agent(apiBaseUrl);
    await otherClient.post('/api/v1/auth/sign-up').send(credentials()).expect(201);
    await otherClient.get('/api/v1/history').expect(200).expect(({ body }) => {
      expect(body.data).toEqual([]);
    });
    expect((await otherClient.get('/api/v1/history/export').expect(200)).text)
      .toBe('When (UTC),Who,What\r\n');

    await request(apiBaseUrl).get('/api/v1/history').expect(401);
    await request(apiBaseUrl).get('/api/v1/history/export').expect(401);
  });
});
