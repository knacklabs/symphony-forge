import { randomUUID } from 'node:crypto';
import request from 'supertest';
import { describe, expect, it } from 'vitest';
import { apiBaseUrl, credentials, csrfToken, invite } from './helpers';
// forge:feature:mcp:start
import { agentClient } from './helpers';
// forge:feature:mcp:end

// forge:feature:generated-tests:start
type ApiClient = ReturnType<typeof request.agent>;

function requestBodySchema(response: request.Response, path: string, method: 'post' | 'put') {
  const schema = response.body.paths[path][method].requestBody.content['application/json'].schema;
  if (!schema.$ref) return schema;
  const name = schema.$ref.split('/').at(-1);
  return response.body.components.schemas[name];
}

async function signedIn(): Promise<{ client: ApiClient; csrf: string }> {
  const client = request.agent(apiBaseUrl);
  const signUp = await client.post('/api/v1/auth/sign-up').send(credentials()).expect(201);
  return { client, csrf: csrfToken(signUp) };
}

// Sign-up allows 30 accounts a minute for the whole API suite, so the cases that read no
// project data share one account.
let sharedAccount: Promise<{ client: ApiClient; csrf: string }> | undefined;
function sharedSignedIn() {
  sharedAccount ??= signedIn();
  return sharedAccount;
}

// A member of the shared account's organisation, invited as invites.e2e-spec.ts does, with the
// permissions the API reports for it.
let sharedMember: Promise<{ client: ApiClient; csrf: string; permissions: string[] }> | undefined;
function sharedMemberSignedIn() {
  sharedMember ??= (async () => {
    const admin = await sharedSignedIn();
    const invited = credentials();
    const token = await invite(admin.client, admin.csrf, invited.email);
    const client = request.agent(apiBaseUrl);
    const joined = await client.post('/api/v1/auth/accept-invite').send({ ...invited, token }).expect(201);
    const permissions = (await client.get('/api/v1/auth/me').expect(200)).body.data.permissions as string[];
    return { client, csrf: csrfToken(joined), permissions };
  })();
  return sharedMember;
}

/** Every projects route with the permission it needs. A plan that changes the mapping keeps this table right. */
const PROJECT_ROUTES: [string, string, (client: ApiClient, csrf: string, id: string) => request.Test][] = [
  ['list', 'projects.view', (client) => client.get('/api/v1/projects')],
  ['export', 'projects.view', (client) => client.get('/api/v1/projects/export')],
  ['detail', 'projects.view', (client, _csrf, id) => client.get(`/api/v1/projects/${id}`)],
  ['changes', 'projects.view', (client, _csrf, id) => client.get(`/api/v1/projects/${id}/changes`)],
  ['create', 'projects.create', (client, csrf) => client.post('/api/v1/projects').set('x-csrf-token', csrf).send({ name: 'Permission check', status: 'active' })],
  ['replace', 'projects.edit', (client, csrf, id) => client.put(`/api/v1/projects/${id}`).set('x-csrf-token', csrf).send({ name: 'Permission check changed', status: 'archived' })],
  ['delete', 'projects.delete', (client, csrf, id) => client.delete(`/api/v1/projects/${id}`).set('x-csrf-token', csrf)],
  ['restore', 'projects.restore', (client, csrf, id) => client.post(`/api/v1/projects/${id}/restore`).set('x-csrf-token', csrf)],
];

async function createProjects(client: ApiClient, csrf: string, projects: { name: string; status: string }[]) {
  for (const project of projects) {
    await client.post('/api/v1/projects').set('x-csrf-token', csrf).send(project).expect(201);
  }
}

function names(response: request.Response): string[] {
  return response.body.data.items.map((project: { name: string }) => project.name);
}

describe('projects API', () => {
  it('creates, lists, reads, updates, and deletes a project through the API', async () => {
    const { client, csrf } = await signedIn();

    const created = await client
      .post('/api/v1/projects')
      .set('x-csrf-token', csrf)
      .send({ name: 'First project', status: 'active' })
      .expect(201);
    const projectId = created.body.data.id as string;
    expect(created.body.data).toMatchObject({ name: 'First project', status: 'active' });

    const list = await client.get('/api/v1/projects?limit=20&sortBy=name&sortOrder=asc').expect(200);
    expect(list.body.data.items).toEqual([expect.objectContaining({ id: projectId, name: 'First project' })]);
    expect(list.body.data.paging).toEqual({ limit: 20, nextCursor: null, previousCursor: null, total: 1, totalCapped: false });

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
    // An admin may restore, so it still reads the deleted project; the list leaves it out.
    await client.get(`/api/v1/projects/${projectId}`).expect(200)
      .expect(({ body }) => expect(body.data.deletedAtUtc).toEqual(expect.any(String)));
    expect((await client.get('/api/v1/projects').expect(200)).body.data.items).toEqual([]);
  });

  it('pages projects with next and previous cursors', async () => {
    const { client, csrf } = await signedIn();
    await createProjects(client, csrf, ['Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo'].map((name) => ({ name, status: 'active' })));

    // The default order is the last change, newest first.
    expect(names(await client.get('/api/v1/projects').expect(200))).toEqual(['Echo', 'Delta', 'Charlie', 'Bravo', 'Alpha']);

    const byName = '/api/v1/projects?limit=2&sortBy=name&sortOrder=asc';
    const first = await client.get(byName).expect(200);
    expect(names(first)).toEqual(['Alpha', 'Bravo']);
    expect(first.body.data.paging).toMatchObject({ limit: 2, previousCursor: null, total: 5, totalCapped: false });
    const second = await client.get(`${byName}&after=${first.body.data.paging.nextCursor}`).expect(200);
    expect(names(second)).toEqual(['Charlie', 'Delta']);
    const last = await client.get(`${byName}&after=${second.body.data.paging.nextCursor}`).expect(200);
    expect(names(last)).toEqual(['Echo']);
    expect(last.body.data.paging.nextCursor).toBeNull();

    const back = await client.get(`${byName}&before=${last.body.data.paging.previousCursor}`).expect(200);
    expect(names(back)).toEqual(['Charlie', 'Delta']);
    expect(back.body.data.paging.nextCursor).not.toBeNull();
    const start = await client.get(`${byName}&before=${back.body.data.paging.previousCursor}`).expect(200);
    expect(names(start)).toEqual(['Alpha', 'Bravo']);
    expect(start.body.data.paging.previousCursor).toBeNull();

    const descending = await client.get('/api/v1/projects?limit=2&sortBy=name&sortOrder=desc').expect(200);
    const next = await client.get(`/api/v1/projects?limit=2&sortBy=name&sortOrder=desc&after=${descending.body.data.paging.nextCursor}`).expect(200);
    expect(names(next)).toEqual(['Charlie', 'Bravo']);

    // A cursor of another sort, both cursors, or an unreadable cursor gets a field error.
    for (const [query, field] of [
      [`sortBy=status&after=${first.body.data.paging.nextCursor}`, 'after'],
      [`after=${first.body.data.paging.nextCursor}&before=${first.body.data.paging.nextCursor}`, 'before'],
      ['after=not+a+cursor', 'after'],
      ['before=bm90LWpzb24', 'before'],
    ]) {
      const refused = await client.get(`/api/v1/projects?${query}`).expect(400);
      expect(refused.body.error.code).toBe('VALIDATION_ERROR');
      expect(refused.body.error.details.fieldErrors).toEqual([expect.objectContaining({ field })]);
    }

    // A cursor holds the whole name, so a full-length name in any script must still page.
    const longNames = ['A', 'B'].map((letter) => `${'项'.repeat(119)}${letter}`);
    await createProjects(client, csrf, longNames.map((name) => ({ name, status: 'active' })));
    const byLongName = '/api/v1/projects?limit=1&sortBy=name&sortOrder=asc&search=%E9%A1%B9';
    const longFirst = await client.get(byLongName).expect(200);
    expect(names(longFirst)).toEqual([longNames[0]]);
    const longNext = await client.get(`${byLongName}&after=${longFirst.body.data.paging.nextCursor}`).expect(200);
    expect(names(longNext)).toEqual([longNames[1]]);
  });

  it('filters projects by search and filters', async () => {
    const { client, csrf } = await signedIn();
    await createProjects(client, csrf, [
      { name: 'Website redesign', status: 'active' },
      { name: 'Website audit', status: 'archived' },
      { name: 'Mobile app', status: 'active' },
    ]);
    const list = (query: string) => client.get(`/api/v1/projects?sortBy=name&sortOrder=asc&${query}`).expect(200);

    expect(names(await list('search=WEBSITE'))).toEqual(['Website audit', 'Website redesign']);
    expect(names(await list('search=%20site%20'))).toEqual(['Website audit', 'Website redesign']);
    expect(names(await list('status=active'))).toEqual(['Mobile app', 'Website redesign']);
    const both = await list('search=website&status=archived');
    expect(names(both)).toEqual(['Website audit']);
    expect(both.body.data.paging.total).toBe(1);
    // Export CSV downloads what the list shows: the same search and filter.
    const exported = await client.get('/api/v1/projects/export?search=website&status=archived').expect(200);
    expect(exported.text).toContain('Website audit');
    expect(exported.text).not.toContain('Website redesign');
    expect(exported.text).not.toContain('Mobile app');
    // The search text is literal: a % or _ does not match every name.
    expect(names(await list('search=%25'))).toEqual([]);
    expect(names(await list('search=_'))).toEqual([]);

    for (const [query, field] of [['status=gone', 'status'], [`search=${'a'.repeat(201)}`, 'search']]) {
      const refused = await client.get(`/api/v1/projects?${query}`).expect(400);
      expect(refused.body.error.details.fieldErrors).toEqual([expect.objectContaining({ field })]);
    }
  });

  it('records each project change in the change history', async () => {
    // The shared account: the suite's sign-up limit leaves no room for another one.
    const { client, csrf } = await sharedSignedIn();
    const owner = { email: (await client.get('/api/v1/auth/me').expect(200)).body.data.email as string };
    const send = (method: 'post' | 'put' | 'delete', path: string, body?: object) =>
      client[method](`/api/v1/projects${path}`).set('x-csrf-token', csrf).send(body);

    const created = await send('post', '', { name: 'Website redesign', status: 'active' }).expect(201);
    const id = created.body.data.id as string;
    expect(created.body.data).toMatchObject({ createdByEmail: owner.email, modifiedByEmail: owner.email });
    // A second project's changes come between this project's changes and must stay out of its list.
    const other = (await send('post', '', { name: 'Mobile app', status: 'active' }).expect(201)).body.data.id as string;
    await send('put', `/${other}`, { name: 'Mobile app', status: 'archived' }).expect(200);
    await send('put', `/${id}`, { name: 'Website relaunch', status: 'archived' }).expect(200);
    // A replace that changes nothing adds no row.
    await send('put', `/${id}`, { name: 'Website relaunch', status: 'archived' }).expect(200);

    const changes = await client.get(`/api/v1/projects/${id}/changes`).expect(200);
    expect(changes.body.data).toEqual([
      { id: expect.any(String), actorEmail: owner.email, summary: 'Name changed from Website redesign to Website relaunch; Status changed from active to archived', createdAtUtc: expect.any(String) },
      { id: expect.any(String), actorEmail: owner.email, summary: 'Created the project', createdAtUtc: expect.any(String) },
    ]);

    // The detail screen lists the newest 5 changes only.
    for (const name of ['Second', 'Third', 'Fourth', 'Fifth']) await send('put', `/${id}`, { name, status: 'archived' }).expect(200);
    const recent = await client.get(`/api/v1/projects/${id}/changes`).expect(200);
    expect(recent.body.data.map((change: { summary: string }) => change.summary)).toEqual([
      'Name changed from Fourth to Fifth', 'Name changed from Third to Fourth', 'Name changed from Second to Third',
      'Name changed from Website relaunch to Second',
      'Name changed from Website redesign to Website relaunch; Status changed from active to archived',
    ]);

    await send('delete', `/${id}`).expect(200);
    // The Change history screen names the project each change was made to.
    const history = await client.get('/api/v1/history').expect(200);
    expect(history.body.data.map((entry: { summary: string }) => entry.summary)).toEqual([
      'Fifth: Deleted the project', 'Fifth: Name changed from Fourth to Fifth', 'Fourth: Name changed from Third to Fourth',
      'Third: Name changed from Second to Third', 'Second: Name changed from Website relaunch to Second',
      'Website relaunch: Name changed from Website redesign to Website relaunch; Status changed from active to archived',
      'Mobile app: Status changed from active to archived', 'Mobile app: Created the project',
      'Website redesign: Created the project',
    ]);
    const otherChanges = await client.get(`/api/v1/projects/${other}/changes`).expect(200);
    expect(otherChanges.body.data.map((change: { summary: string }) => change.summary))
      .toEqual(['Status changed from active to archived', 'Created the project']);
    expect((await client.get('/api/v1/history/export').expect(200)).text).toContain(`,${owner.email},Fifth: Deleted the project`);

    // An admin still reads a deleted project's changes, the delete first.
    const afterDelete = await client.get(`/api/v1/projects/${id}/changes`).expect(200);
    expect(afterDelete.body.data[0]).toMatchObject({ summary: 'Deleted the project', actorEmail: owner.email });
  });

  // After the change history case: these cases add projects to the shared organisation.
  it('each projects endpoint refuses a member without its permission', async () => {
    const admin = await sharedSignedIn();
    const member = await sharedMemberSignedIn();
    const adminPermissions = (await admin.client.get('/api/v1/auth/me').expect(200)).body.data.permissions as string[];
    for (const [who, caller, permissions] of [['member', member, member.permissions], ['admin', admin, adminPermissions]] as const) {
      const id = (await admin.client.post('/api/v1/projects').set('x-csrf-token', admin.csrf)
        .send({ name: `Checked for the ${who}`, status: 'active' }).expect(201)).body.data.id as string;
      for (const [route, permission, send] of PROJECT_ROUTES) {
        const response = await send(caller.client, caller.csrf, id);
        if (permissions.includes(permission)) {
          expect(response.status, `${who} ${route}`).not.toBe(403);
        } else {
          expect(response.status, `${who} ${route}`).toBe(403);
          expect(response.body.error.code, `${who} ${route}`).toBe('PERMISSION_DENIED');
        }
      }
    }
  });

  it('an admin restores a deleted project', async () => {
    const { client, csrf } = await sharedSignedIn();
    const member = await sharedMemberSignedIn();
    const ownerEmail = (await client.get('/api/v1/auth/me').expect(200)).body.data.email as string;
    const mark = randomUUID();
    const create = async (name: string) => (await client.post('/api/v1/projects').set('x-csrf-token', csrf)
      .send({ name: `${name} ${mark}`, status: 'active' }).expect(201)).body.data.id as string;
    const id = await create('Restored');
    const keptId = await create('Kept');
    await client.delete(`/api/v1/projects/${id}`).set('x-csrf-token', csrf).expect(200);
    const listIds = async (caller: ApiClient, extra = '') =>
      (await caller.get(`/api/v1/projects?search=${mark}${extra}`).expect(200)).body.data.items.map((project: { id: string }) => project.id);

    // The deleted project shows among the active ones only when asked for.
    expect(await listIds(client)).toEqual([keptId]);
    const withDeleted = await client.get(`/api/v1/projects?search=${mark}&deleted=yes`).expect(200);
    // Newest change first: the delete changed the deleted project last.
    expect(withDeleted.body.data.items).toEqual([
      expect.objectContaining({ id, deletedAtUtc: expect.any(String), deletedByEmail: ownerEmail }),
      expect.objectContaining({ id: keptId, deletedAtUtc: null, deletedByEmail: null }),
    ]);
    expect((await client.get(`/api/v1/projects/export?search=${mark}&deleted=yes`).expect(200)).text).toContain(`Restored ${mark}`);
    expect((await client.get(`/api/v1/projects/export?search=${mark}`).expect(200)).text).not.toContain(`Restored ${mark}`);

    // A member never sees a deleted project: the key is ignored and the detail is not found.
    expect(await listIds(member.client, '&deleted=yes')).toEqual([keptId]);
    await member.client.get(`/api/v1/projects/${id}`).expect(404);
    await member.client.get(`/api/v1/projects/${id}/changes`).expect(404);

    const restored = await client.post(`/api/v1/projects/${id}/restore`).set('x-csrf-token', csrf).expect(200);
    expect(restored.body.data).toMatchObject({ id, deletedAtUtc: null, deletedByEmail: null, modifiedByEmail: ownerEmail });
    expect(await listIds(client)).toEqual([id, keptId]);
    const changes = await client.get(`/api/v1/projects/${id}/changes`).expect(200);
    expect(changes.body.data.map((change: { summary: string }) => change.summary).slice(0, 2)).toEqual(['Restored the project', 'Deleted the project']);
    // Only a deleted project can be restored.
    await client.post(`/api/v1/projects/${id}/restore`).set('x-csrf-token', csrf).expect(404)
      .expect(({ body }) => expect(body.error.code).toBe('PROJECT_NOT_FOUND'));
  });

  it('rejects a bad list query with the same field errors as a bad body', async () => {
    const { client, csrf } = await sharedSignedIn();

    const query = await client
      .get('/api/v1/projects?limit=500&sortBy=password&unexpected=true')
      .expect(400);
    const body = await client
      .post('/api/v1/projects')
      .set('x-csrf-token', csrf)
      .send({ name: '', status: 'gone', unexpected: true })
      .expect(400);

    for (const response of [query, body]) {
      expect(response.body).toMatchObject({
        success: false,
        data: null,
        error: { code: 'VALIDATION_ERROR', message: 'Check the fields and try again.' },
      });
    }
    expect(query.body.error.details.fieldErrors).toEqual(expect.arrayContaining([
      expect.objectContaining({ field: 'limit' }),
      expect.objectContaining({ field: 'sortBy' }),
      expect.objectContaining({ field: 'unexpected', reason: 'Remove this field.' }),
    ]));
    expect(body.body.error.details.fieldErrors).toEqual(expect.arrayContaining([
      expect.objectContaining({ field: 'name' }),
      expect.objectContaining({ field: 'status' }),
      expect.objectContaining({ field: 'unexpected', reason: 'Remove this field.' }),
    ]));

    for (const malformedLimit of ['?limit=1&limit=2', '?limit=']) {
      const invalidLimit = await client.get(`/api/v1/projects${malformedLimit}`).expect(400);
      expect(invalidLimit.body.error.code).toBe('VALIDATION_ERROR');
      expect(invalidLimit.body.error.details.fieldErrors).toEqual(expect.arrayContaining([
        expect.objectContaining({ field: 'limit' }),
      ]));
    }

    const valid = await client.get('/api/v1/projects?limit=5').expect(200);
    expect(valid.body.data.paging).toMatchObject({ limit: 5 });
  });

  it('documents the list query and request bodies from the shared zod schemas', async () => {
    const response = await request(apiBaseUrl).get('/api/docs-json').expect(200);
    const projectsList = response.body.paths['/api/v1/projects'].get;
    const parameters = projectsList.parameters;

    expect(parameters).toHaveLength(8);
    expect(parameters).toEqual(expect.arrayContaining([
      expect.objectContaining({
        name: 'deleted',
        in: 'query',
        required: false,
        schema: expect.objectContaining({ enum: ['yes'] }),
      }),
      expect.objectContaining({
        name: 'search',
        in: 'query',
        required: false,
        schema: expect.objectContaining({ maxLength: 200 }),
      }),
      expect.objectContaining({
        name: 'status',
        in: 'query',
        required: false,
        schema: expect.objectContaining({ enum: ['active', 'archived'] }),
      }),
      expect.objectContaining({
        name: 'limit',
        in: 'query',
        required: false,
        schema: expect.objectContaining({ maximum: 100, default: 20 }),
      }),
      expect.objectContaining({
        name: 'sortBy',
        in: 'query',
        required: false,
        schema: expect.objectContaining({ enum: ['name', 'status', 'createdAtUtc', 'updatedAtUtc'], default: 'updatedAtUtc' }),
      }),
      expect.objectContaining({
        name: 'sortOrder',
        in: 'query',
        required: false,
        schema: expect.objectContaining({ enum: ['asc', 'desc'] }),
      }),
      expect.objectContaining({ name: 'after', in: 'query', required: false }),
      expect.objectContaining({ name: 'before', in: 'query', required: false }),
    ]));

    for (const [path, method] of [
      ['/api/v1/projects', 'post'],
      ['/api/v1/projects/{id}', 'put'],
    ] as const) {
      const schema = requestBodySchema(response, path, method);
      expect(schema.properties.name).toMatchObject({
        description: 'The project name.',
        example: 'Migration plan',
        maxLength: 120,
      });
      expect(schema.properties.status).toMatchObject({
        description: 'The project status.',
        example: 'active',
        enum: ['active', 'archived'],
      });
    }

    for (const path of ['/api/v1/auth/sign-up', '/api/v1/auth/sign-in']) {
      const schema = requestBodySchema(response, path, 'post');
      expect(schema.properties.password).toMatchObject({
        description: 'The account password.',
        example: 'correct-horse-battery-staple',
        minLength: 12,
        maxLength: 128,
      });
    }

    const forgotPassword = requestBodySchema(response, '/api/v1/auth/forgot-password', 'post');
    expect(forgotPassword.properties.email).toMatchObject({
      description: 'The email address for the account.',
      example: 'ada@example.com',
      maxLength: 254,
      format: 'email',
    });

    const resetPassword = requestBodySchema(response, '/api/v1/auth/reset-password', 'post');
    expect(resetPassword.properties.token).toMatchObject({
      description: 'The single-use token from the reset link.',
      example: 'a-43-character-token-value',
      minLength: 32,
      maxLength: 256,
    });
    expect(resetPassword.properties.password).toMatchObject({
      description: 'The new account password.',
      example: 'new-correct-horse-battery-staple',
      minLength: 12,
      maxLength: 128,
    });
  });

  it('rejects a whitespace-only project name after trimming input', async () => {
    const { client, csrf } = await sharedSignedIn();

    const response = await client
      .post('/api/v1/projects')
      .set('x-csrf-token', csrf)
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

    const { client, csrf } = await sharedSignedIn();
    await client.post('/api/v1/projects').send({ name: 'No token', status: 'active' }).expect(403);
    await client
      .post('/api/v1/projects')
      .set('x-csrf-token', `${csrf}wrong`)
      .send({ name: 'Bad token', status: 'active' })
      .expect(403);
  });
});
// forge:feature:generated-tests:end

// forge:feature:mcp-cases:start
async function addMcpAgent(
  client: ApiClient,
  csrf: string,
  role: 'admin' | 'member',
) {
  const account = (await client.post('/api/v1/agents').set('x-csrf-token', csrf)
    .send({ name: `mcp-${randomUUID().slice(0, 8)}`, role }).expect(201)).body.data;
  const key = (await client.post(`/api/v1/members/${account.accountId}/key`)
    .set('x-csrf-token', csrf).expect(201)).body.data.key as string;
  return { email: account.email as string, accountId: account.accountId as string, key };
}

function resultData(result: unknown): Record<string, unknown> {
  if (typeof result !== 'object' || result === null || !('structuredContent' in result)) {
    throw new Error('The MCP call did not return structured content.');
  }
  const data = result.structuredContent;
  if (typeof data !== 'object' || data === null) throw new Error('The MCP result is not an object.');
  return data as Record<string, unknown>;
}

function resultError(result: unknown): Record<string, unknown> {
  const data = JSON.parse(resultText(result));
  if (typeof data.error !== 'object' || data.error === null) throw new Error('The MCP result has no tool error.');
  return data.error as Record<string, unknown>;
}

function resultText(result: unknown): string {
  if (typeof result !== 'object' || result === null || !('content' in result) || !Array.isArray(result.content)) {
    throw new Error('The MCP call did not return text content.');
  }
  const first = result.content[0];
  if (typeof first !== 'object' || first === null || !('text' in first) || typeof first.text !== 'string') {
    throw new Error('The MCP call did not return a text summary.');
  }
  return first.text;
}

describe('projects MCP tools', () => {
  it('an agent searches, reads, creates and updates projects through MCP as its account', async () => {
    // Audit: protects the real agent path through search, get, create, update and history attribution.
    // A wrong projection, role, or actor would fail here; REST project tests cannot exercise MCP calls.
    const { client, csrf } = await signedIn();
    const agent = await addMcpAgent(client, csrf, 'member');
    const mcp = await agentClient(agent.key);
    const mark = randomUUID();
    try {
      const listed = await mcp.listTools();
      expect(listed.tools.filter(({ name }) => name.startsWith('projects_')).map(({ name }) => name).sort())
        .toEqual(['projects_create', 'projects_get', 'projects_search', 'projects_update']);

      const created = resultData(await mcp.callTool({ name: 'projects_create', arguments: {
        name: `Agent project ${mark}`, status: 'active',
      } }));
      expect(created).toMatchObject({ name: `Agent project ${mark}`, status: 'active', status_label: 'Active' });
      expect(created).not.toHaveProperty('created_by_email');
      const projectId = created.project_id as string;

      const searchResult = await mcp.callTool({ name: 'projects_search', arguments: { query: mark } });
      const search = resultData(searchResult);
      expect(search.items).toEqual([expect.objectContaining({ project_id: projectId, status_label: 'Active' })]);
      expect(search.items).not.toEqual([expect.objectContaining({ created_by_email: expect.any(String) })]);

      const detailed = resultData(await mcp.callTool({ name: 'projects_get', arguments: {
        project_id: projectId, response_format: 'detailed',
      } }));
      expect(detailed).toMatchObject({ project_id: projectId, created_by_email: agent.email });

      const updated = resultData(await mcp.callTool({ name: 'projects_update', arguments: {
        project_id: projectId, name: `Agent project ${mark}`, status: 'archived',
      } }));
      expect(updated).toMatchObject({ name: `Agent project ${mark}`, status_label: 'Archived' });
      expect(updated).not.toHaveProperty('created_by_email');

      const history = await client.get('/api/v1/history').expect(200);
      expect(history.body.data).toEqual(expect.arrayContaining([
        expect.objectContaining({ actorEmail: agent.email, summary: 'Created the project' }),
        expect.objectContaining({ actorEmail: agent.email, summary: 'Status changed from active to archived' }),
      ]));
      const changes = await client.get(`/api/v1/projects/${projectId}/changes`).expect(200);
      expect(changes.body.data).toEqual(expect.arrayContaining([
        expect.objectContaining({ actorEmail: agent.email, summary: 'Status changed from active to archived' }),
        expect.objectContaining({ actorEmail: agent.email, summary: 'Created the project' }),
      ]));
    } finally {
      await mcp.close();
    }
  });

  it('a member agent cannot delete or restore a project through MCP', async () => {
    // Audit: checks both tool discovery and an unauthorized call after the admin turns the switch on.
    // A permission leak would delete a real project; existing screen/API permission tests do not cover MCP.
    const { client, csrf } = await signedIn();
    const agent = await addMcpAgent(client, csrf, 'member');
    const project = (await client.post('/api/v1/projects').set('x-csrf-token', csrf)
      .send({ name: `Member boundary ${randomUUID()}`, status: 'active' }).expect(201)).body.data;
    await client.put('/api/v1/agent-tools/projects').set('x-csrf-token', csrf)
      .send({ deleteAndRestore: true }).expect(200);

    const mcp = await agentClient(agent.key);
    try {
      const tools = (await mcp.listTools()).tools.filter(({ name }) => name.startsWith('projects_')).map(({ name }) => name);
      expect(tools).toEqual(expect.arrayContaining(['projects_search', 'projects_get', 'projects_create', 'projects_update']));
      expect(tools).not.toContain('projects_delete');
      expect(tools).not.toContain('projects_restore');
      const denied = await mcp.callTool({ name: 'projects_delete', arguments: { project_id: project.id } });
      expect(('isError' in denied) ? denied.isError : false).toBe(true);
      expect(resultError(denied)).toMatchObject({ kind: 'not_allowed', retryable: false });
      await client.get(`/api/v1/projects/${project.id}`).expect(200)
        .expect(({ body }) => expect(body.data.deletedAtUtc).toBeNull());
    } finally {
      await mcp.close();
    }
  });

  it('project delete and restore tools stay off until an admin turns them on', async () => {
    // Audit: verifies default-off, permission enforcement, repeat-safe delete/restore, history, and the switch off path.
    // A default-on tool or a repeat that adds another history row would fail; the REST access tests cannot reach MCP.
    const { client, csrf } = await signedIn();
    const agent = await addMcpAgent(client, csrf, 'admin');
    const project = (await client.post('/api/v1/projects').set('x-csrf-token', csrf)
      .send({ name: `Admin boundary ${randomUUID()}`, status: 'active' }).expect(201)).body.data;
    const mcp = await agentClient(agent.key);
    try {
      const fourTools = ['projects_create', 'projects_get', 'projects_search', 'projects_update'];
      const names = () => mcp.listTools().then(({ tools }) => tools.filter(({ name }) => name.startsWith('projects_'))
        .map(({ name }) => name).sort());
      expect(await names()).toEqual(fourTools);
      const denied = await mcp.callTool({ name: 'projects_delete', arguments: { project_id: project.id } });
      expect(resultError(denied)).toMatchObject({ kind: 'not_allowed', retryable: false });

      await client.put('/api/v1/agent-tools/projects').set('x-csrf-token', csrf)
        .send({ deleteAndRestore: true }).expect(200);
      expect(await names()).toEqual([...fourTools, 'projects_delete', 'projects_restore'].sort());

      for (const action of ['delete', 'delete', 'restore', 'restore']) {
        const result = await mcp.callTool({ name: `projects_${action}`, arguments: { project_id: project.id } });
        expect(('isError' in result) ? result.isError : false).toBe(false);
      }
      const history = await client.get('/api/v1/history').expect(200);
      const agentChanges = history.body.data.filter((entry: { actorEmail: string }) => entry.actorEmail === agent.email);
      expect(agentChanges.filter((entry: { summary: string }) => entry.summary === 'Deleted the project')).toHaveLength(1);
      expect(agentChanges.filter((entry: { summary: string }) => entry.summary === 'Restored the project')).toHaveLength(1);

      await client.put('/api/v1/agent-tools/projects').set('x-csrf-token', csrf)
        .send({ deleteAndRestore: false }).expect(200);
      expect(await names()).toEqual(fourTools);
    } finally {
      await mcp.close();
    }
  });

  it('project search pages with a cursor and says how many match', async () => {
    // Audit: protects the search contract at the agent boundary: page size, total, cursor, and narrowing advice.
    // Existing REST paging coverage cannot catch a tool that ignores or misnames MCP paging fields.
    const { client, csrf } = await signedIn();
    const agent = await addMcpAgent(client, csrf, 'member');
    const mark = randomUUID();
    for (let index = 0; index < 25; index += 1) {
      await client.post('/api/v1/projects').set('x-csrf-token', csrf)
        .send({ name: `MCP page ${mark} ${index}`, status: 'active' }).expect(201);
    }
    const excluded = (await client.post('/api/v1/projects').set('x-csrf-token', csrf)
      .send({ name: `MCP page ${mark} archived`, status: 'archived' }).expect(201)).body.data;
    const mcp = await agentClient(agent.key);
    try {
      const firstResult = await mcp.callTool({ name: 'projects_search', arguments: { query: mark, status: 'active' } });
      const first = resultData(firstResult);
      expect(first.items).toHaveLength(20);
      expect(first).toMatchObject({ total: 25, total_is_capped: false, next_cursor: expect.any(String) });
      expect(resultText(firstResult)).toContain('25 matching projects');
      expect(resultText(firstResult)).toContain('narrow with query');

      const next = resultData(await mcp.callTool({ name: 'projects_search', arguments: {
        query: mark, status: 'active', cursor: first.next_cursor,
      } }));
      expect(next.items).toHaveLength(5);
      expect(next.next_cursor).toBeNull();
      for (const page of [first, next]) {
        expect(page.items).not.toEqual(expect.arrayContaining([expect.objectContaining({ project_id: excluded.id })]));
      }

      const invalid = await mcp.callTool({ name: 'projects_search', arguments: { query: mark, limit: 101 } });
      expect(resultError(invalid)).toMatchObject({ kind: 'invalid_input', retryable: false });
    } finally {
      await mcp.close();
    }
  });

  it('a retried project create with the same idempotency key makes one project', async () => {
    // Audit: checks that a client retry creates one database item and returns the same identity.
    // REST creation has no idempotency key, so it cannot detect a duplicate MCP create.
    const { client, csrf } = await signedIn();
    const agent = await addMcpAgent(client, csrf, 'member');
    const mark = randomUUID();
    const mcp = await agentClient(agent.key);
    try {
      const args = { name: `Retry project ${mark}`, status: 'active', idempotency_key: `project-${mark}` };
      const first = resultData(await mcp.callTool({ name: 'projects_create', arguments: args }));
      const retried = resultData(await mcp.callTool({ name: 'projects_create', arguments: args }));
      expect(retried.project_id).toBe(first.project_id);
      const found = resultData(await mcp.callTool({ name: 'projects_search', arguments: { query: mark } }));
      expect(found.items).toHaveLength(1);
    } finally {
      await mcp.close();
    }
  });

  it('a repeated project update changes nothing', async () => {
    // Audit: verifies repeated updates leave one change event and a stable updated timestamp.
    // The REST service's usual update case does not retry the same MCP call.
    const { client, csrf } = await signedIn();
    const agent = await addMcpAgent(client, csrf, 'member');
    const mark = randomUUID();
    const mcp = await agentClient(agent.key);
    try {
      const created = resultData(await mcp.callTool({ name: 'projects_create', arguments: {
        name: `Update project ${mark}`, status: 'active',
      } }));
      const args = { project_id: created.project_id, name: `Updated project ${mark}`, status: 'archived' };
      const first = resultData(await mcp.callTool({ name: 'projects_update', arguments: args }));
      const repeated = resultData(await mcp.callTool({ name: 'projects_update', arguments: args }));
      expect(repeated.updated_at_utc).toBe(first.updated_at_utc);
      const changes = await client.get(`/api/v1/projects/${created.project_id}/changes`).expect(200);
      expect(changes.body.data.filter((entry: { summary: string }) => entry.summary !== 'Created the project')).toHaveLength(1);
    } finally {
      await mcp.close();
    }
  });

  it('an invalid project input gets a non-retryable error with an example', async () => {
    // Audit: protects the repair text and field detail for a schema rejection visible to the agent.
    // REST validation returns a different envelope and cannot prove the MCP tool error is usable.
    const { client, csrf } = await signedIn();
    const agent = await addMcpAgent(client, csrf, 'member');
    const mcp = await agentClient(agent.key);
    try {
      const result = await mcp.callTool({ name: 'projects_create', arguments: {
        name: 'Invalid status', status: 'planned',
      } });
      const error = resultError(result);
      expect(error).toMatchObject({ kind: 'invalid_input', retryable: false });
      expect(JSON.stringify(error.details)).toContain('status');
      expect(error.message).toContain('Example:');
    } finally {
      await mcp.close();
    }
  });

  it('an agent key over its rate limit gets a retryable error', async () => {
    // Audit: verifies a single key is throttled with a useful wait time while another key remains usable.
    // The person-address throttle cannot prove the per-agent-key limit or independent keys.
    const { client, csrf } = await signedIn();
    const firstAgent = await addMcpAgent(client, csrf, 'member');
    const secondAgent = await addMcpAgent(client, csrf, 'member');
    const first = await agentClient(firstAgent.key);
    const second = await agentClient(secondAgent.key);
    try {
      let last: unknown;
      for (let attempt = 0; attempt < 121; attempt += 1) {
        last = await first.callTool({ name: 'projects_search', arguments: { query: 'no matching project' } });
      }
      const limited = resultError(last);
      expect(limited).toMatchObject({ kind: 'rate_limited', retryable: true });
      expect(limited.retry_after_seconds).toEqual(expect.any(Number));
      expect(limited.retry_after_seconds as number).toBeGreaterThanOrEqual(1);
      expect(limited.retry_after_seconds as number).toBeLessThanOrEqual(60);
      const stillWorks = await second.callTool({ name: 'projects_search', arguments: { query: 'no matching project' } });
      expect(('isError' in stillWorks) ? stillWorks.isError : false).toBe(false);
    } finally {
      await Promise.all([first.close(), second.close()]);
    }
  });
});
// forge:feature:mcp-cases:end
