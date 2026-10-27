# Client apps offer MCP resources and prompts too

3 parts · Risks: none one-way · New moving parts: none

## What changes for you

- Each feature of a new starter app also offers MCP resources. A resource is data that an
  agent can read at an address. The resources come from the same schemas as the feature's
  tools, so nobody writes them by hand.
- Each feature has three kinds of resource:
  - Each item at its address, such as `app://projects/{project_id}`. The agent gets the item
    with every field, as the `projects_get` tool gives it.
  - The field guide at `app://projects/fields`. It lists each field with its kind, whether it
    is required, its description, an example and its allowed values.
  - One list of allowed values for each choice field, such as `app://projects/fields/status/values`,
    with the label of each value.
- Each resource has a description for a new agent and the type `application/json`.
- An agent sees and reads only the resources of the features that its role can view, as with
  tools. A read without the permission gets a plain message that says why.
- An agent can subscribe to an item. When a person or an agent changes, deletes or restores
  that item, the app sends the agent a change notice. The agent then reads the item again.
- The field guide and the allowed values change only when a new release of the app goes out.
  The release restarts the API and closes each open connection, so the agent reads them again
  when it connects. There is no separate notice for them.
- A new app has no MCP prompts. A prompt is a ready-made request for a task that people ask an
  agent to do again and again. During setup, when the client notes describe such a task, the
  agent asks one question: "Which tasks will people ask an agent to do again and again?" The
  answers go into the app's constitution. For each task, the agent then writes one prompt in
  the feature's tools file, with the inputs that the task needs.
- The MCP server never asks the person questions through the agent (elicitation) and never
  asks the agent's model to write text (sampling). Gantry Cloud handles approvals, and Mainline
  sets the tool rules.
- A feature that the feature command builds gets its resources at once. In an app made from a
  starter before the MCP server, the command builds the feature without tools or resources and
  says so.
- Existing apps keep their code. On upgrade with `forge sync`, they get the guide text with
  these rules. They get no resources, no prompts and no app file.

Design: none (no screens; it adds MCP resources, notices and prompts to the API and text to the guides)

## Why

With the MCP tools story, an agent can only call tools. To know which values a field takes, it
must guess and read the errors. To read one item, it must call a tool each time, and it cannot
know when the item changes. A task that people ask for every week needs a new request each
time. MCP resources and prompts solve these three problems. The feature's schemas already hold
each field, its rules and its allowed values, so the resources come from them at no extra cost.
Prompts are only useful for real repeated tasks, so the app gets one only when the client notes
name such a task.

## Done when

1. **In a new app from `forge init --starter` or `forge init --starter python`, each feature offers its items at `app://<plural>/{<singular>_id}` as a resource template, its field guide at `app://<plural>/fields` with each field's kind, whether it is required, its description, an example and its allowed values, and one allowed-value list for each choice field. Each resource has a description and the type `application/json`. An agent sees and reads only the resources of the features that its role can view, and a read without that permission gets a plain refusal. A feature that the feature command builds gets its resources at once, and in an app made from a starter before the MCP server, the command builds the feature without tools or resources and says so.**
2. **An agent that subscribes to an item gets a change notice when a person or an agent updates, deletes or restores that item, while its key works and its role can view the feature.**
3. **A new app has no MCP prompts. A prompt that a developer adds in a feature's tools file shows, with its inputs, to the agents whose role has its permission. The MCP server never uses elicitation or sampling.**
4. **The agent's guide and the worker brief carry the resource and prompt rules, the setup interview's question about repeated agent tasks and the constitution's `## Agent tasks` section. A new repo gets this text at `forge init`. An existing repo gets it on upgrade with `forge sync`, and gets no app file.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none one-way. Each part reverts with its pull request. No part adds a table or a
migration.

Trade-off: the app keeps open connections and subscriptions in memory, in each running copy of
the API. With two or more copies, an agent gets a notice only when its connection, its
subscription and the change are on the same copy. With one copy, every notice arrives.

Trade-off: the app sends no list-changed notice. The field guide and the allowed values change
only with a new release. A role change shows the next time the agent lists the resources.

Trade-off: resource reads do not count toward the limit of 120 tool calls a minute on one key.

Trade-off: a notice says only that an item changed. The agent reads the item again to see the
change.

Trade-off: Mainline's gateway must pass the agent's open connection through for notices to
arrive. That is Mainline's work. This story does not build it.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

This story follows FORGE-MCP-1 and uses its words: the tools file, `defineFeatureTools`,
`callTool`, `agentForKey`, the `concise` and `detailed` forms, the `_label` rule, the error
kinds and the `/mcp` endpoint. Where a name here differs from the merged FORGE-MCP-1 code,
follow the merged code.

Each new test file starts with `STORY = "FORGE-MCPRES-1"`. Each Forge test runs the forge
command or, for the app's own behaviour, names the cases that the app's own
`node scripts/test.mjs` reports, and never imports forge. One test per Done-when item, named
`test_<n>_...`. Live tests carry `@pytest.mark.platform` and `@pytest.mark.timeout(1800)` and
use `live_run`, `live_python_starter` and `_require_cases`, as `tests/test_mcp.py` does.
`starter-smoke.yml` runs `tests/test_mcp_resources.py` in both jobs (`-k typescript` and
`-k python`). The `earlier adopted` case of each item uses the
`tests/fixtures/adopted-v1.2.2/client` repo moved to this release and synced, as
`tests/test_mcp.py` does, with one cached upgrade for the file.

**Sources.** The MCP specification 2025-06-18, Server features: Resources (`resources/list`,
`resources/templates/list`, `resources/read`, `resources/subscribe`,
`notifications/resources/updated`, the error `-32002`) and Prompts (`prompts/list`,
`prompts/get`). Use the MCP library that FORGE-MCP-1 pins, at the same version. Add no
dependency.

**One release.** This story ships in the same release as FORGE-MCP-1. So no app has the core
tools file without the resources, and FORGE-MCP-1's one check (the core tools file) still
decides the feature command's no-MCP copy.

### Words this story pins

The part named first owns each name; later parts use it and list that part under After.

- **Where the code lives (RES pins it; RESPY follows it).** `libs/core/server/src/common/resources.ts`
  (Python `apps/api/app/core/resources.py`) holds the resource list, the reads and the change
  events. `libs/core/server/src/common/prompts.ts` (Python `app/core/prompts.py`) holds
  `definePrompt`. Both are exported from `@app/core-server` (Python `app.core`).
  `defineFeatureTools` registers the feature's resources when it registers its tools, so a
  feature's resources need no line in its tools file. The MCP module only carries messages, as
  for tools.
- **Addresses and names (RES).** For each feature, with `<plural>` in snake form and
  `<singular>_id` as the tools use them:
  - The item template `app://<plural>/{<singular>_id}`, name `<plural>_item`, title
    `A project`, description `One project with every field, by its project_id. Use projects_search to find a project_id, and projects_update to change it.`
  - The field guide `app://<plural>/fields`, name `<plural>_fields`, title `Project fields`,
    description `Each project field: its kind, whether it is required, its description, an example and its allowed values. Read it before projects_create or projects_update.`
  - For each choice field (an `enum` in the create tool's input schema),
    `app://<plural>/fields/<field>/values`, name `<plural>_<field>_values`, title
    `Project status values`, description `The allowed values of a project's status, with their labels. Use one of them in projects_create, projects_update or the status filter of projects_search.`
  - Every resource and template has `mimeType: 'application/json'`. Each read returns one
    content item with the same `uri`, `mimeType: 'application/json'` and the JSON as `text`.
- **Contents (RES).** All names are snake case, as in the tools.
  - The item: the `structuredContent` of `<feature>_get` with `response_format: 'detailed'`,
    made by the same code.
  - The field guide: `{ feature, item, fields: [...] }`, made from the create tool's input
    JSON Schema. Each field: `name`; `kind`, the JSON Schema `type` (`string`, `number`,
    `integer` or `boolean`); `format` when the schema has one (`date`, `email`, `uuid`);
    `required`; `description`; `example`; for a choice field `allowed_values` (the `enum`) and
    `values_uri`; for a link field `links_to`, the target feature from the tools file's `links`.
    The guide leaves out `idempotency_key`.
  - An allowed-value list: `{ field, values: [{ value, label }] }`, with each label from the
    `_label` rule.
- **Permissions (RES).** `resources/list` and `resources/templates/list` give only the
  resources of the features whose `.view` permission the agent's role has. A read checks the
  same permission. A deleted item reads only for a role with `.restore`, as `<feature>_get`
  does. A refusal is a JSON-RPC error with code `-32002`, the message of the matching tool error
  and `data: { kind, retryable: false }`: `not_found`
  (`No project has this project_id in your organisation. Use projects_search to find it.`),
  `not_allowed` (`Your agent account's role cannot view projects. An admin can change its role on the Members screen.`),
  and for an address that matches no resource, `not_found` with
  `No resource has this address. Use resources/list and resources/templates/list to find one.`
  The role is read on each request, as for tools.
- **Change notices (RES pins them; RESPY follows).** The server's capabilities are
  `resources: { subscribe: true, listChanged: false }` and `prompts: { listChanged: false }`.
  - `GET /mcp` with a valid agent key opens the agent's notice stream through the MCP
    library's own transport, with the same key check and the same `401` as a `POST`. The MCP
    module keeps each open stream with the agent's account and organisation, in memory, until
    it closes. TypeScript: one `Server` connected to its own `StreamableHTTPServerTransport`
    (`sessionIdGenerator: undefined`) per GET, and `server.sendResourceUpdated({ uri })`.
    Python: a `StreamableHTTPServerTransport` and a `ServerSession` (`stateless=True`) per GET,
    made with the library's classes as its session manager makes them, and
    `session.send_resource_updated(uri)`.
  - `resources/subscribe` takes any address that a read would accept, and refuses the others
    with the read's error. The module keeps the subscriptions for each account in memory, and
    drops them when the account's last stream closes. `resources/unsubscribe` removes one.
    Subscribing to the field guide or a value list works and sends nothing.
  - After the transaction of an update, a delete or a restore commits, the feature service
    calls `resourceChanged(organisationId, feature, id)` (Python
    `resource_changed(organisation_id, feature, item_id)`). The change comes from the service,
    so a change from the screens and a change from a tool both send it. A create sends nothing,
    because nobody can subscribe to a new item yet. An update that changes no field (FORGE-MCP-1's
    no-change update) sends nothing.
  - For each open stream in that organisation whose account subscribed to the item's address,
    the module reads the key again with `agentForKey`. When the key no longer works, the module
    closes the stream. When the role cannot view the feature, it sends nothing. Otherwise it
    sends `notifications/resources/updated` with the address.
  - TypeScript: core keeps the events on a Node `EventEmitter`, and the MCP module listens.
    Python: `app.core.resources` keeps a plain list of listeners. The MCP module adds one at
    start, which passes each change to the event loop with `loop.call_soon_threadsafe`, because
    the sync services run in worker threads. With no listener (scripts, unit tests), a change
    does nothing.
  - A `ponytail:` comment names the ceiling: streams and subscriptions in memory per running
    copy; Postgres `LISTEN` and `NOTIFY` is the upgrade.
  - The lines in `projects.service.ts` (Python `service.py`) go between FORGE-MCP-1's
    `forge:feature:mcp` marks, so the no-MCP copy leaves them out.
- **Prompts (RES pins them; RESPY follows).** `definePrompt({ name, title, description, arguments, permission, text })`
  in a feature's tools file. Every key is required. `name` is `<feature>_<verb>` in snake case,
  as for tools. `arguments` is a strict zod (Python Pydantic) object of strings; each key
  becomes a prompt argument with its `.meta` description, and `required` is true unless the
  key is optional. `text(args)` returns the text of the one `user` message. `prompts/list`
  gives only the prompts whose permission the role has. `prompts/get` checks the same
  permission and parses the arguments with the schema; a missing or unknown argument gets the
  JSON-RPC error `-32602` with a plain message. A second prompt with the same name throws at
  start. The starter defines no prompt.
- **No elicitation and no sampling (RES, RESPY).** The MCP module never sends
  `elicitation/create` or `sampling/createMessage`, and the guide and the brief say so.
- **The tools file comment (RES, RESPY).** The header comment of `projects.tools.ts` (Python
  `tools.py`) becomes
  `The one place that says which tools, resources and prompts agents get for projects. Add a prompt only for a task under ## Agent tasks in docs/product/CONSTITUTION.md.`
  The feature command's copy renames it, so each new feature carries the rule.
- **The no-MCP line (RES).** FORGE-MCP-1's line becomes
  `This app has no MCP server, so <plural> get no agent tools or resources.`
- **Case names.** In `apps/api/test/mcp.e2e-spec.ts` (Python `tests/test_mcp.py`):
  `an agent reads a project, the project fields and the status values as resources`,
  `every resource has a description and the JSON type`,
  `an agent subscribed to a project gets a notice when it changes`,
  `the MCP server has no prompts by default`. In `libs/core/server/src/common/tools.test.ts`
  (Python `tests/test_tools.py`): `a resource read without the view permission is refused` and
  `a tools file can add a prompt with its inputs`. The Python cases use the same names in the
  snake form that FORGE-DEFAULTS-1 pins. These cases are not copied for each new feature: the
  resource code is the same for every feature, and the contract case reads every feature's
  resources.

### Done-when details

1. Resources (RES for TypeScript, RESPY for Python).
   - `an agent reads a project, the project fields and the status values as resources`: a
     Member agent creates a project with `projects_create`; `resources/templates/list` holds
     `app://projects/{project_id}`; `resources/list` holds `app://projects/fields` and
     `app://projects/fields/status/values`; the item read equals the `detailed`
     `projects_get` result; the field guide has `name` (`string`, required, its description and
     example) and `status` (`allowed_values` `active` and `archived`, and its `values_uri`); the
     value list has `Active` and `Archived` as labels; a read of an unknown project id gets
     `-32002` with `not_found`.
   - `every resource has a description and the JSON type`: for every listed resource and
     template, a description of at least one sentence and `mimeType` `application/json`; for
     every listed resource, a read returns one content item with that type and text that parses
     as JSON. Because the case reads the list, it covers each feature that the feature command
     adds.
   - `a resource read without the view permission is refused` (unit, no HTTP): a feature
     defined with a member role that lacks `view` gives a Member principal no resource or
     template of that feature, and its read gets `not_allowed`, not retryable, with the message.
   - Test `tests/test_mcp_resources.py::test_1_each_feature_offers_its_resources`, parameters
     `typescript` (RES), `python` (RESPY) and `earlier adopted` (RES). Live: the reports hold
     the three cases. `earlier adopted`: after upgrade and `forge sync`, the repo has no
     `libs/core/server/src/common/resources.ts` and no `apps/api/app/core/resources.py`, and
     `git status --porcelain` lists only files that sync writes.
   - The older-starter case stays in `tests/test_mcp.py::test_3` (`older starter`): RES changes
     its expected line to the new no-MCP line, and adds `resourceChanged` to the names that no
     written file may hold.
2. Change notices (RES, RESPY).
   - `an agent subscribed to a project gets a notice when it changes`: an agent client opens
     its stream and subscribes to a project's address; an update by a person through
     `PATCH /api/v1/projects/:id` and an update through `projects_update` each bring
     `notifications/resources/updated` with that address within 5 seconds; a second agent that
     did not subscribe gets no notice; after an admin revokes the first agent's key, the next
     update brings it no notice. Use the MCP library's client with a notification handler, as
     `agentClient(key)` makes it (Python `agent_client(key)` with a `message_handler`).
   - Test `tests/test_mcp_resources.py::test_2_an_agent_gets_a_notice_when_an_item_changes`,
     parameters `typescript` (RES), `python` (RESPY) and `earlier adopted` (RES). Live: the
     reports hold the case. `earlier adopted`: the synced repo's `apps/` and `libs/` files are
     unchanged.
3. Prompts, elicitation and sampling (RES, RESPY).
   - `the MCP server has no prompts by default`: `prompts/list` returns an empty list.
   - `a tools file can add a prompt with its inputs` (unit): a feature with one `definePrompt`
     that has one required and one optional argument lists the prompt for a role with its
     permission, with both arguments and their `required` values, and not for a role without
     it; `prompts/get` returns one `user` message with the argument values in its text; a
     missing required argument gets an error; a second prompt with the same name throws.
   - Test `tests/test_mcp_resources.py::test_3_a_new_app_has_no_prompts_until_a_tools_file_adds_one`,
     parameters `typescript` (RES), `python` (RESPY) and `earlier adopted` (RES). Live: the
     reports hold the two cases. In the new starter app, `git grep` finds no tracked file under
     `libs/` or `apps/` with `elicitation/create`, `elicitInput`, `createMessage` or
     `create_message`, and finds `definePrompt(` (Python `define_prompt(`) only in
     `prompts.ts` (`prompts.py`). `earlier adopted`: the synced repo has no
     `libs/core/server/src/common/prompts.ts` and no `apps/api/app/core/prompts.py`.
4. The guides (RESGUIDE).
   - `src/forge/templates/skill.md`, App constitution:
     - After the growth topics paragraph: "In an app with libs/mcp or apps/api/app/mcp, check
       the client notes for tasks that people will ask an agent to do again and again. When the
       notes describe such a task and do not list them all, ask one question: \"Which tasks will
       people ask an agent to do again and again?\" Write each task under ## Agent tasks in the
       constitution as `- <task>: <feature>; inputs: <the inputs it needs>`. With no task, write
       `- None`. Ask it again only when the person wants to change the list."
     - In the constitution outline, after `## Growth notes`: a `## Agent tasks` section with
       `- <the task>: <feature>; inputs: <the inputs it needs>, or None`.
     - In both fixed rules lists, after FORGE-MCP-1's Built in line:
       `- Built in: each feature also offers its items, its field guide and its allowed values as MCP resources, with a notice when a subscribed item changes; agents get a prompt only for a task under ## Agent tasks; the MCP server never uses elicitation or sampling.`
   - `src/forge/templates/skill.md`, Planning a story, after FORGE-MCP-1's tool rules: "Each
     feature's resources come from its tools file's `defineFeatureTools` and need no code. When
     a story builds or changes a feature that a task under ## Agent tasks names, the part names
     its prompt: the name in the form `<feature>_<verb>`, its inputs and its permission. Write
     no other prompt. Add no elicitation and never use sampling."
   - `src/forge/templates/brief.md`, after FORGE-MCP-1's tool sentences: "A feature's
     resources come from `defineFeatureTools`; add none by hand. Add a prompt with
     `definePrompt` only when your part names it, with a strict `arguments` schema and one
     permission. Never send an elicitation or a sampling request."
   - `docs/guide.md`: one sentence in FORGE-MCP-1's MCP paragraph: the three resources, the
     notice, prompts from `## Agent tasks`, and no elicitation or sampling.
   - `forge sync` rewrites `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md`.
   - Test `tests/test_mcp_resources_guide.py::test_4_the_guides_name_resources_and_prompts`,
     parameters `new init` and `previous release`, with the setup of
     `tests/test_services_guide.py::test_3` and whitespace collapsed: the synced skill copies
     have `Which tasks will people ask an agent to do again and again?`, `## Agent tasks`, the
     Built in sentence and `Write no other prompt`; the worker brief from `forge work` has
     `add none by hand` and `Never send an elicitation or a sampling request`.
     `previous release`: after `forge sync`, `git status --porcelain` lists only files that
     sync writes.

### New and existing repos

- **New repos** (`forge init --starter`, `forge init --starter python`): each feature's
  resources and notices, no prompts, the tools file comment, the guide text and the
  constitution's `## Agent tasks` section. Plain `forge init` and a newly adopted app: the
  guide text only.
- **Existing repos** (on upgrade to this release, after `forge sync`): the guide text. No app
  file. In an app made from the starter before FORGE-MCP-1, the feature command builds the
  feature without tools or resources and says so. Tested on the adopted earlier-release
  fixture in each item, and on the older starter app in `tests/test_mcp.py::test_3`.

## Tasks

<!-- One row per task. Covers: the Done-when numbers it delivers, at most three. Scope: the paths
it may change. Tests: the tests it adds or changes. After: the tasks it waits for. When two tasks
share a function, field, file format or command, the first task pins it: it commits the shared
names and stubs plus one test that crosses both sides, and the tasks that use it list it under
After. Split tasks so each owns its files; shared lines (command table, guide list, registry) go
to one task or a small last wiring task; After only when a task needs another task's code. The
Developer column is optional: the lead fills or changes a GitHub username here, below For the
builders, without another approval. Leave it blank for an unassigned part. Forge next uses
the caller's GitHub login; another developer may start it with a warning. Existing tables
without Developer still work. The moving-parts line stays last: "none", or each new dependency, service, datastore,
queue, background job or abstraction layer, with the Done-when item that needs it. -->

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| RES | Resources, notices and prompts in the TypeScript starter | The core resources and prompts files, the MCP module's resource, subscribe and prompt handlers and its notice streams, the notice call in the projects service, the tools file comment, the no-MCP line, the app's cases and the Forge tests. | 1, 2, 3 | `starter/libs/core/server/src/common/resources.ts` and `prompts.ts` (new), `starter/libs/core/server/src/common/tools.ts` (the resource registration only) and `tools.test.ts`, `starter/libs/core/server/src/index.ts`, `starter/libs/mcp/server/**`, `starter/libs/projects/server/src/projects.service.ts` (the notice lines inside the `mcp` marks), `starter/libs/projects/server/src/projects.tools.ts` (the comment), `starter/apps/api/test/mcp.e2e-spec.ts`, `starter/apps/api/test/helpers.ts`, `src/forge/feature*.py` (the no-MCP line only), `tests/test_mcp.py` (`test_3`, `older starter` only), `tests/test_mcp_resources.py` (new), `.github/workflows/starter-smoke.yml` | `tests/test_mcp_resources.py` (`test_1`, `test_2`, `test_3`: `typescript`, `earlier adopted`), `tests/test_mcp.py::test_3` (`older starter`) | FORGE-MCP-1/TOOLS | no | |
| RESPY | Resources, notices and prompts in the Python starter | The same in the Python starter: `app/core/resources.py` and `prompts.py`, the `app/mcp` handlers and notice streams, the notice call in the projects service, the tools file comment and the app's cases. | 1, 2, 3 | `starter-python/apps/api/app/core/resources.py` and `prompts.py` (new), `starter-python/apps/api/app/core/tools.py` (the resource registration only), `starter-python/apps/api/app/core/__init__.py`, `starter-python/apps/api/app/mcp/**`, `starter-python/apps/api/app/projects/service.py` (the notice lines inside the `mcp` marks), `starter-python/apps/api/app/projects/tools.py` (the comment), `starter-python/apps/api/tests/conftest.py`, `test_mcp.py` and `test_tools.py`, `tests/test_mcp_resources.py` | `tests/test_mcp_resources.py` (`test_1`, `test_2`, `test_3`: `python`) | RES, FORGE-MCP-1/TOOLSPY | no | |
| RESGUIDE | The guides carry the resource and prompt rules | The setup interview's question, the constitution's `## Agent tasks` section and Built in line, the planning and worker brief rules, the guide sentence and the synced skill copies, on new and existing repos. | 4 | `src/forge/templates/skill.md`, `src/forge/templates/brief.md`, `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `docs/guide.md`, `tests/test_mcp_resources_guide.py` (new) | `tests/test_mcp_resources_guide.py::test_4` (new) | FORGE-MCP-1/MCPGUIDE | no | |

RESGUIDE shares no file with RES or RESPY and needs no code from them, so it can run beside RES
once FORGE-MCP-1/MCPGUIDE merges. It also waits for any open part that changes the App
constitution section of `skill.md`; follow the merged text.

New moving parts: none. The notice streams and subscriptions are plain in-memory maps in the
MCP module (item 2), and the prompts list is an in-memory list that each tools file fills at
start, as the tools list is (item 3).

## Notes

- **Order.** RES waits for FORGE-MCP-1/TOOLS (the core tools file, the MCP module and the
  tests it changes). RESPY waits for FORGE-MCP-1/TOOLSPY and for RES, because both change
  `tests/test_mcp_resources.py`. RESGUIDE waits for FORGE-MCP-1/MCPGUIDE, because both change
  the same paragraphs of `skill.md` and `brief.md`.
- **Owner decisions (27 Oct 2026, settled).** Resources are always generated for each feature
  from the same schemas as its tools: one item at an address as a resource template, the
  feature's field guide (each field, its kind, required or not, allowed values) and lists of
  allowed values. Resources follow the agent account's permissions as tools do. The server
  sends change notices, as simply as the MCP library allows. Prompts only when the client notes
  describe a repeated workflow: the setup interview gets one question, "Which tasks will people
  ask an agent to do again and again?"; the agent writes one prompt for each answer in the
  feature's tools file, with the inputs the task needs; the default is none. No elicitation by
  default (Gantry Cloud handles approvals; Mainline sets tool rules). Sampling is never used.
  The guide, the worker brief and the feature command carry these rules. New repos get them at
  init; existing repos get the guide text on upgrade with `forge sync` and no app files. An app
  made from a starter before MCP keeps working, and the feature command builds a feature
  without resources there and says so. No new screens.
- **Planner choices the owner did not make.** (1) The field guide's kind is the JSON Schema
  type and format, because the starter's projects feature and hand-made features have no
  feature-command kind record. (2) No list-changed notice: the field guide and the allowed
  values change only with a release, which closes every connection. (3) Notices need the
  agent's open connection (`GET /mcp`) and live in memory in each running copy, as the rate
  limit does; with more than one copy, a notice can miss. (4) Before each notice, the server
  checks the key and the role again, so a revoked key stops getting notices at once. (5) A
  create sends no notice. (6) The resource cases are in the MCP test file and are not copied
  for each new feature; the contract case reads every feature's resources. (7) The feature
  command carries the prompt rule through the tools file's comment, which its copy renames, and
  through its no-MCP line; it writes no prompt. (8) The link between a prompt and a task under
  `## Agent tasks` is held by the guide and by the review, which reports work against the
  constitution as P1; Forge adds no check for it. (9) Resource reads do not count toward the
  limit of 120 calls a minute. (10) This story ships in the same release as FORGE-MCP-1.
- **For Mainline (context only).** Assumption: Mainline's gateway passes `GET /mcp` and its
  open stream through to the app, with the agent key, so that notices arrive.
- No client repo is named anywhere in this story's code, tests, texts or commits.
