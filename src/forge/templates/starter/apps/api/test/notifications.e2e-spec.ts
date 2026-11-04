import { randomUUID } from 'node:crypto';
import request from 'supertest';
import { describe, expect, it } from 'vitest';
import { apiBaseUrl, callNotifications, credentials, csrfToken, invite } from './helpers';

describe('notifications', () => {
  it('a person sees the records that wait for them, with a count', async () => {
    const adminClient = request.agent(apiBaseUrl);
    const adminSignUp = await adminClient.post('/api/v1/auth/sign-up').send(credentials()).expect(201);
    const adminId = adminSignUp.body.data.id as string;
    const adminCsrf = csrfToken(adminSignUp);

    const member = credentials();
    const token = await invite(adminClient, adminCsrf, member.email);
    const memberClient = request.agent(apiBaseUrl);
    const joined = await memberClient
      .post('/api/v1/auth/accept-invite')
      .send({ ...member, token })
      .expect(201);
    const memberId = joined.body.data.id as string;

    const otherCompanyClient = request.agent(apiBaseUrl);
    const otherCompanySignUp = await otherCompanyClient.post('/api/v1/auth/sign-up').send(credentials()).expect(201);
    const otherCompanyId = otherCompanySignUp.body.data.id as string;

    const firstSubjectId = randomUUID();
    const secondSubjectId = randomUUID();
    expect(callNotifications(`
      const membership = await organisations.membershipFor(${JSON.stringify(adminId)});
      if (!membership) throw new Error('The test admin has no company membership.');
      const principal = { id: ${JSON.stringify(adminId)}, organisationId: membership.organisationId };
      await notifications.notify(principal, ${JSON.stringify(memberId)}, ${JSON.stringify(firstSubjectId)}, 'project', 'First waiting record');
      await notifications.notify(principal, ${JSON.stringify(memberId)}, ${JSON.stringify(secondSubjectId)}, 'project', 'Second waiting record');
      return 'created';
    `)).toBe('created');

    const memberList = await memberClient.get('/api/v1/notifications').expect(200);
    expect(memberList.body.data.count).toBe(2);
    expect(memberList.body.data.items).toEqual([
      expect.objectContaining({ subjectId: secondSubjectId, subjectName: 'project', message: 'Second waiting record' }),
      expect.objectContaining({ subjectId: firstSubjectId, subjectName: 'project', message: 'First waiting record' }),
    ]);
    expect(memberList.body.data.items[0].createdAtUtc).toEqual(expect.any(String));
    expect((await adminClient.get('/api/v1/notifications').expect(200)).body.data.count).toBe(0);
    expect((await otherCompanyClient.get('/api/v1/notifications').expect(200)).body.data.count).toBe(0);
    await request(apiBaseUrl).get('/api/v1/notifications').expect(401);

    expect(callNotifications(`
      const membership = await organisations.membershipFor(${JSON.stringify(otherCompanyId)});
      if (!membership) throw new Error('The other test company has no membership.');
      await notifications.resolve(
        { id: ${JSON.stringify(otherCompanyId)}, organisationId: membership.organisationId },
        ${JSON.stringify(secondSubjectId)},
      );
      return 'resolved';
    `)).toBe('resolved');
    expect((await memberClient.get('/api/v1/notifications').expect(200)).body.data.count).toBe(2);

    expect(callNotifications(`
      const membership = await organisations.membershipFor(${JSON.stringify(adminId)});
      if (!membership) throw new Error('The test admin has no company membership.');
      await notifications.resolve(
        { id: ${JSON.stringify(adminId)}, organisationId: membership.organisationId },
        ${JSON.stringify(firstSubjectId)},
      );
      return 'resolved';
    `)).toBe('resolved');
    const afterResolve = await memberClient.get('/api/v1/notifications').expect(200);
    expect(afterResolve.body.data.count).toBe(1);
    expect(afterResolve.body.data.items).toEqual([
      expect.objectContaining({ subjectId: secondSubjectId, message: 'Second waiting record' }),
    ]);

    const rolledBackSubjectId = randomUUID();
    expect(callNotifications(`
      const membership = await organisations.membershipFor(${JSON.stringify(adminId)});
      if (!membership) throw new Error('The test admin has no company membership.');
      const principal = { id: ${JSON.stringify(adminId)}, organisationId: membership.organisationId };
      try {
        await prisma.$transaction(async (tx) => {
          await notifications.notify(
            principal, ${JSON.stringify(memberId)}, ${JSON.stringify(rolledBackSubjectId)}, 'project', 'Rolled-back record', tx,
          );
          await notifications.resolve(principal, ${JSON.stringify(secondSubjectId)}, tx);
          throw new Error('roll back notification changes');
        });
        throw new Error('The notification transaction did not fail.');
      } catch (error) {
        if (!(error instanceof Error) || error.message !== 'roll back notification changes') throw error;
      }
      return 'rolled back';
    `)).toBe('rolled back');
    const afterRollback = await memberClient.get('/api/v1/notifications').expect(200);
    expect(afterRollback.body.data.count).toBe(1);
    expect(afterRollback.body.data.items).toEqual([
      expect.objectContaining({ subjectId: secondSubjectId, message: 'Second waiting record' }),
    ]);

    const additionalSubjectIds = Array.from({ length: 100 }, () => randomUUID());
    expect(callNotifications(`
      const membership = await organisations.membershipFor(${JSON.stringify(adminId)});
      if (!membership) throw new Error('The test admin has no company membership.');
      const principal = { id: ${JSON.stringify(adminId)}, organisationId: membership.organisationId };
      await prisma.$transaction(async (tx) => {
        for (const subjectId of ${JSON.stringify(additionalSubjectIds)}) {
          await notifications.notify(
            principal, ${JSON.stringify(memberId)}, subjectId, 'project', 'Additional waiting record', tx,
          );
        }
      });
      return 'added';
    `)).toBe('added');
    const cappedList = await memberClient.get('/api/v1/notifications').expect(200);
    expect(cappedList.body.data.count).toBe(101);
    expect(cappedList.body.data.items).toHaveLength(100);
  });
});
