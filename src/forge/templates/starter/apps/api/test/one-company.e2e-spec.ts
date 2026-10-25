import { spawnSync } from 'node:child_process';
import request from 'supertest';
import { describe, expect, it } from 'vitest';
import { apiBaseUrl, credentials, csrfToken, invite, psql } from './helpers';

const oneCompanyApiBaseUrl = process.env.ONE_COMPANY_API_TEST_URL ?? 'http://127.0.0.1:3002';

function setupCompany(email: string, password: string): { status: number; output: string } {
  const result = spawnSync('docker', [
    'compose', '-f', 'compose.test.yml', 'exec', '-T',
    '-e', `ADMIN_EMAIL=${email}`, '-e', `ADMIN_PASSWORD=${password}`,
    'one-company-api', 'corepack', 'pnpm', 'run', 'setup:company',
  ], { encoding: 'utf8' });
  return { status: result.status ?? 1, output: `${result.stdout}${result.stderr}` };
}

describe('one-company API', () => {
  it('the setup command makes the company and its first admin', async () => {
    const admin = credentials();
    const setup = setupCompany(admin.email, admin.password);
    expect(setup.status, setup.output).toBe(0);

    const client = request.agent(oneCompanyApiBaseUrl);
    const signIn = await client.post('/api/v1/auth/sign-in').send(admin).expect(200);
    expect(signIn.body.data).toMatchObject({ email: admin.email, role: 'admin' });

    const members = await client.get('/api/v1/members?page=1&limit=20').expect(200);
    expect(members.body.data.items).toEqual([
      expect.objectContaining({ email: admin.email, role: 'admin' }),
    ]);

    const duplicate = setupCompany(admin.email, admin.password);
    expect(duplicate.status).toBe(1);
    expect(duplicate.output).toContain('An account already uses that email.');

    const invalid = setupCompany('not-an-email', admin.password);
    expect(invalid.status).toBe(1);
    expect(invalid.output).toContain('Invalid email address');
    const invalidSignIn = await request(oneCompanyApiBaseUrl)
      .post('/api/v1/auth/sign-in')
      .send({ email: 'not-an-email', password: admin.password });
    expect([400, 401]).toContain(invalidSignIn.status);

    const account = psql(
      `SELECT CASE WHEN EXISTS (SELECT 1 FROM "Account" WHERE email = 'not-an-email') THEN 'found' ELSE 'missing' END`,
    );
    expect(account.status).toBe(0);
    expect(account.output).toContain('missing');
  });

  it('a one-company app refuses sign-up and still takes invites', async () => {
    const admin = credentials();
    const setup = setupCompany(admin.email, admin.password);
    expect(setup.status, setup.output).toBe(0);

    const options = await request(oneCompanyApiBaseUrl).get('/api/v1/auth/options').expect(200);
    expect(options.body.data.signUpOpen).toBe(false);

    const wouldBeAccount = credentials();
    const refused = await request(oneCompanyApiBaseUrl)
      .post('/api/v1/auth/sign-up')
      .send(wouldBeAccount)
      .expect(403);
    expect(refused.body.error).toMatchObject({
      code: 'SIGN_UP_CLOSED',
      message: 'This app is for one company. Ask an admin of your team for an invite.',
    });
    await request(oneCompanyApiBaseUrl).post('/api/v1/auth/sign-in').send(wouldBeAccount).expect(401);

    const adminClient = request.agent(oneCompanyApiBaseUrl);
    const signedIn = await adminClient.post('/api/v1/auth/sign-in').send(admin).expect(200);
    const csrf = csrfToken(signedIn);
    await adminClient
      .post('/api/v1/projects')
      .set('x-csrf-token', csrf)
      .send({ name: 'Company project', status: 'active' })
      .expect(201);

    const member = credentials();
    const token = await invite(adminClient, csrf, member.email, 'one-company-api');
    const memberClient = request.agent(oneCompanyApiBaseUrl);
    const joined = await memberClient
      .post('/api/v1/auth/accept-invite')
      .send({ email: member.email, password: member.password, token })
      .expect(201);
    expect(joined.body.data).toMatchObject({ email: member.email, role: 'member' });

    const projects = await memberClient.get('/api/v1/projects?page=1&limit=20').expect(200);
    expect(projects.body.data.items).toEqual([
      expect.objectContaining({ name: 'Company project' }),
    ]);
  });

  it('a one-company app becomes many-company by its setting alone', async () => {
    const admin = credentials();
    const setup = setupCompany(admin.email, admin.password);
    expect(setup.status, setup.output).toBe(0);

    const adminClient = request.agent(oneCompanyApiBaseUrl);
    const signedIn = await adminClient.post('/api/v1/auth/sign-in').send(admin).expect(200);
    const csrf = csrfToken(signedIn);
    const project = await adminClient
      .post('/api/v1/projects')
      .set('x-csrf-token', csrf)
      .send({ name: 'Kept after switch', status: 'active' })
      .expect(201);

    const member = credentials();
    const token = await invite(adminClient, csrf, member.email, 'one-company-api');
    const memberJoin = await request(oneCompanyApiBaseUrl)
      .post('/api/v1/auth/accept-invite')
      .send({ email: member.email, password: member.password, token })
      .expect(201);
    expect(memberJoin.body.data).toMatchObject({ email: member.email, role: 'member' });

    const manyCompanyAdmin = request.agent(apiBaseUrl);
    await manyCompanyAdmin.post('/api/v1/auth/sign-in').send(admin).expect(200);
    const members = await manyCompanyAdmin.get('/api/v1/members?page=1&limit=20').expect(200);
    expect(members.body.data.items).toEqual(expect.arrayContaining([
      expect.objectContaining({ email: admin.email, role: 'admin' }),
      expect.objectContaining({ email: member.email, role: 'member' }),
    ]));
    const projects = await manyCompanyAdmin.get('/api/v1/projects?page=1&limit=20').expect(200);
    expect(projects.body.data.items).toEqual([
      expect.objectContaining({ id: project.body.data.id, name: 'Kept after switch' }),
    ]);

    const options = await manyCompanyAdmin.get('/api/v1/auth/options').expect(200);
    expect(options.body.data.signUpOpen).toBe(true);
    const newAccount = credentials();
    const manyCompanyClient = request.agent(apiBaseUrl);
    const signedUp = await manyCompanyClient.post('/api/v1/auth/sign-up').send(newAccount).expect(201);
    expect(signedUp.body.data).toMatchObject({ email: newAccount.email, role: 'admin' });
    const newOrganisationMembers = await manyCompanyClient.get('/api/v1/members?page=1&limit=20').expect(200);
    expect(newOrganisationMembers.body.data.items).toEqual([
      expect.objectContaining({ email: newAccount.email, role: 'admin' }),
    ]);
  });
});
