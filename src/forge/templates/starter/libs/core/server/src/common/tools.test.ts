import { describe, expect, it, vi } from 'vitest';
import { z } from 'zod';
import type { AccountPrincipal } from './account-principal';
import { definePermissions } from './permissions';
import { callTool, defineFeatureTools, defineTool, listTools, type ToolContext } from './tools';

const featurePermissions = definePermissions('mcp-unit-items', {
  admin: ['view', 'create', 'edit', 'delete', 'restore'],
  member: ['view', 'create', 'edit'],
});
const customPermissions = definePermissions('mcp-unit-custom', {
  admin: ['create'],
  member: [],
});

const row = (name: string) => ({
  id: '07a190bf-bac2-4f33-b128-02ba72ed358a',
  updatedAtUtc: '2026-10-27T00:00:00.000Z',
  deletedAtUtc: null,
  name,
});

function context(role: AccountPrincipal['role']): ToolContext {
  return {
    account: { id: 'account-id', email: 'agent@example.test', organisationId: 'organisation-id', role },
    deleteAndRestore: ['mcp-unit-items'],
    createOnce: async (_feature, _key, create) => create(async () => undefined),
  };
}

function featureTools() {
  defineFeatureTools({
    feature: 'mcp-unit-items',
    one: 'mcp-unit-item',
    api: 'McpUnitItemsApi', label: 'name',
    permissions: featurePermissions,
    input: z.object({ name: z.string() }),
    query: z.object({
      search: z.string().optional(),
      limit: z.coerce.number().int().default(20),
      sortBy: z.enum(['name']),
      sortOrder: z.enum(['asc', 'desc']),
      after: z.string().optional(),
      before: z.string().optional(),
    }),
    concise: ['name'],
    links: {},
    hide: ['delete'],
    service: {
      async list() { return { items: [row('sample')], paging: { total: 1, totalCapped: false, nextCursor: null } }; },
      async get() { return row('sample'); },
      async create(_account: AccountPrincipal, input: { name: string }) { return row(input.name); },
      async update(_account: AccountPrincipal, _id: string, input: { name: string }) { return row(input.name); },
      async delete() {},
      async restore() { return row('sample'); },
    },
  });
  defineTool({
    name: 'mcp_unit_items_custom',
    permission: customPermissions.create,
    description: 'Run the custom item check. Use it when the default tools do not cover this task.',
    input: z.object({}),
    output: z.object({ value: z.string() }),
    annotations: { title: 'Custom item check', readOnlyHint: true, destructiveHint: false, idempotentHint: false, openWorldHint: false },
    async call(_principal, _args) { return { data: { value: 'ready' }, summary: 'The custom item check is ready.' }; },
  });
}

describe('MCP tools', () => {
  it('a tools file can hide a default tool and add its own', async () => {
    // Audit: guards the feature registry contract for custom tools and hidden defaults. A feature
    // file that cannot hide delete, loses its custom permission, or registers a duplicate would fail;
    // HTTP contract tests cannot identify those registry-listing errors without another feature.
    featureTools();
    const admin = listTools(context('admin')).map(({ name }) => name);
    const member = listTools(context('member')).map(({ name }) => name);
    expect(admin).not.toContain('mcp_unit_items_delete');
    expect(admin).toContain('mcp_unit_items_restore');
    expect(admin).toContain('mcp_unit_items_custom');
    expect(member).not.toContain('mcp_unit_items_custom');

    expect(() => defineTool({
      name: 'mcp_unit_items_custom',
      permission: customPermissions.create,
      description: 'A duplicate custom tool. It cannot register twice.',
      input: z.object({}),
      output: z.object({ value: z.string() }),
      annotations: { title: 'Duplicate', readOnlyHint: true, destructiveHint: false, idempotentHint: false, openWorldHint: false },
      async call() { return { data: { value: 'duplicate' }, summary: 'Duplicate.' }; },
    })).toThrow('Duplicate tool: mcp_unit_items_custom');
  });

  it('a tool over its time limit gets a retryable unavailable error', async () => {
    // Audit: protects the timeout visible to agents when a tool never finishes; the public MCP
    // contract tests cover normal calls but cannot wait ten seconds to prove the deadline. Fake
    // timers let this case exercise the same callTool boundary without a production test seam.
    const stalledName = 'mcp_unit_items_stalled';
    defineTool({
      name: stalledName,
      permission: featurePermissions.view,
      description: 'Wait for a tool result. Use this only to verify the time limit.',
      input: z.object({}),
      output: z.object({ value: z.string() }),
      annotations: { title: 'Stalled tool', readOnlyHint: true, destructiveHint: false, idempotentHint: false, openWorldHint: false },
      async call() { return new Promise<never>(() => {}); },
    });

    vi.useFakeTimers();
    try {
      const resultPromise = callTool(stalledName, {}, context('member'));
      await vi.advanceTimersByTimeAsync(10_000);
      const result = await resultPromise;
      expect(result.isError).toBe(true);
      expect(result.structuredContent).toMatchObject({
        error: { kind: 'unavailable', retryable: true, retry_after_seconds: 5 },
      });
    } finally {
      vi.useRealTimers();
    }
  });
});
