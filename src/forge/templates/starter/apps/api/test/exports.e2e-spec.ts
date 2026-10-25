import request from 'supertest';
import { describe, expect, it } from 'vitest';
import { apiBaseUrl, credentials, csrfToken } from './helpers';

const PROJECTS_HEADER = 'Name,Status,Created (UTC),Updated (UTC)';
const MEMBERS_HEADER = 'Email,Role,Joined (UTC)';
const HISTORY_HEADER = 'When (UTC),Who,What';
const UTC_DATE_TIME = '\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}';

describe('CSV exports', () => {
  it('projects export as CSV', async () => {
    const client = request.agent(apiBaseUrl);
    const csrf = csrfToken(await client.post('/api/v1/auth/sign-up').send(credentials()).expect(201));
    for (const name of ['Plan, "draft"', '=1+1', 'Deleted project']) {
      await client.post('/api/v1/projects').set('x-csrf-token', csrf).send({ name, status: 'active' }).expect(201);
    }
    const list = await client.get('/api/v1/projects?sortBy=name&sortOrder=asc').expect(200);
    const deleted = list.body.data.items.find((project: { name: string }) => project.name === 'Deleted project');
    await client.delete(`/api/v1/projects/${deleted.id}`).set('x-csrf-token', csrf).expect(200);

    const response = await client.get('/api/v1/projects/export').expect(200);
    expect(response.get('Content-Type')).toBe('text/csv; charset=utf-8');
    expect(response.get('Content-Disposition')).toBe('attachment; filename="projects.csv"');
    const lines = response.text.split('\r\n');
    expect(lines).toHaveLength(4);
    expect(lines[0]).toBe(PROJECTS_HEADER);
    // Newest first, whatever order the screen sorts by.
    expect(lines[1]).toMatch(new RegExp(`^'=1\\+1,active,${UTC_DATE_TIME},${UTC_DATE_TIME}$`));
    expect(lines[2]).toMatch(new RegExp(`^"Plan, ""draft""",active,${UTC_DATE_TIME},${UTC_DATE_TIME}$`));
    expect(lines[3]).toBe('');
    expect(response.text).not.toContain('Deleted project');

    const other = request.agent(apiBaseUrl);
    await other.post('/api/v1/auth/sign-up').send(credentials()).expect(201);
    expect((await other.get('/api/v1/projects/export').expect(200)).text).toBe(`${PROJECTS_HEADER}\r\n`);
    await request(apiBaseUrl).get('/api/v1/projects/export').expect(401);
  });

  it('members export as CSV', async () => {
    const account = credentials();
    const client = request.agent(apiBaseUrl);
    await client.post('/api/v1/auth/sign-up').send(account).expect(201);

    const response = await client.get('/api/v1/members/export').expect(200);
    expect(response.get('Content-Type')).toBe('text/csv; charset=utf-8');
    expect(response.get('Content-Disposition')).toBe('attachment; filename="members.csv"');
    const lines = response.text.split('\r\n');
    expect(lines).toHaveLength(3);
    expect(lines[0]).toBe(MEMBERS_HEADER);
    expect(lines[1].startsWith(`${account.email},admin,`)).toBe(true);
    expect(lines[1]).toMatch(/,\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
    expect(lines[2]).toBe('');
    await request(apiBaseUrl).get('/api/v1/members/export').expect(401);
  });

  it('change history exports as CSV', async () => {
    const admin = credentials();
    const client = request.agent(apiBaseUrl);
    const csrf = csrfToken(await client.post('/api/v1/auth/sign-up').send(admin).expect(201));
    const emails: string[] = [];
    for (let index = 0; index < 101; index += 1) {
      const email = credentials().email;
      emails.push(email);
      await client.post('/api/v1/invites').set('x-csrf-token', csrf).send({ email }).expect(201);
    }

    const history = await client.get('/api/v1/history').expect(200);
    expect(history.body.data).toHaveLength(100);
    expect(history.body.data[0].summary).toBe(`Invited ${emails[100]}`);
    expect(history.body.data[99].summary).toBe(`Invited ${emails[1]}`);

    const response = await client.get('/api/v1/history/export').expect(200);
    expect(response.get('Content-Type')).toBe('text/csv; charset=utf-8');
    expect(response.get('Content-Disposition')).toBe('attachment; filename="history.csv"');
    const lines = response.text.split('\r\n');
    expect(lines).toHaveLength(103);
    expect(lines[0]).toBe(HISTORY_HEADER);
    expect(lines[102]).toBe('');
    const rows = lines.slice(1, 102).map((line) => line.split(','));
    expect(rows.map(([when, who, what]) => {
      expect(when).toMatch(new RegExp(`^${UTC_DATE_TIME}$`));
      return [who, what];
    })).toEqual([...emails].reverse().map((email) => [admin.email, `Invited ${email}`]));
  });
});
