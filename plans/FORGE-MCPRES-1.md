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
- The app sends no change notices. An agent reads a resource again when it needs fresh data.
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

Design: none (no screens; it adds MCP resources and prompts to the API and text to the guides)

## Why

With the MCP tools story, an agent can only call tools. To know which values a field takes, it
must guess and read the errors. A task that people ask for every week needs a new request each
time. MCP resources and prompts solve these two problems. The feature's schemas already hold
each field, its rules and its allowed values, so the resources come from them at no extra cost.
Prompts are only useful for real repeated tasks, so the app gets one only when the client notes
name such a task.

## Done when

1. **In a new app from `forge init --starter` or `forge init --starter python`, each feature offers its items at `app://<plural>/{<singular>_id}` as a resource template, its field guide at `app://<plural>/fields` with each field's kind, whether it is required, its description, an example and its allowed values, and one allowed-value list for each choice field. Each resource has a description and the type `application/json`. An agent sees and reads only the resources of the features that its role can view, and a read without that permission gets a plain refusal. A feature that the feature command builds gets its resources at once, and in an app made from a starter before the MCP server, the command builds the feature without tools or resources and says so.**
2. **A new app has no MCP prompts. A prompt that a developer adds in a feature's tools file shows, with its inputs, to the agents whose role has its permission. The MCP server never uses elicitation or sampling.**
3. **The agent's guide and the worker brief carry the resource and prompt rules, the setup interview's question about repeated agent tasks and the constitution's `## Agent tasks` section. A new repo gets this text at `forge init`. An existing repo gets it on upgrade with `forge sync`, and gets no app file.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none one-way. Each part reverts with its pull request. No part adds a table or a
migration.

Trade-off: the app sends no change notices, so an agent does not learn when an item changes.
It reads the resource again when it needs fresh data. A later story can add notices with MCP
sessions and Postgres `LISTEN` and `NOTIFY`, so that a notice reaches the agent from any
running copy of the API.

Trade-off: resource reads do not count toward the limit of 120 tool calls a minute on one key.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

This story follows FORGE-MCP-1 and uses its words: the tools file, `defineFeatureTools`,
`callTool`, the `concise` and `detailed` forms, the `_label` rule, the error kinds and the
`/mcp` endpoint. Where a name here differs from the merged FORGE-MCP-1 code, follow the merged
code.

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
`resources/templates/list`, `resources/read`, the error `-32002`) and Prompts (`prompts/list`,
`prompts/get`). Use the MCP library that FORGE-MCP-1 pins, at the same version. Add no
dependency.

**One release.** This story ships in the same release as FORGE-MCP-1. So no app has the core
tools file without the resources, and FORGE-MCP-1's one check (the core tools file) still
decides the feature command's no-MCP copy.

**Part sizes.** RES and RESPY can each pass the 400-line limit. Do not split them. As for
FORGE-MCP-1, the owner will be asked to allow these parts over the line limit
(`forge fix allow-large`, with this reason).

### Words this story pins

The part named first owns each name; later parts use it and list that part under After.

- **Where the code lives (RES pins it; RESPY follows it).** `libs/core/server/src/common/resources.ts`
  (Python `apps/api/app/core/resources.py`) holds the resource list and the reads.
  `libs/core/server/src/common/prompts.ts` (Python `app/core/prompts.py`) holds
  `definePrompt`. Both are exported from `@app/core-server` (Python `app.core`).
  `defineFeatureTools` registers the feature's resources when it registers its tools, so a
  feature's resources need no line in its tools file. The MCP module only carries messages, as
  for tools. The server's capabilities are `resources: { subscribe: false, listChanged: false }`
  and `prompts: { listChanged: false }`.
- **Addresses and names (RES).** For each feature, with `<plural>` in snake form and
  `<singular>_id` as the tools use them:
  - The item template `app://<plural>/{<singular>_id}`, name `<plural>_item`, title
    `A project`, description `One project with every field, by its project_id. Use projects_search to find a project_id, and projects_update to change it.`
  - The field guide `app://<plural>/fields`, name `<plural>_fields`, title `Project fields`,
    description `Each project field: its kind, whether it is required, its description, an example and its allowed values. Read it before projects_create or projects_update.`
  - For each choice field (an `enum` among the feature's own fields),
    `app://<plural>/fields/<field>/values`, name `<plural>_<field>_values`, title
    `Project status values`, description `The allowed values of a project's status, with their labels. Use one of them in projects_create, projects_update or the status filter of projects_search.`
  - Every resource and template has `mimeType: 'application/json'`. Each read returns one
    content item with the same `uri`, `mimeType: 'application/json'` and the JSON as `text`.
- **Contents (RES).** All names are snake case, as in the tools.
  - The item: the `structuredContent` of `<feature>_get` with `response_format: 'detailed'`,
    made by the same code.
  - The field guide: `{ feature, item, fields: [...] }`, made from the create tool's input
    JSON Schema, with only the feature's own fields: it leaves out the tool options
    `response_format` and `idempotency_key`, so neither gets a field entry or a value list.
    Each field: `name`; `kind`, the JSON Schema `type` (`string`, `number`, `integer` or
    `boolean`); `format` when the schema has one (`date`, `email`, `uuid`); `required`;
    `description`; `example`; for a choice field `allowed_values` (the `enum`) and
    `values_uri`; for a link field `links_to`, the target feature from the tools file's `links`.
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
  `every feature has its resources, each with a description and the JSON type`, and
  `the MCP server has no prompts by default`. In `libs/core/server/src/common/tools.test.ts`
  (Python `tests/test_tools.py`): `a resource read without the view permission is refused` and
  `a tools file can add a prompt with its inputs`. The Python cases use the same names in the
  snake form that FORGE-DEFAULTS-1 pins. These cases are not copied for each new feature: the
  resource code is the same for every feature, and the contract case checks every feature.

### Done-when details

1. Resources (RES for TypeScript, RESPY for Python).
   - `an agent reads a project, the project fields and the status values as resources`: a
     Member agent creates a project with `projects_create`; `resources/templates/list` holds
     `app://projects/{project_id}`; `resources/list` holds `app://projects/fields` and
     `app://projects/fields/status/values`; the item read equals the `detailed`
     `projects_get` result; the field guide has `name` (`string`, required, its description and
     example) and `status` (`allowed_values` `active` and `archived`, and its `values_uri`), and
     no `response_format` or `idempotency_key`; the value list has `Active` and `Archived` as
     labels; a read of an unknown project id gets `-32002` with `not_found`.
   - `every feature has its resources, each with a description and the JSON type`: an Admin
     agent builds the expected features from the tools list, one for each `<feature>_search`
     tool, as FORGE-MCP-1's contract case does, so the list does not come from the resource
     code. For each expected feature, the case fails unless `resources/templates/list` has
     `app://<feature>/{<singular>_id}`, `resources/list` has `app://<feature>/fields`, and
     `resources/list` has one value list for each `enum` among the feature's own fields in its
     `<feature>_create` input schema. For every listed resource and template, it checks a
     description of at least one sentence and `mimeType` `application/json`; for every listed
     resource, a read returns one content item with that type and text that parses as JSON.
   - `a resource read without the view permission is refused` (unit, no HTTP): a feature
     defined with a member role that lacks `view` gives a Member principal no resource or
     template of that feature, and its read gets `not_allowed`, not retryable, with the message.
   - Test `tests/test_mcp_resources.py::test_1_each_feature_offers_its_resources`, parameters
     `typescript` (RES), `python` (RESPY) and `earlier adopted` (RES). Live: the reports hold
     the three cases. Live, for a generated feature: the feature run that FORGE-FEATURE-1's
     test_2 caches (its `jobs` feature, built by the feature command) holds the contract case,
     and its tools list has `jobs_search`, so the contract case checked the jobs resources.
     `earlier adopted`: after upgrade and `forge sync`, the repo has no
     `libs/core/server/src/common/resources.ts` and no `apps/api/app/core/resources.py`, and
     `git status --porcelain` lists only files that sync writes.
   - The older-starter case stays in `tests/test_mcp.py::test_3` (`older starter`): RES changes
     its expected line to the new no-MCP line.
2. Prompts, elicitation and sampling (RES, RESPY).
   - `the MCP server has no prompts by default`: `prompts/list` returns an empty list.
   - `a tools file can add a prompt with its inputs` (unit): a feature with one `definePrompt`
     that has one required and one optional argument lists the prompt for a role with its
     permission, with both arguments and their `required` values, and not for a role without
     it; `prompts/get` returns one `user` message with the argument values in its text; a
     missing required argument gets an error; a second prompt with the same name throws.
   - Test `tests/test_mcp_resources.py::test_2_a_new_app_has_no_prompts_until_a_tools_file_adds_one`,
     parameters `typescript` (RES), `python` (RESPY) and `earlier adopted` (RES). Live: the
     reports hold the two cases. In the new starter app, `git grep` over the tracked files under
     `libs/` and `apps/`, leaving out test files (`*.test.ts`, `*.spec.ts` and
     `apps/api/tests/`), finds no `elicitation/create`, `elicitInput`, `createMessage` or
     `create_message`, and finds `definePrompt(` (Python `define_prompt(`) only in
     `prompts.ts` (`prompts.py`). `earlier adopted`: the synced repo has no
     `libs/core/server/src/common/prompts.ts` and no `apps/api/app/core/prompts.py`.
3. The guides (RESGUIDE).
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
       `- Built in: each feature also offers its items, its field guide and its allowed values as MCP resources; agents get a prompt only for a task under ## Agent tasks; the MCP server never uses elicitation or sampling.`
   - `src/forge/templates/skill.md`, Planning a story, after FORGE-MCP-1's tool rules: "Each
     feature's resources come from its tools file's `defineFeatureTools` and need no code. When
     a story builds or changes a feature that a task under ## Agent tasks names, the part names
     its prompt: the name in the form `<feature>_<verb>`, its inputs and its permission. Write
     no other prompt. Add no elicitation and never use sampling."
   - `src/forge/templates/brief.md`, after FORGE-MCP-1's tool sentences: "A feature's
     resources come from `defineFeatureTools`; add none by hand. Add a prompt with
     `definePrompt` only when your part names it, with a strict `arguments` schema and one
     permission. Never send an elicitation or a sampling request."
   - `docs/guide.md`: one sentence in FORGE-MCP-1's MCP paragraph: the three resources,
     prompts from `## Agent tasks`, and no elicitation or sampling.
   - `forge sync` rewrites `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md`.
   - Test `tests/test_mcp_resources_guide.py::test_3_the_guides_name_resources_and_prompts`,
     parameters `new init` and `previous release`, with the setup of
     `tests/test_services_guide.py::test_3` and whitespace collapsed: the synced skill copies
     have `Which tasks will people ask an agent to do again and again?`, `## Agent tasks`, the
     Built in sentence and `Write no other prompt`; the worker brief from `forge work` has
     `add none by hand` and `Never send an elicitation or a sampling request`.
     `previous release`: after `forge sync`, `git status --porcelain` lists only files that
     sync writes.

### New and existing repos

- **New repos** (`forge init --starter`, `forge init --starter python`): each feature's
  resources, no prompts, the tools file comment, the guide text and the constitution's
  `## Agent tasks` section. Plain `forge init` and a newly adopted app: the guide text only.
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
| RES | Resources and prompts in the TypeScript starter | The core resources and prompts files, the MCP module's resource and prompt handlers, the tools file comment, the no-MCP line, the app's cases and the Forge tests. | 1, 2 | `starter/libs/core/server/src/common/resources.ts` and `prompts.ts` (new), `starter/libs/core/server/src/common/tools.ts` (the resource registration only) and `tools.test.ts`, `starter/libs/core/server/src/index.ts`, `starter/libs/mcp/server/**`, `starter/libs/projects/server/src/projects.tools.ts` (the comment), `starter/apps/api/test/mcp.e2e-spec.ts`, `src/forge/feature*.py` (the no-MCP line only), `tests/test_mcp.py` (`test_3`, `older starter` only), `tests/test_mcp_resources.py` (new), `.github/workflows/starter-smoke.yml` | `tests/test_mcp_resources.py` (`test_1`, `test_2`: `typescript`, `earlier adopted`), `tests/test_mcp.py::test_3` (`older starter`) | FORGE-MCP-1/TOOLS | no | |
| RESPY | Resources and prompts in the Python starter | The same in the Python starter: `app/core/resources.py` and `prompts.py`, the `app/mcp` handlers, the tools file comment and the app's cases. | 1, 2 | `starter-python/apps/api/app/core/resources.py` and `prompts.py` (new), `starter-python/apps/api/app/core/tools.py` (the resource registration only), `starter-python/apps/api/app/core/__init__.py`, `starter-python/apps/api/app/mcp/**`, `starter-python/apps/api/app/projects/tools.py` (the comment), `starter-python/apps/api/tests/test_mcp.py` and `test_tools.py`, `tests/test_mcp_resources.py` | `tests/test_mcp_resources.py` (`test_1`, `test_2`: `python`) | RES, FORGE-MCP-1/TOOLSPY | no | |
| RESGUIDE | The guides carry the resource and prompt rules | The setup interview's question, the constitution's `## Agent tasks` section and Built in line, the planning and worker brief rules, the guide sentence and the synced skill copies, on new and existing repos. | 3 | `src/forge/templates/skill.md`, `src/forge/templates/brief.md`, `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `docs/guide.md`, `tests/test_mcp_resources_guide.py` (new) | `tests/test_mcp_resources_guide.py::test_3` (new) | FORGE-MCP-1/MCPGUIDE | no | |

RESGUIDE shares no file with RES or RESPY and needs no code from them, so it can run beside RES
once FORGE-MCP-1/MCPGUIDE merges. It also waits for any open part that changes the App
constitution section of `skill.md`; follow the merged text.

New moving parts: none. The resources and the prompts are in-memory lists that each tools file
fills at start, as the tools list is (items 1 and 2).

## Notes

- **Order.** RES waits for FORGE-MCP-1/TOOLS (the core tools file, the MCP module and the
  tests it changes). RESPY waits for FORGE-MCP-1/TOOLSPY and for RES, because both change
  `tests/test_mcp_resources.py`. RESGUIDE waits for FORGE-MCP-1/MCPGUIDE, because both change
  the same paragraphs of `skill.md` and `brief.md`.
- **Owner decisions (27 Oct 2026, settled).** Resources are always generated for each feature
  from the same schemas as its tools: one item at an address as a resource template, the
  feature's field guide (each field, its kind, required or not, allowed values) and lists of
  allowed values. Resources follow the agent account's permissions as tools do. Prompts only
  when the client notes describe a repeated workflow: the setup interview gets one question,
  "Which tasks will people ask an agent to do again and again?"; the agent writes one prompt for
  each answer in the feature's tools file, with the inputs the task needs; the default is none.
  No elicitation by default (Gantry Cloud handles approvals; Mainline sets tool rules). Sampling
  is never used. The guide, the worker brief and the feature command carry these rules. New
  repos get them at init; existing repos get the guide text on upgrade with `forge sync` and no
  app files. An app made from a starter before MCP keeps working, and the feature command builds
  a feature without resources there and says so. No new screens.
- **Owner decision after the first cold read (27 Oct 2026, settled).** No change notices in
  this story: no subscriptions, no `GET /mcp` stream and no notice tests. Agents read
  resources again when they need fresh data. Notices stay a later option, with MCP sessions and
  Postgres `LISTEN` and `NOTIFY`.
- **Planner choices the owner did not make.** (1) The field guide's kind is the JSON Schema
  type and format, because the starter's projects feature and hand-made features have no
  feature-command kind record. (2) The field guide holds only the feature's own fields, not the
  tool options `response_format` and `idempotency_key`. (3) The resource cases are in the MCP
  test file and are not copied for each new feature; the contract case finds every feature
  from the tools list and fails when one has no resources, and the live feature run checks a
  generated feature. (4) The feature command carries the prompt rule through the tools file's
  comment, which its copy renames, and through its no-MCP line; it writes no prompt. (5) The
  link between a prompt and a task under `## Agent tasks` is held by the guide and by the
  review, which reports work against the constitution as P1; Forge adds no check for it.
  (6) Resource reads do not count toward the limit of 120 calls a minute. (7) This story ships
  in the same release as FORGE-MCP-1.
- No client repo is named anywhere in this story's code, tests, texts or commits.
