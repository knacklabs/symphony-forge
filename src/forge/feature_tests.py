"""Render the API-boundary tests copied into a generated feature."""
from __future__ import annotations

import json
import re
from typing import Any


def _column(field: dict[str, Any]) -> str:
    return field.get("column", field["name"] + ("Id" if field["kind"] == "link" else ""))


def _label(value: str) -> str:
    return re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value).replace("-", " ").title()


def _field_cases(fields: list[dict[str, Any]], kinds: dict[str, Any]) -> str:
    cases = []
    for field in fields:
        definition = kinds["kinds"][field["kind"]]
        options = field.get("options", [])
        sample = definition["sample"]
        changed = definition["changed"]
        bad = definition["bad"]
        if field["kind"] == "status":
            sample = sample if sample in options else options[0]
            changed = changed if changed in options and changed != sample else next(
                (option for option in options if option != sample), sample
            )
            while bad in options:
                bad = f"{bad}_invalid"
        values = {
            "kind": field["kind"],
            "sample": sample,
            "changed": changed,
            "bad": bad,
            "optional": bool(field.get("optional")),
            "options": options,
        }
        if field.get("target") is not None:
            values["target"] = field["target"]
        cases.append(f"  {json.dumps(_column(field))}: {json.dumps(values, ensure_ascii=False)},")
    return "\n".join(cases)


def _snake(value: str) -> str:
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value).replace("-", "_").lower()


def render_mcp_cases(fields: list[dict[str, Any]], one: str, plural: str, kinds: dict[str, Any]) -> str:
    """Render the three feature-specific MCP permission and history cases."""
    root = f"/api/v1/{plural}"
    feature = plural.replace("-", "_")
    item_id = f"{_snake(one)}_id"
    display_one, display_plural = one.replace("-", " "), plural.replace("-", " ")
    label = _snake(_column(next(field for field in fields if field["kind"] == "text" and not field.get("optional"))))
    concise = [_snake(_column(field)) for field in fields if kinds["kinds"][field["kind"]]["column"]]
    numbers = [_snake(_column(field)) for field in fields
               if field["kind"] == "number" and kinds["kinds"][field["kind"]]["column"]]
    statuses = [_snake(_column(field)) for field in fields if field["kind"] == "status"]
    links = [_snake(_column(field)) for field in fields if field["kind"] == "link"]
    optional_input_fields = [_column(field) for field in fields if field.get("optional")]
    optional_fields = []
    nullable_optional_fields = []
    optional_concise_fields = []
    for field in fields:
        if not field.get("optional"):
            continue
        value = _snake(_column(field))
        optional_fields.append(value)
        if field["kind"] != "yes-no":
            nullable_optional_fields.append(value)
        if kinds["kinds"][field["kind"]]["column"] or field["kind"] == "link":
            optional_concise_fields.append(value)
        if field["kind"] == "link":
            name = value[:-3] + "_name" if value.endswith("_id") else value + "_name"
            optional_fields.append(name)
            nullable_optional_fields.append(name)
            optional_concise_fields.append(name)
        if field["kind"] == "status":
            label_field = value + "_label"
            optional_fields.append(label_field)
            nullable_optional_fields.append(label_field)
            if kinds["kinds"][field["kind"]]["column"]:
                optional_concise_fields.append(label_field)
    detail_only = [_snake(_column(field)) for field in fields
                   if not kinds["kinds"][field["kind"]]["column"] and field["kind"] != "link"]
    filter_fields = [field for field in fields if field["kind"] in ("link", "yes-no")
                     or (field["kind"] == "status" and len(field.get("options", [])) > 1)]
    filter_cases = []
    for field in filter_fields:
        column = _column(field)
        arg = _snake(column)
        if field["kind"] == "status":
            change_filter = (
                f"excludedInput[{json.dumps(column)}] = FIELD_CASES[{json.dumps(column)}].options"
                f".find((option) => option !== matchingInput[{json.dumps(column)}])!;"
            )
            filter_value = f"matchingInput[{json.dumps(column)}]"
        elif field["kind"] == "yes-no":
            change_filter = f"excludedInput[{json.dumps(column)}] = !(matchingInput[{json.dumps(column)}] as boolean);"
            filter_value = f"matchingInput[{json.dumps(column)}] ? 'yes' : 'no'"
        else:
            change_filter = (
                f"excludedInput[{json.dumps(column)}] = await linkedItem(client, csrf, "
                f"FIELD_CASES[{json.dumps(column)}].target as string, `${{mark}}-other-{arg}`);"
            )
            filter_value = f"matchingInput[{json.dumps(column)}]"
        filter_cases.append(f'''      {{
        const mark = randomUUID();
        const matchingInput = await featureInput(client, csrf, mark, 'sample');
        const excludedInput = {{ ...matchingInput }};
        {change_filter}
        const matchingItem = resultData(await mcp.callTool({{ name: '@@FEATURE@@_create', arguments: featureArguments(matchingInput) }}));
        const excludedItem = resultData(await mcp.callTool({{ name: '@@FEATURE@@_create', arguments: featureArguments(excludedInput) }}));
        const filtered = resultData(await mcp.callTool({{ name: '@@FEATURE@@_search', arguments: {{
          query: mark, {json.dumps(arg)}: {filter_value},
        }} }}));
        const filteredIds = (filtered.items as Record<string, unknown>[]).map((item) => item['@@ITEM_ID@@']);
        expect(filteredIds).toContain(matchingItem['@@ITEM_ID@@']);
        expect(filteredIds).not.toContain(excludedItem['@@ITEM_ID@@']);
      }}''')
    filter_cases_text = "\n".join(filter_cases)
    optional_case = ""
    if optional_fields:
        optional_case = r'''  it('omitted optional fields stay valid in concise and detailed MCP results', async () => {
    // Audit: protects nullable service responses at the real MCP boundary for every optional feature field.
    // Omission is accepted by the API but returns null from storage; REST tests cannot catch MCP output parsing, and no test-only production seam is used.
    const { client, csrf } = await signedIn();
    const memberPermissions = await featurePermissions(client, 'member');
    const role = FEATURE_MAIN_ACTIONS.every((action) => memberPermissions.includes(FEATURE_PERMISSIONS[action]))
      ? 'member' : 'admin';
    const permissions = role === 'member' ? memberPermissions : await featurePermissions(client, 'admin');
    const { mcp } = await featureAgent(client, csrf, role);
    const mark = randomUUID();
    try {
      expect((await mcp.listTools()).tools.filter((tool) => tool.name.startsWith('@@FEATURE@@_')).map((tool) => tool.name))
        .toEqual(featureToolNames(permissions));
      const optionalInput = await featureInput(client, csrf, mark, 'sample');
      for (const field of FEATURE_OPTIONAL_INPUT_FIELDS) delete optionalInput[field];
      const input = featureArguments(optionalInput);

      const createdResult = await mcp.callTool({ name: '@@FEATURE@@_create', arguments: input });
      expect(('isError' in createdResult) ? createdResult.isError : false).toBe(false);
      const created = resultData(createdResult);
      const id = String(created['@@ITEM_ID@@']);
      const fetchedResult = await mcp.callTool({ name: '@@FEATURE@@_get', arguments: { '@@ITEM_ID@@': id } });
      expect(('isError' in fetchedResult) ? fetchedResult.isError : false).toBe(false);
      const fetched = resultData(fetchedResult);
      const searchedResult = await mcp.callTool({ name: '@@FEATURE@@_search', arguments: { query: mark } });
      expect(('isError' in searchedResult) ? searchedResult.isError : false).toBe(false);
      const searched = resultData(searchedResult);
      const conciseSearchItem = (searched.items as Record<string, unknown>[])
        .find((item) => item['@@ITEM_ID@@'] === id);
      expect(conciseSearchItem).toBeDefined();
      const detailedGetResult = await mcp.callTool({ name: '@@FEATURE@@_get', arguments: {
        '@@ITEM_ID@@': id, response_format: 'detailed',
      } });
      expect(('isError' in detailedGetResult) ? detailedGetResult.isError : false).toBe(false);
      const detailedGet = resultData(detailedGetResult);
      const detailedSearchResult = await mcp.callTool({ name: '@@FEATURE@@_search', arguments: {
        query: mark, response_format: 'detailed',
      } });
      expect(('isError' in detailedSearchResult) ? detailedSearchResult.isError : false).toBe(false);
      const detailedSearch = resultData(detailedSearchResult);
      const detailedSearchItem = (detailedSearch.items as Record<string, unknown>[])
        .find((item) => item['@@ITEM_ID@@'] === id);
      expect(detailedSearchItem).toBeDefined();

      for (const row of [created, fetched, conciseSearchItem ?? {}]) {
        for (const field of FEATURE_OPTIONAL_CONCISE_FIELDS) {
          expect(row).toHaveProperty(field, FEATURE_OPTIONAL_NULL_FIELDS.includes(field) ? null : false);
        }
        for (const field of FEATURE_DETAIL_ONLY_FIELDS) expect(row).not.toHaveProperty(field);
      }
      for (const row of [detailedGet, detailedSearchItem ?? {}]) {
        for (const field of FEATURE_OPTIONAL_FIELDS) {
          expect(row).toHaveProperty(field, FEATURE_OPTIONAL_NULL_FIELDS.includes(field) ? null : false);
        }
        for (const field of FEATURE_DETAIL_ONLY_FIELDS) expect(row).toHaveProperty(field);
      }
      const nullableInputField = FEATURE_OPTIONAL_INPUT_FIELDS
        .map((field) => field.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`))
        .find((field) => FEATURE_OPTIONAL_NULL_FIELDS.includes(field));
      if (nullableInputField) {
        const invalid = await mcp.callTool({ name: '@@FEATURE@@_create', arguments: { ...input, [nullableInputField]: null } });
        expect(resultError(invalid)).toMatchObject({ kind: 'invalid_input', retryable: false });
      }
    } finally {
      await mcp.close();
    }
  });
'''
    deleted_link_case = ""
    if any(field["kind"] == "link" for field in fields):
        link_checks = []
        for field in fields:
            if field["kind"] != "link":
                continue
            column = _column(field)
            arg = _snake(column)
            target = field["target"]
            target_feature = target.replace("-", "_")
            target_view = f"{target}.view"
            target_restore = f"{target}.restore"
            link_name = arg[:-3] + "_name" if arg.endswith("_id") else arg + "_name"
            link_checks.append(f'''      {{
        const mark = randomUUID();
        const targetId = await linkedItem(client, csrf, {json.dumps(target)}, `${{mark}}-{arg}`);
        const input = await featureInput(client, csrf, mark, 'sample');
        input[{json.dumps(column)}] = targetId;
        const parent = await client.post('@@ROOT@@').set('x-csrf-token', csrf).send(input).expect(201);
        const parentId = parent.body.data.id as string;
        await client.delete(`/api/v1/{target}/${{targetId}}`).set('x-csrf-token', csrf).expect(200);
        const canReadDeletedTarget = memberPermissions.includes({json.dumps(target_view)})
          && memberPermissions.includes({json.dumps(target_restore)});
        const expectedName = canReadDeletedTarget
          ? expect.any(String) : null;

        const fetchedResult = await mcp.callTool({{ name: '@@FEATURE@@_get', arguments: {{ '@@ITEM_ID@@': parentId }} }});
        expect(('isError' in fetchedResult) ? fetchedResult.isError : false).toBe(false);
        const fetched = resultData(fetchedResult);
        expect(fetched).toMatchObject({{ {arg}: targetId, {link_name}: expectedName }});
        const searchedResult = await mcp.callTool({{ name: '@@FEATURE@@_search', arguments: {{ query: mark }} }});
        expect(('isError' in searchedResult) ? searchedResult.isError : false).toBe(false);
        const searched = resultData(searchedResult);
        expect(searched.items).toEqual(expect.arrayContaining([
          expect.objectContaining({{ '@@ITEM_ID@@': parentId, {arg}: targetId, {link_name}: expectedName }}),
        ]));

        const availableTools = (await mcp.listTools()).tools;
        if (memberPermissions.includes({json.dumps(target_view)})) {{
          const targetPrefix = {json.dumps(target_feature)};
          const targetTool = availableTools.find((tool) => tool.name === `${{targetPrefix}}_get`);
          if (!targetTool) throw new Error('The linked feature get tool is missing for a permitted role.');
          const properties = (targetTool.inputSchema as {{ properties?: Record<string, unknown> }}).properties ?? {{}};
          const targetIdField = Object.keys(properties).find((property) => property.endsWith('_id'));
          if (!targetIdField) throw new Error('The linked feature get tool has no id field.');
          const targetResult = await mcp.callTool({{ name: `${{targetPrefix}}_get`, arguments: {{ [targetIdField]: targetId }} }});
          if (canReadDeletedTarget) expect(resultData(targetResult)[targetIdField]).toBe(targetId);
          else expect(resultError(targetResult)).toMatchObject({{ kind: 'not_found', retryable: false }});
        }} else expect(availableTools.map((tool) => tool.name)).not.toContain({json.dumps(target_feature + '_get')});
            }}''')
        deleted_link_case = f'''  it('a deleted linked item does not stop parent reads or bypass the member role', async () => {{
    // Audit: protects parent reads through MCP when a link target is no longer readable to this member.
    // Deleted targets must not fail the parent response or bypass target permissions; REST tests cannot reach MCP name resolution, and no test-only production seam is used.
    const {{ client, csrf }} = await signedIn();
    const memberPermissions = await featurePermissions(client, 'member');
    const {{ mcp }} = await featureAgent(client, csrf, 'member');
    try {{
      if (!memberPermissions.includes(FEATURE_PERMISSIONS.view)) {{
        expect((await mcp.listTools()).tools.map((tool) => tool.name)).not.toContain('@@FEATURE@@_get');
        return;
      }}
{chr(10).join(link_checks)}
    }} finally {{
      await mcp.close();
    }}
  }});
'''
    template = r'''describe('@@PLURAL@@ MCP tools', () => {
  async function featureAgent(client: ApiClient, csrf: string, role: 'admin' | 'member') {
    const name = `feature-${randomUUID().slice(0, 8)}`;
    const added = await client.post('/api/v1/agents').set('x-csrf-token', csrf)
      .send({ name, role }).expect(201);
    const agent = added.body.data as { accountId: string; email: string };
    const key = (await client.post(`/api/v1/members/${agent.accountId}/key`)
      .set('x-csrf-token', csrf).expect(201)).body.data.key as string;
    return { email: agent.email, mcp: await agentClient(key) };
  }

  function featureArguments(input: Record<string, unknown>): Record<string, unknown> {
    return Object.fromEntries(Object.entries(input).map(([field, value]) => [
      field.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`), value,
    ]));
  }

  function resultData(result: { isError?: boolean; structuredContent?: Record<string, unknown> }): Record<string, unknown> {
    if (result.isError || !result.structuredContent) throw new Error('The MCP tool call failed.');
    return result.structuredContent;
  }

  function resultError(result: { isError?: boolean; content?: unknown }): Record<string, unknown> {
    if (!result.isError || !Array.isArray(result.content) || result.content[0]?.type !== 'text') {
      throw new Error('The MCP tool did not return an error.');
    }
    const data = JSON.parse(result.content[0].text);
    if (typeof data.error !== 'object' || data.error === null) throw new Error('The MCP tool did not return an error.');
    return data.error as Record<string, unknown>;
  }

  function expectFeatureFields(actual: Record<string, unknown>, input: Record<string, unknown>, detailed = false): void {
    for (const field of FEATURE_CONCISE_FIELDS) {
      if (FEATURE_NUMBER_FIELDS.includes(field)) expect(Number(actual[field])).toBe(Number(input[field]));
      else expect(actual[field]).toEqual(input[field]);
    }
    for (const field of FEATURE_STATUS_FIELDS) {
      if (!detailed && !FEATURE_CONCISE_FIELDS.includes(field)) continue;
      const value = String(input[field]);
      expect(actual[`${field}_label`]).toBe(value.charAt(0).toUpperCase() + value.slice(1).replace(/-/g, ' '));
    }
    for (const field of FEATURE_LINK_FIELDS) {
      const nameField = field.endsWith('_id') ? `${field.slice(0, -3)}_name` : `${field}_name`;
      expect(typeof actual[nameField]).toBe('string');
      expect(actual[nameField]).not.toBe(input[field]);
    }
    if (detailed) {
      for (const [column, definition] of Object.entries(FIELD_CASES)) {
        const field = column.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
        if (FEATURE_CONCISE_FIELDS.includes(field)) continue;
        if (definition.kind === 'number') expect(Number(actual[field])).toBe(Number(input[field]));
        else expect(actual[field]).toEqual(input[field]);
      }
    }
  }

  const FEATURE_CONCISE_FIELDS: string[] = @@CONCISE@@;
  const FEATURE_NUMBER_FIELDS: string[] = @@NUMBERS@@;
  const FEATURE_STATUS_FIELDS: string[] = @@STATUSES@@;
  const FEATURE_LINK_FIELDS: string[] = @@LINKS@@;
  const FEATURE_OPTIONAL_INPUT_FIELDS: string[] = @@OPTIONAL_INPUT@@;
  const FEATURE_OPTIONAL_FIELDS: string[] = @@OPTIONAL@@;
  const FEATURE_OPTIONAL_NULL_FIELDS: string[] = @@OPTIONAL_NULL@@;
  const FEATURE_OPTIONAL_CONCISE_FIELDS: string[] = @@OPTIONAL_CONCISE@@;
  const FEATURE_DETAIL_ONLY_FIELDS: string[] = @@DETAIL_ONLY@@;
  const FEATURE_PERMISSIONS = {
    view: '@@SLUG@@.view', create: '@@SLUG@@.create', edit: '@@SLUG@@.edit',
    delete: '@@SLUG@@.delete', restore: '@@SLUG@@.restore',
  };
  const FEATURE_MAIN_ACTIONS = ['view', 'create', 'edit'] as const;
  const FEATURE_TOOL_ACTIONS: { action: string; permission: keyof typeof FEATURE_PERMISSIONS }[] = [
    { action: 'search', permission: 'view' }, { action: 'get', permission: 'view' },
    { action: 'create', permission: 'create' }, { action: 'update', permission: 'edit' },
    { action: 'delete', permission: 'delete' }, { action: 'restore', permission: 'restore' },
  ];

  function featureToolNames(permissions: readonly string[], includeDeleteAndRestore = false): string[] {
    return FEATURE_TOOL_ACTIONS.filter(({ action, permission }) => permissions.includes(FEATURE_PERMISSIONS[permission])
      && (includeDeleteAndRestore || (action !== 'delete' && action !== 'restore')))
      .map(({ action }) => `@@FEATURE@@_${action}`);
  }

  async function featurePermissions(client: ApiClient, role: 'admin' | 'member'): Promise<string[]> {
    if (role === 'member') return (await sharedMemberSignedIn()).permissions;
    return (await client.get('/api/v1/auth/me').expect(200)).body.data.permissions as string[];
  }

  async function featureRoleForMainActions(client: ApiClient): Promise<'admin' | 'member'> {
    const permissions = await featurePermissions(client, 'member');
    return FEATURE_MAIN_ACTIONS.every((action) => permissions.includes(FEATURE_PERMISSIONS[action]))
      ? 'member' : 'admin';
  }

  it('an agent searches, reads, creates and updates @@PLURAL@@ through MCP as its account', async () => {
    const { client, csrf } = await signedIn();
    const role = await featureRoleForMainActions(client);
    const permissions = await featurePermissions(client, role);
    const { email, mcp } = await featureAgent(client, csrf, role);
    try {
      const listed = await mcp.listTools();
      expect(listed.tools.filter((tool) => tool.name.startsWith('@@FEATURE@@_')).map((tool) => tool.name))
        .toEqual(featureToolNames(permissions));

      const mark = randomUUID();
      const input = featureArguments(await featureInput(client, csrf, mark, 'sample'));
      const created = await mcp.callTool({ name: '@@FEATURE@@_create', arguments: input });
      expect(created.content).toEqual([{ type: 'text', text: `Created the @@ONE@@ ${String(input['@@LABEL@@'])}.` }]);
      const createdData = resultData(created);
      const id = String(createdData['@@ITEM_ID@@']);
      expect(id).toMatch(/^[0-9a-f-]{36}$/i);
      expectFeatureFields(createdData, input);
      expect(createdData).not.toHaveProperty('created_by_email');

      const fetched = resultData(await mcp.callTool({ name: '@@FEATURE@@_get', arguments: { '@@ITEM_ID@@': id } }));
      expectFeatureFields(fetched, input);
      expect(fetched).not.toHaveProperty('created_by_email');
      const detailed = resultData(await mcp.callTool({ name: '@@FEATURE@@_get', arguments: {
        '@@ITEM_ID@@': id, response_format: 'detailed',
      } }));
      expect(detailed.created_by_email).toBe(email);
      expectFeatureFields(detailed, input, true);
      for (const field of FEATURE_DETAIL_ONLY_FIELDS) {
        expect(createdData).not.toHaveProperty(field);
        expect(detailed).toHaveProperty(field);
      }

      const searched = resultData(await mcp.callTool({ name: '@@FEATURE@@_search', arguments: { query: mark } }));
      expect(searched.items).toEqual(expect.arrayContaining([
        expect.objectContaining({ '@@ITEM_ID@@': id }),
      ]));
      expect(searched.items).not.toEqual(expect.arrayContaining([
        expect.objectContaining({ created_by_email: expect.any(String) }),
      ]));
      const found = (searched.items as Record<string, unknown>[]).find((item) => item['@@ITEM_ID@@'] === id);
      expect(found).toBeDefined();
      if (found) {
        expectFeatureFields(found, input);
        expect(found).not.toHaveProperty('created_by_email');
      }
      const detailedSearch = resultData(await mcp.callTool({ name: '@@FEATURE@@_search', arguments: {
        query: mark, response_format: 'detailed',
      } }));
      const detailedFound = (detailedSearch.items as Record<string, unknown>[])
        .find((item) => item['@@ITEM_ID@@'] === id);
      expect(detailedFound).toBeDefined();
      if (detailedFound) expectFeatureFields(detailedFound, input, true);

      const changedInput = featureArguments(await featureInput(client, csrf, mark, 'changed'));
      const updated = resultData(await mcp.callTool({ name: '@@FEATURE@@_update', arguments: {
        ...changedInput, '@@ITEM_ID@@': id,
      } }));
      expectFeatureFields(updated, changedInput);
      expect(updated).not.toHaveProperty('created_by_email');

      for (const [field, value] of Object.entries(FIELD_CASES)) {
        const argument = field.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
        const rejected = await mcp.callTool({ name: '@@FEATURE@@_create', arguments: {
          ...input, [argument]: value.bad,
        } });
        expect(rejected.isError).toBe(true);
        const error = resultError(rejected);
        expect(error).toMatchObject({ kind: 'invalid_input', retryable: false });
        expect(String(error.message)).toContain('Example:');
        expect(error.details).toEqual(expect.arrayContaining([expect.objectContaining({ field: argument })]));
      }

      const changes = (await client.get(`@@ROOT@@/${id}/changes`).expect(200)).body.data as
        { actorEmail: string; summary: string }[];
      expect(changes).toEqual(expect.arrayContaining([
        expect.objectContaining({ actorEmail: email, summary: 'Created the @@ONE@@' }),
        expect.objectContaining({ actorEmail: email, summary: expect.stringContaining(' changed from ') }),
      ]));
      const history = (await client.get('/api/v1/history').expect(200)).body.data as
        { actorEmail: string; summary: string }[];
      const agentChanges = history.filter((entry) => entry.actorEmail === email
        && (entry.summary.includes('Created the @@ONE@@') || entry.summary.includes(' changed from ')));
      expect(agentChanges).toHaveLength(2);
      // Audit: protects permission-filtered MCP discovery and filters plus concise/detailed projections.
      // Hard-coded role grants or ignored filters/missing fields would fail; REST tests cannot reach MCP list/call behavior, and no test-only production seam is used.
@@FILTER_CASES@@
    } finally {
      await mcp.close();
    }
  });

@@OPTIONAL_CASE@@

@@DELETED_LINK_CASE@@

  it('a member agent cannot delete or restore a @@ONE@@ through MCP', async () => {
    const { client, csrf } = await signedIn();
    const memberPermissions = await featurePermissions(client, 'member');
    const { mcp } = await featureAgent(client, csrf, 'member');
    try {
      await client.put('/api/v1/agent-tools/@@SLUG@@').set('x-csrf-token', csrf)
        .send({ deleteAndRestore: true }).expect(200);
      const mark = randomUUID();
      const id = await createFeature(client, csrf, await featureInput(client, csrf, mark, 'sample'));
      const listed = await mcp.listTools();
      const names = listed.tools.filter((tool) => tool.name.startsWith('@@FEATURE@@_')).map((tool) => tool.name);
      expect(names).toEqual(featureToolNames(memberPermissions, true));
      for (const action of ['delete', 'restore']) {
        const result = await mcp.callTool({ name: `@@FEATURE@@_${action}`, arguments: { '@@ITEM_ID@@': id } });
        const permission = FEATURE_PERMISSIONS[action as 'delete' | 'restore'];
        if (memberPermissions.includes(permission)) expect(result.isError).not.toBe(true);
        else expect(resultError(result)).toMatchObject({ kind: 'not_allowed', retryable: false });
      }
      const after = await client.get(`@@ROOT@@/${id}`).expect(200);
      if (memberPermissions.includes(FEATURE_PERMISSIONS.delete)
        && !memberPermissions.includes(FEATURE_PERMISSIONS.restore)) {
        expect(after.body.data.deletedAtUtc).toEqual(expect.any(String));
      } else expect(after.body.data.deletedAtUtc).toBeNull();
    } finally {
      await mcp.close();
    }
  });

  it('@@ONE@@ delete and restore tools stay off until an admin turns them on', async () => {
    const { client, csrf } = await signedIn();
    const adminPermissions = await featurePermissions(client, 'admin');
    const { email, mcp } = await featureAgent(client, csrf, 'admin');
    try {
      expect((await mcp.listTools()).tools.filter((tool) => tool.name.startsWith('@@FEATURE@@_')).map((tool) => tool.name))
        .toEqual(featureToolNames(adminPermissions));
      const mark = randomUUID();
      const id = await createFeature(client, csrf, await featureInput(client, csrf, mark, 'sample'));
      const refused = await mcp.callTool({ name: '@@FEATURE@@_delete', arguments: { '@@ITEM_ID@@': id } });
      expect(refused.isError).toBe(true);
      expect(resultError(refused)).toMatchObject({
        kind: 'not_allowed', retryable: false,
      });

      await client.put('/api/v1/agent-tools/@@SLUG@@').set('x-csrf-token', csrf)
        .send({ deleteAndRestore: true }).expect(200);
      expect((await mcp.listTools()).tools.filter((tool) => tool.name.startsWith('@@FEATURE@@_')).map((tool) => tool.name))
        .toEqual(featureToolNames(adminPermissions, true));
      for (let attempt = 0; attempt < 2; attempt += 1) {
        expect(resultData(await mcp.callTool({ name: '@@FEATURE@@_delete', arguments: { '@@ITEM_ID@@': id } })).deleted)
          .toBe(true);
      }
      for (let attempt = 0; attempt < 2; attempt += 1) {
        expect(resultData(await mcp.callTool({ name: '@@FEATURE@@_restore', arguments: { '@@ITEM_ID@@': id } }))['@@ITEM_ID@@'])
          .toBe(id);
      }
      const changes = (await client.get(`@@ROOT@@/${id}/changes`).expect(200)).body.data as
        { actorEmail: string; summary: string }[];
      const deleted = changes.filter((entry) => entry.summary === 'Deleted the @@ONE@@');
      const restored = changes.filter((entry) => entry.summary === 'Restored the @@ONE@@');
      expect(deleted).toHaveLength(1);
      expect(deleted[0].actorEmail).toBe(email);
      expect(restored).toHaveLength(1);
      expect(restored[0].actorEmail).toBe(email);

      await client.put('/api/v1/agent-tools/@@SLUG@@').set('x-csrf-token', csrf)
        .send({ deleteAndRestore: false }).expect(200);
      expect((await mcp.listTools()).tools.filter((tool) => tool.name.startsWith('@@FEATURE@@_')).map((tool) => tool.name))
        .toEqual(featureToolNames(adminPermissions));
    } finally {
      await mcp.close();
    }
  });
});
'''
    template = template.replace("@@FILTER_CASES@@", filter_cases_text)
    template = template.replace("@@OPTIONAL_CASE@@", optional_case)
    template = template.replace("@@DELETED_LINK_CASE@@", deleted_link_case)
    replacements = {
        "@@PLURAL@@": display_plural,
        "@@SLUG@@": plural,
        "@@ONE@@": display_one,
        "@@ROOT@@": root,
        "@@FEATURE@@": feature,
        "@@ITEM_ID@@": item_id,
        "@@CONCISE@@": json.dumps(concise),
        "@@NUMBERS@@": json.dumps(numbers),
        "@@STATUSES@@": json.dumps(statuses),
        "@@LINKS@@": json.dumps(links),
        "@@OPTIONAL_INPUT@@": json.dumps(optional_input_fields),
        "@@OPTIONAL@@": json.dumps(optional_fields),
        "@@OPTIONAL_NULL@@": json.dumps(nullable_optional_fields),
        "@@OPTIONAL_CONCISE@@": json.dumps(optional_concise_fields),
        "@@DETAIL_ONLY@@": json.dumps(detail_only),
        "@@LABEL@@": label,
    }
    for marker, value in replacements.items():
        template = template.replace(marker, value)
    return template.strip()


def _target_helper(fields: list[dict[str, Any]]) -> str:
    if not any(field["kind"] == "link" for field in fields):
        return ""
    return r'''let featureDocs: request.Response | undefined;
async function docs(): Promise<request.Response> {
  featureDocs ??= await request(apiBaseUrl).get('/api/docs-json').expect(200);
  return featureDocs;
}

async function linkedItem(
  client: ApiClient,
  csrf: string,
  target: string,
  mark: string,
): Promise<string> {
  const openapi = await docs();
  const schema = requestBodySchema(openapi, `/api/v1/${target}`, 'post');
  const properties = schema.properties as Record<string, Record<string, unknown>>;
  const input: Record<string, unknown> = {};
  for (const name of schema.required as string[]) {
    const property = properties[name];
    const values = property.enum;
    const linkDescription = typeof property.description === 'string' ? property.description : '';
    const linkedTarget = /^The linked item from (.+)\.$/.exec(linkDescription)?.[1];
    let value: unknown = property.example;
    if (linkedTarget) {
      value = await linkedItem(client, csrf, linkedTarget, `${mark}-${name}`);
    } else if (Array.isArray(values) && values.length > 0) value = values[0];
    else if (typeof value === 'undefined') {
      value = property.format === 'email' ? `${mark}@example.test`
        : property.type === 'boolean' ? false
          : property.type === 'number' || property.type === 'integer' ? 1
            : `Linked ${mark}`;
    }
    if (!linkedTarget && name.toLowerCase().includes('name')) value = `Linked ${mark}`;
    input[name] = value;
  }
  const response = await client.post(`/api/v1/${target}`).set('x-csrf-token', csrf).send(input).expect(201);
  return response.body.data.id as string;
}'''


def render_api_tests(
    fields: list[dict[str, Any]], one: str, plural: str, kinds: dict[str, Any]
) -> str:
    """Return the generated feature's HTTP tests, using the kind table as test data."""
    text_fields = [field for field in fields if field["kind"] == "text" and not field.get("optional")]
    search_fields = [field for field in fields if field["kind"] in ("text", "email")]
    if not text_fields or not search_fields:
        raise ValueError("Generated feature API tests need a text field and a searchable field.")

    root = f"/api/v1/{plural}"
    primary = _column(text_fields[0])
    primary_label = _label(text_fields[0]["name"])
    has_link = any(field["kind"] == "link" for field in fields)
    field_cases = _field_cases(fields, kinds)
    target_helper = _target_helper(fields)
    link_case = ""
    if has_link:
        link_fields = [field for field in fields if field["kind"] == "link"]
        link_checks = []
        for field in link_fields:
            column = _column(field)
            target = field["target"]
            link_checks.append(f'''    {{
      const {column} = await linkedItem(client, csrf, {json.dumps(target)}, `${{mark}}-{column}`);
      const other{column[0].upper() + column[1:]} = await linkedItem(otherClient, otherCsrf, {json.dumps(target)}, `other-${{mark}}-{column}`);
      const deleted{column[0].upper() + column[1:]} = await linkedItem(client, csrf, {json.dumps(target)}, `deleted-${{mark}}-{column}`);
      await client.delete(`/api/v1/{target}/${{deleted{column[0].upper() + column[1:]}}}`).set('x-csrf-token', csrf).expect(200);
      const linkedInput = await featureInput(client, csrf, mark, 'sample');
      linkedInput[{json.dumps(column)}] = {column};
      await client.post('{root}').set('x-csrf-token', csrf).send(linkedInput).expect(201);
      const crossOrganisation = {{ ...linkedInput, [{json.dumps(column)}]: other{column[0].upper() + column[1:]} }};
      const crossRefused = await client.post('{root}').set('x-csrf-token', csrf).send(crossOrganisation).expect(400);
      expect(crossRefused.body.error.details.fieldErrors).toEqual(expect.arrayContaining([expect.objectContaining({{ field: {json.dumps(column)} }})]));
      const deletedLink = {{ ...linkedInput, [{json.dumps(column)}]: deleted{column[0].upper() + column[1:]} }};
      const deletedRefused = await client.post('{root}').set('x-csrf-token', csrf).send(deletedLink).expect(400);
      expect(deletedRefused.body.error.details.fieldErrors).toEqual(expect.arrayContaining([expect.objectContaining({{ field: {json.dumps(column)} }})]));
    }}''')
        link_case = f'''  it('checks linked items through their public API', async () => {{
    const {{ client, csrf }} = await sharedSignedIn();
    const other = credentials();
    const otherClient = request.agent(apiBaseUrl);
    const otherJoined = await otherClient.post('/api/v1/auth/sign-up').send(other).expect(201);
    const otherCsrf = csrfToken(otherJoined);
    const mark = randomUUID();
{chr(10).join(link_checks)}
  }});
'''

    filter_fields = [field for field in fields if field["kind"] in ("status", "link", "yes-no")]
    filter_check_lines = []
    for field in filter_fields:
        column, kind = _column(field), field["kind"]
        alternate = ""
        if kind == "status":
            options = field.get("options", [])
            if len(options) < 2:
                continue
            alternate = (
                f"other[{json.dumps(column)}] = FIELD_CASES[{json.dumps(column)}].options"
                f".find((option) => option !== matching[{json.dumps(column)}])!;"
            )
        elif kind == "yes-no":
            alternate = f"other[{json.dumps(column)}] = !(matching[{json.dumps(column)}] as boolean);"
        else:
            alternate = (
                f"other[{json.dumps(column)}] = await linkedItem(client, csrf, "
                f"FIELD_CASES[{json.dumps(column)}].target as string, `${{mark}}-other-{column}`);"
            )
        query_value = (
            f"String(matching[{json.dumps(column)}])" if kind != "yes-no"
            else "matching[" + json.dumps(column) + "] ? 'yes' : 'no'"
        )
        filter_check_lines.append(f'''    {{
      const mark = randomUUID();
      const matching = await featureInput(client, csrf, mark, 'sample');
      const other = {{ ...matching }};
      {alternate}
      const id = await createFeature(client, csrf, matching);
      await createFeature(client, csrf, other);
      const response = await client.get(`{root}?search=${{mark}}&{column}=${{encodeURIComponent({query_value})}}`).expect(200);
      expect(featureItems(response).map((item) => item.id)).toEqual([id]);
      const exported = await client.get(`{root}/export?search=${{mark}}&{column}=${{encodeURIComponent({query_value})}}`).expect(200);
      expect(exported.text.trim().split(/\\r?\\n/)).toHaveLength(2);
    }}''')

    filter_cases = "\n".join(filter_check_lines)
    sortable = [(_column(field), field) for field in fields if field["kind"] != "long-text"] + [
        ("createdAtUtc", None), ("updatedAtUtc", None),
    ]
    sort_fields = ",\n  ".join(json.dumps(column) for column, _ in sortable) + ","
    bad_cases = "\n".join(
        f'''    {{
      const body = await featureInput(client, csrf, randomUUID(), 'sample');
      body[{json.dumps(_column(field))}] = FIELD_CASES[{json.dumps(_column(field))}].bad;
      const refused = await client.post('{root}').set('x-csrf-token', csrf).send(body).expect(400);
      expect(refused.body.error.details.fieldErrors).toEqual(expect.arrayContaining([expect.objectContaining({{ field: {json.dumps(_column(field))} }})]));
    }}'''
        for field in fields
    )

    template = r'''type ApiClient = ReturnType<typeof request.agent>;
type FeatureFieldCase = { kind: string; sample: unknown; changed: unknown; bad: unknown; optional: boolean; options: string[]; target?: string };
type FeatureItem = Record<string, unknown> & { id: string };

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

let sharedAccount: Promise<{ client: ApiClient; csrf: string }> | undefined;
function sharedSignedIn() {
  sharedAccount ??= signedIn();
  return sharedAccount;
}

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

const FIELD_CASES: Record<string, FeatureFieldCase> = {
@@FIELD_CASES@@
};
const FEATURE_PERMISSIONS = {
  view: '@@PLURAL@@.view', create: '@@PLURAL@@.create', edit: '@@PLURAL@@.edit',
  delete: '@@PLURAL@@.delete', restore: '@@PLURAL@@.restore',
};

@@TARGET_HELPER@@

async function featureInput(
  client: ApiClient,
  csrf: string,
  mark: string,
  mode: 'sample' | 'changed' | 'sort' = 'sample',
  variant = 0,
  nullColumn = '',
): Promise<Record<string, unknown>> {
  const input: Record<string, unknown> = {};
  for (const [column, field] of Object.entries(FIELD_CASES)) {
    if (mode === 'sort' && variant === 3 && column === nullColumn && field.optional && field.kind !== 'yes-no') continue;
    let value = mode === 'changed' ? field.changed : field.sample;
    if (field.kind === 'link') {
@@LINK_INPUT@@
    } else if (mode === 'sort') {
      if (field.kind === 'text' || field.kind === 'long-text') value = `${String(field.sample)} ${mark}-${variant}`;
      else if (field.kind === 'email') value = `${mark}-${variant}@example.test`;
      else if (field.kind === 'number') value = (Number(field.sample) + variant).toFixed(4);
      else if (field.kind === 'money') value = Number(field.sample) + variant;
      else if (field.kind === 'date') {
        const date = new Date(`${String(field.sample)}T00:00:00.000Z`);
        date.setUTCDate(date.getUTCDate() + variant);
        value = date.toISOString().slice(0, 10);
      } else if (field.kind === 'yes-no') value = variant % 2 === 1;
      else if (field.kind === 'status') value = field.options[variant % field.options.length];
    } else if (field.kind === 'text' || field.kind === 'long-text') value = `${String(value)} ${mark}`;
    else if (field.kind === 'email') value = `${String(value).split('@')[0]}-${mark}@example.test`;
    input[column] = value;
  }
  return input;
}

async function createFeature(client: ApiClient, csrf: string, input: Record<string, unknown>): Promise<string> {
  const response = await client.post('@@ROOT@@').set('x-csrf-token', csrf).send(input).expect(201);
  return response.body.data.id as string;
}

function featureItems(response: request.Response): FeatureItem[] {
  return response.body.data.items as FeatureItem[];
}

function compareValues(left: unknown, right: unknown, order: 'asc' | 'desc', kind = 'text'): number {
  let result = 0;
  if (left === null || left === undefined) result = right === null || right === undefined ? 0 : 1;
  else if (right === null || right === undefined) result = -1;
  else if (kind === 'number' || kind === 'money') result = Number(left) - Number(right);
  else if (typeof left === 'boolean' && typeof right === 'boolean') result = Number(left) - Number(right);
  else result = String(left) < String(right) ? -1 : String(left) > String(right) ? 1 : 0;
  if (left === null || left === undefined || right === null || right === undefined) return result;
  return order === 'asc' ? result : -result;
}

function expectFeatureValues(actual: Record<string, unknown>, input: Record<string, unknown>): void {
  for (const [column, expected] of Object.entries(input)) {
    if (FIELD_CASES[column].kind === 'number') {
      expect(typeof actual[column]).toBe('string');
      expect(Number(actual[column])).toBe(Number(expected));
    } else expect(actual[column]).toEqual(expected);
  }
}

describe('@@PLURAL@@ API', () => {
  it('creates, lists, reads, updates, soft-deletes, and restores a feature item', async () => {
    const { client, csrf } = await sharedSignedIn();
    const mark = randomUUID();
    const input = await featureInput(client, csrf, mark, 'sample');
    const created = await client.post('@@ROOT@@').set('x-csrf-token', csrf).send(input).expect(201);
    const id = created.body.data.id as string;
    expectFeatureValues(created.body.data as Record<string, unknown>, input);
    expect(created.body.data.createdByEmail).toEqual(expect.any(String));
    expect(created.body.data.modifiedByEmail).toBe(created.body.data.createdByEmail);
    const listed = await client.get(`@@ROOT@@?search=${mark}`).expect(200);
    expect(featureItems(listed).map((item) => item.id)).toEqual([id]);
    await client.get(`@@ROOT@@/${id}`).expect(200).expect(({ body }) => expect(body.data.id).toBe(id));

    const changed = await featureInput(client, csrf, mark, 'changed');
    const updated = await client.put(`@@ROOT@@/${id}`).set('x-csrf-token', csrf).send(changed).expect(200);
    expectFeatureValues(updated.body.data as Record<string, unknown>, changed);
    await client.delete(`@@ROOT@@/${id}`).set('x-csrf-token', csrf).expect(200);
    const deleted = await client.get(`@@ROOT@@/${id}`).expect(200);
    expect(deleted.body.data.deletedAtUtc).toEqual(expect.any(String));
    expect((await client.get(`@@ROOT@@?search=${mark}`).expect(200)).body.data.items).toEqual([]);
    const withDeleted = await client.get(`@@ROOT@@?search=${mark}&deleted=yes`).expect(200);
    expect(featureItems(withDeleted).map((item) => item.id)).toEqual([id]);
    const member = await sharedMemberSignedIn();
    // A member who may view never sees the deleted item; one who may not gets 403, as the endpoint case checks.
    if (member.permissions.includes(FEATURE_PERMISSIONS.view)) {
      expect(featureItems(await member.client.get(`@@ROOT@@?search=${mark}&deleted=yes`).expect(200))).toEqual([]);
      await member.client.get(`@@ROOT@@/${id}`).expect(404);
      await member.client.get(`@@ROOT@@/${id}/changes`).expect(404);
    }
    const restored = await client.post(`@@ROOT@@/${id}/restore`).set('x-csrf-token', csrf).expect(200);
    expect(restored.body.data).toMatchObject({ id, deletedAtUtc: null, deletedByEmail: null });
  });

  it('pages forward and backward by every sortable field, including null and scalar cursors', async () => {
    const { client, csrf } = await signedIn();
    const sortFields = [
  @@SORT_FIELDS@@
    ];
    for (const sortBy of sortFields) {
      const created: FeatureItem[] = [];
      const mark = `${randomUUID()}-${sortBy}`;
      for (let variant = 0; variant < 4; variant += 1) {
        const input = await featureInput(client, csrf, mark, 'sort', variant, sortBy);
        const response = await client.post('@@ROOT@@').set('x-csrf-token', csrf).send(input).expect(201);
        created.push(response.body.data as FeatureItem);
      }
      for (const sortOrder of ['asc', 'desc'] as const) {
        const hasNull = created.some((item) => item[sortBy] === null);
        const pageSize = hasNull ? 3 : 2;
        const expected = [...created].sort((left, right) => {
          const byValue = compareValues(left[sortBy], right[sortBy], sortOrder, FIELD_CASES[sortBy]?.kind ?? 'date');
          if (byValue !== 0) return byValue;
          return compareValues(left.id, right.id, sortOrder);
        });
        const query = `@@ROOT@@?limit=${pageSize}&sortBy=${encodeURIComponent(sortBy)}&sortOrder=${sortOrder}`;
        const first = await client.get(query).expect(200);
        expect(first.body.data.paging.total).toBe(4);
        expect(first.body.data.paging.totalCapped).toBe(false);
        expect(first.body.data.paging.previousCursor).toBeNull();
        expect(first.body.data.paging.nextCursor).toEqual(expect.any(String));
        const second = await client.get(`${query}&after=${encodeURIComponent(first.body.data.paging.nextCursor)}`).expect(200);
        const actual = featureItems(first).concat(featureItems(second));
        expect(new Set(actual.map((item) => item.id)).size).toBe(expected.length);
        expect(actual.map((item) => item.id)).toEqual(expected.map((item) => item.id));
        expect(second.body.data.paging.nextCursor).toBeNull();
        if (hasNull) expect(featureItems(second)[0][sortBy]).toBeNull();
        const previous = await client.get(`${query}&before=${encodeURIComponent(second.body.data.paging.previousCursor)}`).expect(200);
        expect(featureItems(previous).map((item) => item.id)).toEqual(expected.slice(0, pageSize).map((item) => item.id));
      }
      for (const item of created) await client.delete(`@@ROOT@@/${item.id}`).set('x-csrf-token', csrf).expect(200);
    }
  });

  it('searches and filters the feature list and exports its matching rows', async () => {
    const { client, csrf } = await sharedSignedIn();
    const mark = randomUUID();
    const matching = await featureInput(client, csrf, mark, 'sample');
    const id = await createFeature(client, csrf, matching);
    const unrelated = await featureInput(client, csrf, randomUUID(), 'sample');
    await createFeature(client, csrf, unrelated);
    const searched = await client.get(`@@ROOT@@?search=${mark}`).expect(200);
    expect(featureItems(searched).map((item) => item.id)).toEqual([id]);
    expect(searched.body.data.paging.total).toBe(1);
    const exported = await client.get(`@@ROOT@@/export?search=${mark}`).expect(200);
    expect(exported.text).toContain(String(matching['@@PRIMARY@@']));
    expect(exported.text).not.toContain(String(unrelated['@@PRIMARY@@']));
@@FILTER_CASES@@
  });

  it('keeps formula-leading text safe in CSV', async () => {
    const { client, csrf } = await sharedSignedIn();
    const mark = randomUUID();
    const formulas = [`=${mark}+1`, `+${mark}+1`, `-${mark}+1`, `@${mark}+1`];
    for (const formula of formulas) {
      const input = await featureInput(client, csrf, mark, 'sample');
      input['@@PRIMARY@@'] = formula;
      await createFeature(client, csrf, input);
    }
    const exported = await client.get(`@@ROOT@@/export?search=${mark}`).expect(200);
    for (const formula of formulas) expect(exported.text).toContain(`'${formula}`);
  });

@@LINK_CASE@@
  it('records each @@ONE@@ change in the change history', async () => {
    const { client, csrf } = await sharedSignedIn();
    const actorEmail = (await client.get('/api/v1/auth/me').expect(200)).body.data.email as string;
    const mark = randomUUID();
    const original = await featureInput(client, csrf, mark, 'sample');
    const created = await client.post('@@ROOT@@').set('x-csrf-token', csrf).send(original).expect(201);
    const id = created.body.data.id as string;
    const originalName = String(created.body.data['@@PRIMARY@@']);
    const originalRecordName = String(created.body.data['@@PRIMARY@@']);
    const changedName = `Changed ${mark}`;
    const changed = { ...original, ['@@PRIMARY@@']: changedName };
    const updated = await client.put(`@@ROOT@@/${id}`).set('x-csrf-token', csrf).send(changed).expect(200);
    const changedRecordName = String(updated.body.data['@@PRIMARY@@']);
    await client.put(`@@ROOT@@/${id}`).set('x-csrf-token', csrf).send(changed).expect(200);
    const changesPath = `@@ROOT@@/${id}/changes`;
    const beforeDelete = (await client.get(changesPath).expect(200)).body.data as { summary: string }[];
    expect(beforeDelete.map((change) => change.summary)).toEqual([
      '@@PRIMARY_LABEL@@ changed from ' + originalName + ' to ' + changedName,
      'Created the @@ONE@@',
    ]);
    await client.delete(`@@ROOT@@/${id}`).set('x-csrf-token', csrf).expect(200);
    await client.post(`@@ROOT@@/${id}/restore`).set('x-csrf-token', csrf).expect(200);
    const changes = (await client.get(changesPath).expect(200)).body.data as { summary: string; actorEmail: string }[];
    expect(changes.map((change) => change.summary)).toEqual([
      'Restored the @@ONE@@', 'Deleted the @@ONE@@',
      '@@PRIMARY_LABEL@@ changed from ' + originalName + ' to ' + changedName,
      'Created the @@ONE@@',
    ]);
    expect(changes.map((change) => change.actorEmail)).toEqual(Array(4).fill(actorEmail));
    const history = (await client.get('/api/v1/history').expect(200)).body.data as { summary: string }[];
    expect(history.map((entry) => entry.summary)).toEqual(expect.arrayContaining([
      `${changedRecordName}: Restored the @@ONE@@`, `${changedRecordName}: Deleted the @@ONE@@`,
      `${changedRecordName}: @@PRIMARY_LABEL@@ changed from ${originalName} to ${changedName}`,
      `${originalRecordName}: Created the @@ONE@@`,
    ]));
  });

  it('an admin restores a deleted @@ONE@@', async () => {
    const { client, csrf } = await sharedSignedIn();
    const mark = randomUUID();
    const kept = await createFeature(client, csrf, await featureInput(client, csrf, mark, 'sample'));
    const id = await createFeature(client, csrf, await featureInput(client, csrf, mark, 'sample'));
    await client.delete(`@@ROOT@@/${id}`).set('x-csrf-token', csrf).expect(200);
    const withDeleted = await client.get(`@@ROOT@@?search=${mark}&deleted=yes`).expect(200);
    expect(featureItems(withDeleted).map((item) => item.id).sort()).toEqual([kept, id].sort());
    await client.post(`@@ROOT@@/${id}/restore`).set('x-csrf-token', csrf).expect(200);
    const listed = await client.get(`@@ROOT@@?search=${mark}`).expect(200);
    expect(featureItems(listed).map((item) => item.id).sort()).toEqual([kept, id].sort());
    const changes = (await client.get(`@@ROOT@@/${id}/changes`).expect(200)).body.data as { summary: string }[];
    expect(changes[0].summary).toBe('Restored the @@ONE@@');
  });

  it('keeps another organisation from reading or changing a feature item', async () => {
    const owner = await sharedSignedIn();
    const mark = randomUUID();
    const input = await featureInput(owner.client, owner.csrf, mark, 'sample');
    const id = await createFeature(owner.client, owner.csrf, input);
    const other = await signedIn();
    expect(featureItems(await other.client.get(`@@ROOT@@?search=${mark}`).expect(200))).toEqual([]);
    expect((await other.client.get(`@@ROOT@@/export?search=${mark}`).expect(200)).text)
      .not.toContain(String(input['@@PRIMARY@@']));
    await other.client.get(`@@ROOT@@/${id}`).expect(404);
    await other.client.get(`@@ROOT@@/${id}/changes`).expect(404);
    const replacement = await featureInput(other.client, other.csrf, randomUUID(), 'sample');
    await other.client.put(`@@ROOT@@/${id}`).set('x-csrf-token', other.csrf).send(replacement).expect(404);
    await other.client.delete(`@@ROOT@@/${id}`).set('x-csrf-token', other.csrf).expect(404);
    await other.client.post(`@@ROOT@@/${id}/restore`).set('x-csrf-token', other.csrf).expect(404);
  });

  it('each @@PLURAL@@ endpoint refuses a member without its permission', async () => {
    const admin = await sharedSignedIn();
    const member = await sharedMemberSignedIn();
    const adminPermissions = (await admin.client.get('/api/v1/auth/me').expect(200)).body.data.permissions as string[];
    for (const [who, caller, permissions] of [['admin', admin, adminPermissions], ['member', member, member.permissions]] as const) {
      const input = await featureInput(admin.client, admin.csrf, randomUUID(), 'sample');
      const id = await createFeature(admin.client, admin.csrf, input);
      const changed = await featureInput(caller.client, caller.csrf, randomUUID(), 'changed');
      const routes: [string, string, () => request.Test][] = [
        ['list', FEATURE_PERMISSIONS.view, () => caller.client.get('@@ROOT@@')],
        ['export', FEATURE_PERMISSIONS.view, () => caller.client.get('@@ROOT@@/export')],
        ['detail', FEATURE_PERMISSIONS.view, () => caller.client.get(`@@ROOT@@/${id}`)],
        ['changes', FEATURE_PERMISSIONS.view, () => caller.client.get(`@@ROOT@@/${id}/changes`)],
        ['create', FEATURE_PERMISSIONS.create, () => caller.client.post('@@ROOT@@').set('x-csrf-token', caller.csrf).send(changed)],
        ['edit', FEATURE_PERMISSIONS.edit, () => caller.client.put(`@@ROOT@@/${id}`).set('x-csrf-token', caller.csrf).send(changed)],
        ['delete', FEATURE_PERMISSIONS.delete, () => caller.client.delete(`@@ROOT@@/${id}`).set('x-csrf-token', caller.csrf)],
        ['restore', FEATURE_PERMISSIONS.restore, () => caller.client.post(`@@ROOT@@/${id}/restore`).set('x-csrf-token', caller.csrf)],
      ];
      for (const [route, permission, send] of routes) {
        const response = await send();
        if (permissions.includes(permission)) {
          expect(response.status, `${who} ${route}`).not.toBe(403);
        } else {
          expect(response.status, `${who} ${route}`).toBe(403);
          expect(response.body.error.code, `${who} ${route}`).toBe('PERMISSION_DENIED');
        }
      }
    }
  });

  it('rejects bad fields, unknown inputs, and unknown list parameters', async () => {
    const { client, csrf } = await sharedSignedIn();
@@BAD_CASES@@
    const valid = await featureInput(client, csrf, randomUUID(), 'sample');
    const unknownBody = await client.post('@@ROOT@@').set('x-csrf-token', csrf).send({ ...valid, unexpected: true }).expect(400);
    expect(unknownBody.body.error.details.fieldErrors).toEqual(expect.arrayContaining([expect.objectContaining({ field: 'unexpected' })]));
    const unknownQuery = await client.get('@@ROOT@@?sortBy=unknown&unexpected=true').expect(400);
    expect(unknownQuery.body.error.details.fieldErrors).toEqual(expect.arrayContaining([
      expect.objectContaining({ field: 'sortBy' }), expect.objectContaining({ field: 'unexpected' }),
    ]));
  });

  it('documents feature requests and filters from the shared schemas', async () => {
    const response = await request(apiBaseUrl).get('/api/docs-json').expect(200);
    const list = response.body.paths['@@ROOT@@'].get;
    const parameters = list.parameters as { name: string; schema?: { enum?: string[] } }[];
    expect(parameters.map(({ name }) => name)).toEqual(expect.arrayContaining([
      'limit', 'sortBy', 'sortOrder', 'after', 'before', 'search', 'deleted',
    ]));
    const sort = parameters.find(({ name }) => name === 'sortBy');
    expect(sort?.schema?.enum).toEqual(expect.arrayContaining([
  @@SORT_FIELDS@@
    ]));
    const schema = requestBodySchema(response, '@@ROOT@@', 'post');
    for (const column of Object.keys(FIELD_CASES)) expect(schema.properties[column]).toBeDefined();
  });

  it('requires sign-in and CSRF protection for feature changes', async () => {
    await request(apiBaseUrl).get('@@ROOT@@').expect(401);
    const { client, csrf } = await sharedSignedIn();
    const input = await featureInput(client, csrf, randomUUID(), 'sample');
    await client.post('@@ROOT@@').send(input).expect(403);
    await client.post('@@ROOT@@').set('x-csrf-token', `${csrf}wrong`).send(input).expect(403);
  });
});
'''

    link_input = "value = await linkedItem(client, csrf, field.target as string, `${mark}-${variant}-${column}`);"
    replacements = {
        "@@FIELD_CASES@@": field_cases,
        "@@PLURAL@@": plural,
        "@@ONE@@": one,
        "@@ROOT@@": root,
        "@@PRIMARY@@": primary,
        "@@PRIMARY_LABEL@@": primary_label,
        "@@SORT_FIELDS@@": sort_fields,
        "@@FILTER_CASES@@": filter_cases,
        "@@LINK_CASE@@": link_case.rstrip(),
        "@@TARGET_HELPER@@": target_helper,
        "@@LINK_INPUT@@": link_input if has_link else "value = field.sample;",
        "@@BAD_CASES@@": bad_cases,
    }
    for marker, value in replacements.items():
        template = template.replace(marker, value)
    return template.strip()
