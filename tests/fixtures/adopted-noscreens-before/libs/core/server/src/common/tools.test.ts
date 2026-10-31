import { describe, expect, it, vi } from 'vitest';
import { z } from 'zod';
import type { AccountPrincipal } from './account-principal';
import { definePermissions } from './permissions';
import { definePrompt, getPrompt, listPrompts } from './prompts';
import { listResourceTemplates, listResources, readResource } from './resources';
import { callTool, defineFeatureTools, defineTool, listTools, type ToolContext } from './tools';

const featurePermissions = definePermissions('mcp-unit-items', {
  admin: ['view', 'create', 'edit', 'delete', 'restore'],
  member: ['view', 'create', 'edit'],
});
const customPermissions = definePermissions('mcp-unit-custom', {
  admin: ['create'],
  member: [],
});
const hiddenPermissions = definePermissions('mcp-unit-hidden', {
  admin: ['view'],
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

function registerFeatureTools(feature: string, one: string, permissions: typeof featurePermissions, itemName: string) {
  defineFeatureTools({
    feature,
    one,
    api: `${feature}Api`, label: 'name',
    permissions,
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
      async list() { return { items: [row(itemName)], paging: { total: 1, totalCapped: false, nextCursor: null } }; },
      async get() { return row(itemName); },
      async create(_account: AccountPrincipal, input: { name: string }) { return row(input.name); },
      async update(_account: AccountPrincipal, _id: string, input: { name: string }) { return row(input.name); },
      async delete() {},
      async restore() { return row(itemName); },
    },
  });
}

function featureTools() {
  registerFeatureTools('mcp-unit-items', 'mcp-unit-item', featurePermissions, 'sample');
  defineTool({
    name: 'mcp_unit_items_custom',
    permission: customPermissions.create,
    description: 'Run the custom item check. Use it when the default tools do not cover this task.',
    input: z.object({}),
    output: z.object({ value: z.string() }),
    annotations: { title: 'Custom item check', readOnlyHint: true, destructiveHint: false, idempotentHint: false, openWorldHint: false },
    async call() { return { data: { value: 'ready' }, summary: 'The custom item check is ready.' }; },
  });
}

function hiddenFeatureTools() {
  registerFeatureTools('mcp-unit-hidden', 'mcp-unit-hidden-item', hiddenPermissions, 'hidden');
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
      const content = result.content[0];
      if (content.type !== 'text') throw new Error('The tool error has no text content.');
      expect(JSON.parse(content.text)).toMatchObject({
        error: { kind: 'unavailable', retryable: true, retry_after_seconds: 5 },
      });
    } finally {
      vi.useRealTimers();
    }
  });

  it('a resource read without the view permission is refused', async () => {
    // Audit: protects resource discovery and read access for a feature with an explicit role gap.
    // A resource that appears or can be read by a member would expose feature data; tool permission
    // tests do not exercise the resource registry or its read boundary.
    hiddenFeatureTools();
    expect(listResources(context('admin')).some(({ uri }) => uri === 'app://mcp-unit-hidden/fields')).toBe(true);
    expect(listResourceTemplates(context('admin')).some(({ uriTemplate }) => uriTemplate === 'app://mcp-unit-hidden/{mcp_unit_hidden_item_id}')).toBe(true);
    expect(listResources(context('member')).some(({ uri }) => uri.startsWith('app://mcp-unit-hidden/'))).toBe(false);
    expect(listResourceTemplates(context('member')).some(({ uriTemplate }) => uriTemplate.startsWith('app://mcp-unit-hidden/'))).toBe(false);

    for (const uri of [
      'app://mcp-unit-hidden/fields',
      'app://mcp-unit-hidden/07a190bf-bac2-4f33-b128-02ba72ed358a',
    ]) {
      await expect(readResource(uri, context('member'))).rejects.toMatchObject({
        code: -32002,
        data: { kind: 'not_allowed', retryable: false, message: expect.any(String) },
      });
    }
  });

  it('a tools file can add a prompt with its inputs', () => {
    // Audit: guards the public prompt definition contract: role visibility, argument requirements,
    // rendering and duplicate rejection. No prompt behavior exists in the starter to cover it yet.
    const name = 'mcp_unit_custom_review';
    definePrompt({
      name,
      permission: customPermissions.create,
      description: 'Prepare a project review. Use it when an agent needs a repeatable review request.',
      arguments: z.object({
        projectName: z.string().meta({ description: 'The project name.' }),
        status: z.string().optional().meta({ description: 'The requested status.' }),
      }).strict(),
      render: ({ projectName, status }) => `Review ${projectName} in ${status ?? 'the default'} mode.`,
    });

    const adminPrompts = listPrompts(context('admin'));
    const prompt = adminPrompts.find((entry) => entry.name === name);
    if (!prompt) throw new Error('The prompt was not listed for an allowed role.');
    expect(prompt.arguments).toEqual(expect.arrayContaining([
      expect.objectContaining({ name: 'projectName', required: true }),
      expect.objectContaining({ name: 'status', required: false }),
    ]));
    expect(listPrompts(context('member')).some((entry) => entry.name === name)).toBe(false);

    const result = getPrompt(name, { projectName: 'Atlas', status: 'archived' }, context('admin'));
    expect(result.messages).toHaveLength(1);
    expect(result.messages[0]).toMatchObject({
      role: 'user',
      content: { type: 'text', text: 'Review Atlas in archived mode.' },
    });
    expect(getPrompt(name, { projectName: 'Atlas' }, context('admin')).messages[0]).toMatchObject({
      role: 'user', content: { type: 'text', text: 'Review Atlas in the default mode.' },
    });
    expect(() => getPrompt(name, { projectName: 'Atlas' }, context('member')))
      .toThrow("Your agent account's role cannot use this prompt.");
    expect(() => getPrompt(name, {}, context('admin'))).toThrow('The prompt inputs are invalid.');
    expect(() => getPrompt(name, { projectName: 'Atlas', unexpected: true }, context('admin')))
      .toThrow('The prompt inputs are invalid.');
    expect(() => definePrompt({
      name,
      permission: customPermissions.create,
      description: 'A duplicate prompt. It cannot register twice.',
      arguments: z.object({}),
      render: () => 'Duplicate.',
    })).toThrow(`Duplicate prompt: ${name}`);
  });
});
