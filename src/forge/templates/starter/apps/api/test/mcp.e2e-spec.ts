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
});
