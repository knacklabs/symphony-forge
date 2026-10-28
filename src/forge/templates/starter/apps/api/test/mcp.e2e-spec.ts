import { randomUUID } from 'node:crypto';
import request from 'supertest';
import { describe, expect, it } from 'vitest';
import { agentClient, apiBaseUrl, credentials, csrfToken } from './helpers';

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

function initialize(key?: string) {
  const call = request(apiBaseUrl).post('/mcp')
    .set('Accept', 'application/json, text/event-stream')
    .set('Content-Type', 'application/json');
  return (key ? call.set('Authorization', `Bearer ${key}`) : call).send(initializeRequest);
}

async function addAgentKey(role: 'admin' | 'member' = 'admin') {
  const client = request.agent(apiBaseUrl);
  const signedUp = await client.post('/api/v1/auth/sign-up').send(credentials()).expect(201);
  const csrf = csrfToken(signedUp);
  const agent = (await client.post('/api/v1/agents').set('x-csrf-token', csrf)
    .send({ name: 'mcp-check', role }).expect(201)).body.data;
  const key = (await client.post(`/api/v1/members/${agent.accountId}/key`)
    .set('x-csrf-token', csrf).expect(201)).body.data.key as string;
  return { client, csrf, agent, key };
}

function record(value: unknown): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new Error('Expected an object.');
  return value as Record<string, unknown>;
}

function records(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) throw new Error('Expected a list of objects.');
  return value.map(record);
}

function resultData(result: unknown): Record<string, unknown> {
  const value = record(result);
  if (!('structuredContent' in value)) throw new Error('The MCP call did not return structured content.');
  return record(value.structuredContent);
}

async function readJsonResource(client: Awaited<ReturnType<typeof agentClient>>, uri: string): Promise<unknown> {
  const result = await client.readResource({ uri });
  expect(result.contents).toHaveLength(1);
  const content = result.contents[0];
  if (!content || !('text' in content) || typeof content.text !== 'string') throw new Error('The resource did not return JSON text.');
  expect(content.mimeType).toBe('application/json');
  return JSON.parse(content.text);
}

function expectSentence(value: unknown) {
  expect(typeof value).toBe('string');
  if (typeof value !== 'string') throw new Error('The resource has no description.');
  expect(value).toMatch(/[.!?](?:\s|$)/);
}

function schemaProperties(value: unknown): Record<string, unknown> {
  const schema = record(value);
  return schema.properties && typeof schema.properties === 'object'
    ? schema.properties as Record<string, unknown>
    : {};
}

function enumValues(value: unknown): unknown[] | undefined {
  const schema = record(value);
  return Array.isArray(schema.enum) ? schema.enum : undefined;
}

describe('MCP server', () => {
  it('the MCP server refuses a missing or revoked agent key', async () => {
    // Audit: protects the public transport's authentication boundary, including immediate key revocation.
    // A route that accepts an absent, unknown, or revoked key would fail this; the API auth tests do not
    // exercise MCP transport. The real SDK client proves a created key can initialize before revocation.
    for (const response of [await initialize(), await initialize(`agent_${'A'.repeat(43)}`)]) {
      expect(response.status).toBe(401);
      expect(response.body.error.code).toBe('UNAUTHENTICATED');
    }

    const { client, csrf, agent, key } = await addAgentKey();
    const mcp = await agentClient(key);
    try {
      const listed = await mcp.listTools();
      expect(listed.tools.some(({ name }) => name.startsWith('projects_'))).toBe(true);
    } finally {
      await mcp.close();
    }

    await client.delete(`/api/v1/members/${agent.accountId}/key`).set('x-csrf-token', csrf).expect(200);
    const revoked = await initialize(key);
    expect(revoked.status).toBe(401);
    expect(revoked.body.error.code).toBe('UNAUTHENTICATED');
  });

  it('every tool has a description, annotations, schemas and the error shape', async () => {
    // Audit: checks every advertised tool at the real MCP boundary, including generated defaults and
    // hand-written tools. A tool missing its schema, annotations, strict input or recoverable error fails;
    // the projects tests cover calls that change or read actual data. No test-only production seam is used.
    const { client, csrf, key } = await addAgentKey('admin');
    const mcp = await agentClient(key);
    try {
      const initial = await mcp.listTools();
      const features = [...new Set(initial.tools.filter(({ name }) => name.endsWith('_search'))
        .map(({ name }) => name.slice(0, -'_search'.length)))];
      for (const feature of features) {
        await client.put(`/api/v1/agent-tools/${feature.replace(/_/g, '-')}`)
          .set('x-csrf-token', csrf).send({ deleteAndRestore: true }).expect(200);
      }

      const tools = (await mcp.listTools()).tools;
      expect(tools.length).toBeGreaterThan(0);
      for (const tool of tools) {
        expect(tool.description).toEqual(expect.any(String));
        expect((tool.description?.match(/[.!?](?:\s|$)/g) ?? []).length).toBeGreaterThanOrEqual(2);
        expect(tool.annotations?.title).toEqual(expect.any(String));
        for (const hint of ['readOnlyHint', 'destructiveHint', 'idempotentHint', 'openWorldHint'] as const) {
          expect(typeof tool.annotations?.[hint]).toBe('boolean');
        }
        expect(tool.inputSchema).toMatchObject({ type: 'object', additionalProperties: false });
        expect(tool.outputSchema).toMatchObject({ type: 'object' });

        const suffix = tool.name.match(/_(search|get|create|update|delete|restore)$/)?.[1];
        if (suffix) {
          expect(tool.annotations).toMatchObject({
            readOnlyHint: suffix === 'search' || suffix === 'get',
            destructiveHint: suffix === 'delete',
            idempotentHint: suffix === 'update' || suffix === 'delete' || suffix === 'restore',
            openWorldHint: false,
          });
        }

        const failed = await mcp.callTool({ name: tool.name, arguments: { unexpected_argument: true } });
        expect(failed.isError).toBe(true);
        expect(failed.structuredContent).toBeUndefined();
        if (!Array.isArray(failed.content) || failed.content[0]?.type !== 'text') {
          throw new Error('The tool error has no text content.');
        }
        expect(JSON.parse(failed.content[0].text)).toMatchObject({
          error: { kind: 'invalid_input', retryable: false, message: expect.any(String) },
        });
      }
      const projectSearch = tools.find(({ name }) => name === 'projects_search');
      expect(projectSearch?.inputSchema.properties).toHaveProperty('query');
      for (const action of ['get', 'update', 'delete', 'restore']) {
        const projectTool = tools.find(({ name }) => name === `projects_${action}`);
        expect(projectTool?.inputSchema.properties).toHaveProperty('project_id');
        expect(projectTool?.inputSchema.properties).not.toHaveProperty('id');
      }
    } finally {
      await mcp.close();
    }
  });

  it('an agent reads a project, the project fields and the status values as resources', async () => {
    // Audit: protects project resource content at the public MCP boundary, including equality with
    // detailed get and unknown-id behavior. Existing tests exercise project tools but do not read resources.
    const { key } = await addAgentKey('member');
    const mcp = await agentClient(key);
    const mark = `Resource project ${randomUUID()}`;
    try {
      const created = resultData(await mcp.callTool({ name: 'projects_create', arguments: { name: mark, status: 'active' } }));
      if (typeof created.project_id !== 'string') throw new Error('The created project has no id.');
      const projectId = created.project_id;
      const templates = (await mcp.listResourceTemplates()).resourceTemplates;
      expect(templates).toEqual(expect.arrayContaining([
        expect.objectContaining({ uriTemplate: 'app://projects/{project_id}' }),
      ]));

      const listed = (await mcp.listResources()).resources;
      const fieldsUri = 'app://projects/fields';
      const valuesUri = 'app://projects/fields/status/values';
      expect(listed.map(({ uri }) => uri)).toEqual(expect.arrayContaining([fieldsUri, valuesUri]));
      const fieldGuide = record(await readJsonResource(mcp, fieldsUri));
      const fields = records(fieldGuide.fields);
      expect(fields).toEqual(expect.arrayContaining([
        expect.objectContaining({
          name: 'name', kind: 'string', required: true,
          description: 'The project name.', example: 'Migration plan',
        }),
        expect.objectContaining({
          name: 'status', allowed_values: ['active', 'archived'], values_uri: valuesUri,
        }),
      ]));
      const fieldNames = fields.map(({ name }) => name);
      expect(fieldNames).not.toContain('response_format');
      expect(fieldNames).not.toContain('idempotency_key');
      expect(await readJsonResource(mcp, valuesUri)).toEqual({ values: [
        { value: 'active', label: 'Active' },
        { value: 'archived', label: 'Archived' },
      ] });

      const detailed = resultData(await mcp.callTool({ name: 'projects_get', arguments: {
        project_id: projectId, response_format: 'detailed',
      } }));
      expect(await readJsonResource(mcp, `app://projects/${projectId}`)).toEqual(detailed);
      await expect(readJsonResource(mcp, `app://projects/${randomUUID()}`)).rejects.toMatchObject({
        code: -32002,
        data: { kind: 'not_found', retryable: false, message: expect.any(String) },
      });
    } finally {
      await mcp.close();
    }
  });

  it('every feature has its resources, each with a description and the JSON type', async () => {
    // Audit: derives feature coverage from the real tools list and checks every advertised static
    // resource can be read as JSON. A new feature without generated resources fails without a copied inventory.
    const { key } = await addAgentKey('admin');
    const mcp = await agentClient(key);
    try {
      const tools = (await mcp.listTools()).tools;
      const features = [...new Set(tools.filter(({ name }) => name.endsWith('_search'))
        .map(({ name }) => name.slice(0, -'_search'.length)))];
      const resources = (await mcp.listResources()).resources;
      const templates = (await mcp.listResourceTemplates()).resourceTemplates;
      const resourceUris = resources.map(({ uri }) => uri);
      const templateUris = templates.map(({ uriTemplate }) => uriTemplate);

      for (const resource of resources) {
        expectSentence(resource.description);
        expect(resource.mimeType).toBe('application/json');
        await readJsonResource(mcp, resource.uri);
      }
      for (const template of templates) {
        expectSentence(template.description);
        expect(template.mimeType).toBe('application/json');
      }

      expect(features.length).toBeGreaterThan(0);
      for (const feature of features) {
        const featurePath = feature.replace(/_/g, '-');
        const getTool = tools.find(({ name }) => name === `${feature}_get`);
        const createTool = tools.find(({ name }) => name === `${feature}_create`);
        if (!getTool || !createTool) throw new Error(`The ${feature} feature is missing its get or create tool.`);
        const idFields = Object.keys(schemaProperties(getTool.inputSchema)).filter((field) => field.endsWith('_id'));
        expect(idFields).toHaveLength(1);
        expect(templateUris).toContain(`app://${featurePath}/{${idFields[0]}}`);
        expect(resourceUris).toContain(`app://${featurePath}/fields`);

        for (const [field, schema] of Object.entries(schemaProperties(createTool.inputSchema))) {
          if (field === 'response_format' || field === 'idempotency_key') continue;
          if (enumValues(schema)) expect(resourceUris).toContain(`app://${featurePath}/fields/${field}/values`);
        }
      }
    } finally {
      await mcp.close();
    }
  });

  it('the MCP server has no prompts by default', async () => {
    // Audit: protects the default prompt catalog at the public MCP boundary. A prompt registered
    // without a repeated-task request would appear here; unit tests only cover explicit definitions.
    const { key } = await addAgentKey('admin');
    const mcp = await agentClient(key);
    try {
      expect((await mcp.listPrompts()).prompts).toEqual([]);
    } finally {
      await mcp.close();
    }
  });
});
