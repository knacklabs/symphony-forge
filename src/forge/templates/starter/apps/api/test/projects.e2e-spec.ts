import request from 'supertest';
import { describe, expect, it } from 'vitest';
import { apiBaseUrl, credentials, csrfToken } from './helpers';

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
    await client.get(`/api/v1/projects/${projectId}`).expect(404);
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

    expect(parameters).toHaveLength(7);
    expect(parameters).toEqual(expect.arrayContaining([
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
