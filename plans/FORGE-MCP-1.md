# Client apps ship an MCP server so agents can use their features

4 parts · Risks: none one-way · New moving parts: the MCP library in each starter

## What changes for you

- Every new app from either starter has an MCP server from the start. MCP is the standard way
  for AI agents to use an app's features as tools. Gantry Cloud agents, for example, can use the
  app through Mainline's gateway.
- The MCP server runs inside the app's API at `/mcp`. It uses the same code and the same
  permission checks as the screens. It is not a second container. `services.toml` marks the API
  service with `mcp = "/mcp"`, so Mainline can show it under Connectors.
- Each feature has six tools, made from the feature's own field rules: list, get, create,
  update, delete and restore. Each tool name is the feature name, an underscore and the action,
  such as `projects_list` or `work_orders_update`. Each tool has a short description in plain
  words.
- An admin adds an agent account on the Members screen and gives it the Admin or the Member role.
  The admin then creates a key for that agent account. The key shows one time only. The admin
  can revoke the key, and a revoked key stops working at once. Mainline's gateway sends the key.
- An agent acts as its agent account. Its role's permissions apply exactly as on the screens.
  Each change that an agent makes shows in the Change history as that agent account.
- Delete and restore tools are off until an admin turns them on for a feature. Each feature's
  list screen has an "Agent access" button for admins, with one switch for that feature. The
  list, get, create and update tools are always on. The agent's role still applies.
- An agent key can make 120 calls a minute. A call over the limit gets a clear refusal. A call
  with a missing or revoked key, a tool that the role cannot use, or a tool that is off also gets
  a clear refusal.
- A feature that the feature command builds gets its six tools at once. A developer can add a
  tool by hand, or hide a default tool, in the feature's one tools file.
- An agent cannot act for a person in this story. An agent always acts as its own account.
- Existing apps keep their code. On upgrade with `forge sync`, they get the guide text and the
  changed feature command. They get no MCP server, no `services.toml` change and no app file. In
  an app made from an older starter, the feature command builds the feature without tools and
  says so.

Design: docs/design/FORGE-MCP-1/ (a1de7c1d7f5c5bf9a059d738f91383c384bea40b)

## Why

Agents cannot use a client app's features today. Each feature is available only through the
app's screens and its API, and the API needs a person's sign-in cookie. Each app would need its
own hand-built connection for each agent. An MCP server in each starter gives every app the same
connection from the first commit. Agent accounts with a role keep agents inside the same
permissions and the same change history as people.

## Done when

1. **A new app from `forge init --starter` or `forge init --starter python` serves an MCP server at `/mcp` inside its API, and its `services.toml` marks that service with `mcp = "/mcp"`. A call with a missing or revoked agent key, or more than 120 calls in a minute on one key, gets a clear refusal. An app from plain `forge init` gets no MCP server and no `mcp` line.**
2. **An admin adds an agent account on the Members screen with the Admin or the Member role, creates its key, which shows one time only, and can revoke it. Each of these changes adds a Change history row.**
3. **With a valid key, an agent lists each feature's tools, which come from the feature's own schemas and are named `<feature>_<action>`, such as `projects_list`, and calls them as its agent account. The role's permissions apply as on the screens, a tool that the role cannot use is refused, and each change shows in the Change history as that agent. The delete and restore tools stay off, and a call to them is refused, until an admin turns on that feature's switch on its list screen.**
4. **A feature that the feature command builds gets its six tools at once, and a developer can hide a default tool or add a tool in the feature's one tools file. In an app made from an older starter, the command builds the feature without tools and says so.**
5. **The agent's guide, the worker brief and the deploy guide name the MCP server, the tools file and the `mcp` line. A new repo gets this text at `forge init`. An existing repo gets it on upgrade with `forge sync`, and gets no MCP server, no `services.toml` change and no app file.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none one-way. Each part reverts with its pull request. The new migrations add columns
with defaults and change no existing value.

Trade-off: a new dependency in each starter, the official MCP library (TypeScript and Python),
pinned to one exact version.

Trade-off: anyone who has an agent key can do what the agent's role can do. The key shows one
time only, the app keeps only its hash, and a revoke stops it at once.

Trade-off: the rate limit is counted in each running copy of the API. With two copies, an agent
can make up to 240 calls a minute.

Trade-off: an agent account cannot be removed, because the starter cannot remove members today.
An admin revokes its key instead.

Trade-off: only starter apps get the MCP server. An app from plain `forge init`, or an adopted
app, needs its own story for one.

Trade-off: Mainline shows the server under Connectors and its gateway sends the key. That is
Mainline's work. This story does not build it.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new test file starts with `STORY = "FORGE-MCP-1"`. Each Forge test runs the forge command
or, for the app's own behaviour, names the cases that the app's own `node scripts/test.mjs`
reports, and never imports forge. One test per Done-when item, named `test_<n>_...`. A part that
adds a side (the Python starter, the MCP half of item 3) adds a parameter or a case list to the
same test, not a new test. Live tests carry `@pytest.mark.platform` and
`@pytest.mark.timeout(1800)` and use `live_run`, `live_python_starter` and `_require_cases` from
`tests/test_starter_tree.py` and `tests/test_python_starter.py`, as
`tests/test_feature_access.py` does. `starter-smoke.yml` runs `tests/test_mcp.py` in both jobs
(`-k typescript` and `-k python`, as it runs `tests/test_feature_*.py`).

The existing-repo case for each rule uses the `tests/fixtures/adopted-v1.2.2/client` repo moved
to this release and synced, as `tests/test_feature_access.py::test_3` (`earlier adopted`) does.
Item 4's existing case uses the **adopted starter app** that FORGE-FEATURE-1 defines (the
current starter files copied into that fixture), with the MCP files removed, which is the shape
of an app made from the starter before this story.

**Design.** `docs/design/FORGE-MCP-1/SCREENS.md` is the source for every screen text, state and
layout: the Members screen's Add agent account dialog, the agent rows, the key dialog, the
revoke AlertDialog, and the Agent access dialog on a feature's list screen. Until it lands, the
texts below are the defaults.

**Both starters in step.** `forge init --starter python` copies the TypeScript `apps/web`, and
the Python live run runs every web flow. So AGENTS, which changes the web app's HTTP contract,
changes the TypeScript API, the Python API and the web app in the same part. TOOLS and TOOLSPY
add only the `/mcp` endpoint, which no web flow uses, so each changes one starter.

**Layout.** Paths follow the merged library layout (FORGE-LIBS-1) and the projects files as
FORGE-FEATURE-1 leaves them. Where a path here differs from the merged tree, follow the merged
tree.

### Words this story pins

The part named first owns each name; later parts use it and list that part under After.

- **Agent accounts (AGENTS).** An agent account is an `Account` with no usable password (its
  password hash is the empty string, which no password matches; sign-in refuses it with the usual
  wrong email or password message) and a `Membership` with `isAgent = true`. The admin gives a
  name: lower-case letters, digits and hyphens, 2 to 40 characters, starting with a letter. The
  account's email is `<name>-<6 random lower-case letters or digits>@agents.invalid`, so it is
  unique across organisations, can never receive mail, and the Members screen, the Change
  history and its CSV show it with no new column.
  - Database: `core."Membership"` gets `"isAgent" boolean NOT NULL DEFAULT false` and
    `"agentKeyHash" text NULL` with the unique constraint `"Membership_agentKeyHash_key"`;
    `core."Organisation"` gets `"agentDeleteRestore" text[] NOT NULL DEFAULT '{}'`, the
    features whose delete and restore tools are on. One new migration in each starter (the
    TypeScript migration folder `<UTC yyyyMMddHHmmss>_agents`, and the next Alembic revision
    `<next>_agents.py` chained to the head on main). Python names: `is_agent`,
    `agent_key_hash`, `agent_delete_restore`.
  - The key: `agent_` and 32 random bytes in base64url. The app keeps only its SHA-256 hex in
    `agentKeyHash` and returns the key once. One key per agent account: Create key sets a new
    hash (an old one stops working), Revoke key sets it to null.
  - Routes, all admin only (`@AdminOnly()`, Python `admin_only`), with OpenAPI docs as the
    other routes have them:
    - `POST /api/v1/agents` with `{ name, role }` (auth module, because it makes the account,
      as sign-up and invites do): makes the account, then calls the new
      `OrganisationsApi.addAgent(account, role, admin)`, which writes the membership and the
      history row. Returns the `Member`. A taken email (one chance in two billion for one name)
      gets the usual `409`.
    - `POST /api/v1/members/:accountId/key` returns `{ key }`;
      `DELETE /api/v1/members/:accountId/key` returns 204. A person's membership, or another
      organisation's, gets `404 MEMBER_NOT_FOUND`.
    - `GET /api/v1/agent-tools` returns `{ deleteAndRestore: string[] }`;
      `PUT /api/v1/agent-tools/:feature` with `{ deleteAndRestore: boolean }` adds or removes
      the feature. `:feature` must match `^[a-z][a-z0-9-]*$`; nothing else checks it
      (`ponytail:` comment: an unknown name is stored and does nothing).
  - History rows (organisations module, through `HISTORY_API`, in the same transaction):
    `agent.added` `Added the agent account <email> as <Role>`, `agent.key-created`
    `Created a key for <email>`, `agent.key-revoked` `Revoked the key for <email>`,
    `agent-tools.changed` `Turned on agent delete and restore for <feature>` (or `Turned off`).
  - `Member` gets `isAgent: boolean` and `hasKey: boolean`.
  - `OrganisationsApi.agentForKey(keyHash: string): Promise<{ principal: OrganisationPrincipal & { role: Role }; deleteAndRestore: string[] } | null>`
    reads the membership by `agentKeyHash` and its organisation's `agentDeleteRestore` in one
    query. Python: `agent_for_key(db, key_hash)` on the organisations public service, returning
    an `AccountPrincipal` and the list, or `None`. AGENTS adds it with no caller; TOOLS and
    TOOLSPY call it.
- **Screens (AGENTS).** On the Members screen, admins see `Add agent account` beside `Invite`.
  Its dialog has `Name` (help text `Lower-case letters, numbers and hyphens, such as gantry.`),
  `Role` (Admin or Member, Member first), and `Cancel` and `Add agent account`. An agent row
  shows an `Agent` Badge after its email. For an agent row, admins see `Create key` when it has
  no key and `Revoke key` when it has one. Create key opens a dialog with the key in a read-only
  field, a `Copy` button, the text `Copy this key now. You cannot see it again.` and `Done`.
  Revoke key opens an AlertDialog `Revoke this key? Agents that use it stop working at once.`
  with `Cancel` and `Revoke key`. Members see agent rows and no buttons. On each feature's list
  screen, admins see `Agent access` beside `Export CSV`. Its dialog has one Switch,
  `Agents can delete and restore <plural>`, the line
  `Agents still need a role that can delete and restore. List, view, create and edit are always on.`,
  and `Done`; a change saves at once with the toast `Agent access updated.` The dialog is one
  component, `AgentAccessDialog({ feature, label })`, in `libs/core/web/src/agent-access-dialog.tsx`,
  exported from `@app/core-web`, with its own response type, so a feature's web library uses it
  within the boundary rules. The projects list page renders
  `<AgentAccessDialog feature="projects" label="projects" />`, so the feature command's web copy
  renames it.
- **The tools file (TOOLS pins it; TOOLSPY follows it).** The one place per feature, beside its
  permissions file: `libs/<plural>/server/src/<plural>.tools.ts`, Python
  `apps/api/app/<plural>/tools.py`. For projects:
  ```ts
  /** The one place that says which tools agents get for projects. */
  defineFeatureTools({ feature: 'projects', one: 'project', permissions: PROJECT_PERMISSIONS,
    listQuery: projectListQuerySchema, input: projectSchema, service: this.projects, hide: [] });
  ```
  called from `onModuleInit` of an `@Injectable()` `ProjectsTools` class that the projects
  module lists as a provider (Python: called at import, and `app/projects/__init__.py` imports
  `tools`). `hide` takes action names (`'delete'`). `defineTool({ name, description, input, permission, call })`
  adds a hand-made tool; `call(principal, args)` returns the result. Both are in
  `libs/core/server/src/common/tools.ts`, exported from `@app/core-server` (Python
  `app/core/tools.py`, exported from `app.core`), and fill one in-memory list, as
  `definePermissions` does. A second tool with the same name throws at start.
- **Tool names and descriptions (TOOLS).** `<feature>_<action>`, where `<feature>` is the
  plural in snake form and `<action>` is `list`, `get`, `create`, `update`, `delete` or
  `restore`: `projects_list`, `work_orders_get`. A hand-made tool uses the same form with its own
  verb (`invoices_send`). Descriptions: `List <plural> in your organisation, newest change first. Takes search, filters, sort and a cursor.`,
  `Get one <singular> by its id.`, `Create a <singular>.`, `Replace the fields of a <singular>.`,
  `Delete a <singular>. An admin can restore it.`, `Restore a deleted <singular>.`.
- **Tool inputs and results (TOOLS).** list takes the list query schema; get, delete and
  restore take `{ id }` (a uuid); create takes the input schema; update takes `{ id }` and the
  input schema's fields. The input JSON Schema comes from the same schema: `z.toJSONSchema(schema, { io: 'input' })`,
  Python `model_json_schema()`. Each call parses the arguments with the same schema. The result
  is the same JSON that the REST route returns in `data`, as `structuredContent` and as one text
  item; delete returns the text `Deleted the <singular>.` A refusal is a tool result with
  `isError: true`, `structuredContent` `{ code, message, details }` and the text
  `<message>`: a schema error gives the API's `VALIDATION_FAILED` details, a missing item
  `<SINGULAR>_NOT_FOUND`.
- **Which tools an agent sees (TOOLS).** `tools/list` returns only the tools that the agent's
  role has the permission for and that are on. A call to a tool checks the same two things, in
  this order: a role without the permission gets `PERMISSION_DENIED`
  `You do not have permission to do this.`; a delete or restore tool whose feature is not in
  `deleteAndRestore` gets `TOOL_OFF` `An admin has not turned on this tool for agents.`. The
  permission for each action is the feature's REST one: list and get `.view`, create `.create`,
  update `.edit`, delete `.delete`, restore `.restore`. The role and the switch are read on each
  call, so a change applies at the next call.
- **The endpoint (TOOLS for TypeScript, TOOLSPY for Python).** `/mcp`, Streamable HTTP,
  stateless (no session id) with JSON responses, so it needs no store and works with more than
  one copy of the API. It reads `Authorization: Bearer <key>`, hashes it, and calls
  `agentForKey`. A missing, unknown or revoked key gets HTTP `401` with the API's error envelope
  `{ code: 'UNAUTHENTICATED', message: 'Send a valid agent key.' }`, before any MCP message is
  read. Over the limit gets HTTP `429` with the existing `RATE_LIMITED`
  `Too many requests. Wait and try again.`. The server name is the app's name from
  `package.json` (Python `pyproject.toml`).
- **The rate limit (TOOLS, TOOLSPY).** 120 calls a minute per key, counted by the SHA-256 of the
  `Authorization` header, in memory. TypeScript: the installed `@nestjs/throttler`; the MCP
  route skips the default per-address limit (the gateway sends every agent's calls from one
  address) and has its own limit with that tracker. Python: `_is_rate_limited` in
  `app/core/security.py` gets a `limit` argument (default `_RATE_LIMIT_COUNT`) and the `/mcp`
  check uses 120 with the header hash as the client. Keep the existing
  `ponytail: per instance` comment true for both.
- **`services.toml` (TOOLS for TypeScript, TOOLSPY for Python).** Each starter gets its own
  `services.toml`, which replaces the skeleton's at init, because the starter files come after
  the skeleton in `init._scaffold`:
  ```toml
  [[service]]
  name = "app"
  dockerfile = "Dockerfile"
  port = 3000
  health = "/health"
  expose = "main"
  mcp = "/mcp"
  ```
  The skeleton file does not change, so plain `forge init` gets no `mcp` line. Close does not
  check `mcp` (the `ponytail:` comment in `app_baseline.services` stays true).
- **Generated test names.** The projects cases sit in the projects test files, so the feature
  command's copy gives each new feature the same cases with its words:
  `an agent lists the project tools and creates, reads, lists and updates a project through MCP`,
  `a member agent cannot delete or restore a project through MCP`,
  `project delete and restore tools stay off until an admin turns them on`, and the flow
  `an admin turns on agent delete and restore for projects`. The starter-wide cases:
  `an admin adds an agent account and creates and revokes its key`,
  `a member cannot add an agent account or change its key or agent access`,
  `an agent account cannot sign in with a password`,
  `the MCP server refuses a missing or revoked agent key`,
  `the MCP server refuses an agent key over its rate limit`,
  `a tools file can hide a default tool and add its own`, and the flow
  `an admin adds an agent account, creates its key once and revokes it`. The Python cases use
  the same names in the snake form that FORGE-DEFAULTS-1 pins.

### Done-when details

1. The MCP server and the services list (TOOLS for TypeScript, TOOLSPY for Python).
   - TypeScript: a new module library `libs/mcp/server` (`@app/mcp-server`, tags `type:server`
     and `scope:mcp`, with `package.json`, `project.json` and `tsconfig.json` as the other
     server libraries have them) with `McpModule` and `McpController`. The controller is
     `@Public()` (the session guard skips it; the CSRF guard passes a call with no session and
     no foreign `Origin`, as today). It uses the MCP library's low-level `Server` with the
     `tools/list` and `tools/call` handlers over the core tools list, and
     `StreamableHTTPServerTransport` with `sessionIdGenerator: undefined` and
     `enableJsonResponse: true`, one per request. Wiring: `McpModule` in `app.module.ts`, the
     `scope:mcp` line under the module lines' comment in `eslint.config.mjs`, the package in
     `apps/api/package.json` and the reference in `apps/api/tsconfig.json`, its importer in
     `pnpm-lock.yaml`, its `dist` folder in `scripts/test-build.mjs`; in `main.ts`, `mcp`
     excluded from `setGlobalPrefix` and `/mcp` excluded from the web app's fallback route.
     The MCP library `@modelcontextprotocol/sdk` at one exact version (the newest release at
     least two weeks old) in the root `package.json` and the lock file.
   - Python (TOOLSPY): `apps/api/app/mcp/` (`__init__.py`, `server.py`) with the `mcp`
     library's low-level `Server` and `StreamableHTTPSessionManager(stateless=True, json_response=True)`,
     mounted at `/mcp` in `main.py` before the web app's catch-all route, which also skips
     `mcp`; the session manager runs inside the app's lifespan. Each call opens a database
     session from `app.state.session_factory`. The `mcp internals` import-linter contract in
     `apps/api/pyproject.toml`, and `mcp==<one exact version>` in its dependencies and
     `uv.lock`.
   - The app's own cases: `apps/api/test/mcp.e2e-spec.ts` (Python `apps/api/tests/test_mcp.py`),
     through the running API with the MCP library's client and Streamable HTTP client transport:
     `the MCP server refuses a missing or revoked agent key` (no header, an unknown key, and a
     key after Revoke key each get 401 with `UNAUTHENTICATED`; a key from Create key works
     before the revoke) and `the MCP server refuses an agent key over its rate limit` (121
     `tools/list` calls in a minute on one new key: the last one gets 429 `RATE_LIMITED`, and a
     second new key still works). A helper `agentClient(key)` in `apps/api/test/helpers.ts`
     (Python: `agent_client(key)` in `tests/conftest.py`) makes the client; the projects cases
     use it too.
   - Test `tests/test_mcp.py::test_1_a_new_starter_app_serves_its_mcp_server`, parameters
     `typescript` (TOOLS), `python` (TOOLSPY), `plain` and `earlier adopted` (TOOLS). Starter
     cases: `_fresh_client(repo, gh, tmp_path, "--starter", kind)`; `tomllib.loads` of
     `services.toml` gives the one service above with `"mcp": "/mcp"`; `git ls-files` lists it;
     live, the API report holds the two refusal cases. `plain`: `_fresh_client` with no starter;
     `services.toml` has no `mcp` key and the repo has no `libs/mcp`. `earlier adopted`: after
     upgrade and `forge sync`, the repo has no `services.toml`, no `libs/mcp` and no
     `apps/api/app/mcp`, and `git status --porcelain` lists only files that sync writes.
   - Change `tests/test_services_list.py::test_1`: the `react` (TOOLS) and `python` (TOOLSPY)
     cases expect the `mcp` key; `plain` and `plain-own-dockerfile` stay as they are.
2. Agent accounts and keys (AGENTS).
   - Both APIs and the web app as **Agent accounts** and **Screens** above say. Web:
     `libs/organisations/web/src/pages/members-page.tsx`, the new
     `add-agent-dialog.tsx` and `agent-key-dialog.tsx` beside `invite-dialog.tsx`, and the
     hooks in `members-hooks.ts`. The key dialog keeps the key only in component state, and
     closing it drops the key.
   - The app's own cases, in `apps/api/test/agents.e2e-spec.ts` (Python `tests/test_agents.py`):
     `an admin adds an agent account and creates and revokes its key` (the member list shows
     the agent with `isAgent` and `hasKey`, the key starts with `agent_`, a second Create key
     returns a new key, and `/api/v1/history` holds the three rows with the admin as actor);
     `a member cannot add an agent account or change its key or agent access` (403 on each
     route; another organisation's agent gets 404); `an agent account cannot sign in with a password`.
     The flow `an admin adds an agent account, creates its key once and revokes it` in
     `apps/web/e2e/members.spec.ts`: after `Done`, the key is not on the page.
   - Test `tests/test_mcp.py::test_2_an_admin_adds_an_agent_account_and_its_key`, parameters
     `typescript`, `python` and `earlier adopted`: live, the API and browser reports hold the
     cases above. `earlier adopted`: after upgrade and sync, the files under `libs/` and
     `apps/` are unchanged, as `test_feature_access.py::test_3` checks.
3. Each feature's tools (AGENTS for the switch; TOOLS and TOOLSPY for the tools).
   - AGENTS: the Agent access dialog, its routes and its history row; the flow
     `an admin turns on agent delete and restore for projects` in `apps/web/e2e/projects.spec.ts`
     (an admin turns it on, reloads, sees it on, turns it off; a member sees no `Agent access`).
   - TOOLS: the core tools list, `projects.tools.ts`, and the projects cases in
     `apps/api/test/projects.e2e-spec.ts`, outside the marks that the feature command fills:
     - `an agent lists the project tools and creates, reads, lists and updates a project through MCP`:
       a Member agent's `tools/list` holds exactly `projects_list`, `projects_get`,
       `projects_create` and `projects_update`, each with its description and an input schema
       that has the projects fields; create, get, list (with `search`) and update each return
       what the REST route returns; a create with a bad field gets `isError` with
       `VALIDATION_FAILED`; `/api/v1/history` and the project's changes show the agent's email
       as the actor of the create and the update.
     - `a member agent cannot delete or restore a project through MCP`: with the switch on, a
       Member agent's list has no delete or restore tool, and a call to `projects_delete` gets
       `PERMISSION_DENIED` and leaves the project.
     - `project delete and restore tools stay off until an admin turns them on`: an Admin
       agent's list has four tools and its `projects_delete` call gets `TOOL_OFF`; after the
       admin's `PUT /api/v1/agent-tools/projects`, the list has six, delete and restore work,
       and the history shows `Deleted the project` and `Restored the project` with the agent
       as actor; after the admin turns it off, the list has four again.
   - TOOLSPY: `app/core/tools.py`, `app/projects/tools.py` and the same cases in
     `tests/test_projects.py`.
   - Test `tests/test_mcp.py::test_3_an_agent_uses_each_features_tools_as_its_account`,
     parameters `typescript`, `python` and `earlier adopted`: live, the reports hold the
     projects cases and the flow (AGENTS adds the flow and the parameters; TOOLS and TOOLSPY
     add the API cases). `earlier adopted`: after upgrade and sync, the projects files are
     unchanged.
4. The feature command's tools (TOOLS for TypeScript, TOOLSPY for Python).
   - `src/forge/feature_api.py`: add `libs/projects/server/src/projects.tools.ts` to the plain
     renamed copies beside `projects.permissions.ts`. When the app has no
     `libs/core/server/src/common/tools.ts`, the command writes no tools file, leaves out the
     lines between `// forge:feature:tools:start` and `// forge:feature:tools:end` in the copied
     module (the `ProjectsTools` import and provider; TOOLS adds these marks to
     `projects.module.ts`), and prints
     `This app has no MCP server, so <plural> get no agent tools.` after the files it wrote. It
     still exits 0. `src/forge/feature_tests.py` renders the copied MCP cases with the kind
     table's `sample`, `changed` and `bad` values, as it renders the other API cases.
   - TOOLSPY: the same in the Python copy that FORGE-FEATURE-1/PY adds: `app/projects/tools.py`
     copied, and the `tools` import line in `app/projects/__init__.py` between
     `# forge:feature:tools:start` and `# forge:feature:tools:end`, left out when the app has no
     `apps/api/app/core/tools.py`.
   - Hide and hand-made tools: the app's own unit case `a tools file can hide a default tool and add its own`,
     in `libs/core/server/src/common/tools.test.ts` (run by `test:hooks`, whose include list
     takes `libs/*/*/src/**/*.test.ts`) and Python `tests/test_tools.py` (imports `app.core`,
     no HTTP): a feature defined with `hide: ['delete']` and one `defineTool` has no `_delete`
     tool, has the hand-made one with its permission, and a second tool with the same name
     throws.
   - Test `tests/test_mcp.py::test_4_the_feature_command_adds_the_features_tools`, parameters
     `typescript` (TOOLS), `python` (TOOLSPY) and `older starter` (TOOLS). In a new starter app,
     `forge task feature jobs --one job --field 'name:text' --field 'status:status(planned|active|done)'`
     exits 0 and writes `libs/jobs/server/src/jobs.tools.ts` (Python `apps/api/app/jobs/tools.py`)
     with `feature: 'jobs'` and `JOB_PERMISSIONS`. Live: the feature run that
     FORGE-FEATURE-1's test_2 caches holds the copied cases for its `jobs` feature
     (`an agent lists the job tools and creates, reads, lists and updates a job through MCP`
     and the other two) and the flow `an admin turns on agent delete and restore for jobs`;
     the starter's report holds `a tools file can hide a default tool and add its own`.
     `older starter`: the adopted starter app with `libs/core/server/src/common/tools.ts` and
     `libs/mcp` removed: the same line exits 0, writes no tools file, the copied module has no
     `JobsTools` line, and the output has the no-MCP line.
5. The guides (MCPGUIDE).
   - `src/forge/templates/skill.md`:
     - In the constitution outline's `## Fixed rules`, after the change history line:
       `- Built in: the API serves an MCP server at /mcp. An admin adds agent accounts on the Members screen, with a role and a key that shows once; agents use each feature's tools with that role's permissions, and delete and restore tools stay off until an admin turns them on for the feature.`
       And the same sentence in the Python fixed rules list.
     - In the services paragraph at the top, after `when needed, \`subdomain\` and \`command\``:
       `, and \`mcp\` with the path of the service's MCP server`; and after its write rule:
       `In a starter app, the API service has mcp = "/mcp".`
     - In Planning a story, after FORGE-FEATURE-1/GUIDE's feature command paragraph:
       "In a starter app, each feature's agent tools are in its one tools file
       (`libs/<plural>/server/src/<plural>.tools.ts`, Python `apps/api/app/<plural>/tools.py`),
       and the feature command writes it. When a story adds a route that agents need, the part
       names the hand-made tool, its name in the form `<feature>_<verb>` and its permission.
       When the owner wants a default tool hidden, the part says so."
   - `src/forge/templates/brief.md`, after FORGE-FEATURE-1/GUIDE's permission sentence:
     "In an app with `libs/core/server/src/common/tools.ts` (Python `app/core/tools.py`), a
     feature's agent tools are in its tools file. Add a tool there only when your part names
     it, with `defineTool` and one permission, and hide a default tool only with `hide`. Never
     call a feature's service from the MCP module." And in the `services.toml` sentence, after
     `start command`: `or MCP path`.
   - `src/forge/templates/conventions/deploy.md`, in the services paragraph, after the
     `command` sentence: "An optional `mcp` is the path where the service serves its MCP
     server, such as `/mcp`; Mainline shows it under Connectors, and its gateway sends the
     agent key that an admin creates in the app."
   - `docs/guide.md`: one paragraph after the feature command's: the MCP server at `/mcp`, the
     six tools and their names, agent accounts and keys, the switch, the limit, the tools file,
     and that only starter apps get it.
   - `forge sync` rewrites `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md`.
   - Test `tests/test_mcp_guide.py::test_5_the_guides_name_the_mcp_server`, parameters
     `new init` and `previous release`, with the setup of
     `tests/test_services_guide.py::test_3` and whitespace collapsed: the synced skill copies
     have the Built in sentence, `mcp = "/mcp"` and the tools-file sentence; the worker brief
     from `forge work` has `a feature's agent tools are in its tools file` and
     `Never call a feature's service from the MCP module`; the installed deploy guide has
     `Mainline shows it under Connectors`. `previous release`: after `forge sync`, the repo has
     no `services.toml`, and `git status --porcelain` lists only files that sync writes.

### New and existing repos

- **New repos** (`forge init --starter`, `forge init --starter python`): the MCP server at
  `/mcp`, `services.toml` with `mcp = "/mcp"`, agent accounts and keys on the Members screen,
  the Agent access switch on the projects list, the projects tools file, the guide text, and a
  feature command that writes each feature's tools. Plain `forge init`: the skeleton
  `services.toml` with no `mcp` line, no MCP server, the guide text. A newly adopted app
  (`forge init` on a repo with history): the guide text, no app file.
- **Existing repos** (on upgrade to this release, after `forge sync`): the guide text, and the
  release's feature command. No `services.toml` change, no MCP server and no app file: sync
  writes no app file. In an app made from the starter before this story, the feature command
  builds the feature without tools and says so. Tested on the adopted earlier-release fixture in
  each item, and on the older starter app in item 4.

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
| AGENTS | Agent accounts and the delete and restore switch | Agent accounts, their keys and the agent access list in both APIs, with their migrations, history rows and `agentForKey`; the Members screen's agent dialogs and rows; the Agent access dialog in core web and on the projects list; the app's own cases and flows. | 2, 3 | `starter/libs/organisations/**`, `starter/libs/auth/server/**` (the agents route only), `starter/libs/core/web/src/agent-access-dialog.tsx` (new), `starter/libs/core/web/src/index.ts`, `starter/libs/projects/web/src/pages/projects-page.tsx` (the dialog line only), `starter/apps/api/prisma/schema/organisations.prisma`, `starter/apps/api/prisma/migrations/<new>_agents/` (new), `starter/apps/api/test/agents.e2e-spec.ts` (new), `starter/apps/web/e2e/members.spec.ts`, `starter/apps/web/e2e/projects.spec.ts`, `starter-python/apps/api/app/organisations/**`, `starter-python/apps/api/app/auth/**` (the agents route only), `starter-python/apps/api/migrations/versions/<next>_agents.py` (new), `starter-python/apps/api/tests/test_agents.py` (new), `starter-python/libs/organisations/contracts/**`, `starter-python/libs/shared/api-types/**` (regenerated), `.github/workflows/starter-smoke.yml`, `tests/test_mcp.py` (new) | `tests/test_mcp.py` (`test_2`; `test_3` with the flow, `typescript`, `python`, `earlier adopted`) | FORGE-FEATURE-1/WEB | yes | |
| TOOLS | The MCP server and tools in the TypeScript starter | The core tools list, the `libs/mcp/server` module at `/mcp` with key check and rate limit, the projects tools file, the starter's `services.toml`, the MCP cases, and the feature command's tools copy with its no-MCP rule. | 1, 3, 4 | `starter/libs/core/server/src/common/tools.ts` and `tools.test.ts` (new), `starter/libs/core/server/src/index.ts`, `starter/libs/mcp/server/**` (new), `starter/libs/projects/server/src/projects.tools.ts` (new), `starter/libs/projects/server/src/projects.module.ts`, `starter/apps/api/src/app.module.ts`, `starter/apps/api/src/main.ts`, `starter/apps/api/package.json`, `starter/apps/api/tsconfig.json`, `starter/package.json`, `starter/pnpm-lock.yaml`, `starter/eslint.config.mjs`, `starter/scripts/test-build.mjs`, `starter/services.toml` (new), `starter/apps/api/test/helpers.ts`, `starter/apps/api/test/mcp.e2e-spec.ts` (new), `starter/apps/api/test/projects.e2e-spec.ts` (the MCP cases), `src/forge/feature_api.py`, `src/forge/feature_tests.py`, `tests/test_mcp.py`, `tests/test_services_list.py` (`test_1`, `react`) | `tests/test_mcp.py` (`test_1` `typescript`, `plain`, `earlier adopted`; `test_3` API cases, `typescript`; `test_4` `typescript`, `older starter`) | AGENTS, FORGE-FEATURE-1/WEB | no | |
| TOOLSPY | The MCP server and tools in the Python starter | The same in the Python starter: the core tools list, the `app/mcp` package at `/mcp`, the rate limit, the projects tools file, the starter's `services.toml`, the MCP cases, and the Python feature copy's tools file. | 1, 3, 4 | `starter-python/apps/api/app/core/tools.py` (new), `starter-python/apps/api/app/core/__init__.py`, `starter-python/apps/api/app/core/security.py`, `starter-python/apps/api/app/mcp/**` (new), `starter-python/apps/api/app/main.py`, `starter-python/apps/api/app/projects/tools.py` (new), `starter-python/apps/api/app/projects/__init__.py`, `starter-python/apps/api/pyproject.toml`, `starter-python/apps/api/uv.lock`, `starter-python/services.toml` (new), `starter-python/apps/api/tests/conftest.py`, `starter-python/apps/api/tests/test_mcp.py`, `test_tools.py` (new) and `test_projects.py` (the MCP cases), `src/forge/feature*.py` (the Python copy only), `tests/test_mcp.py`, `tests/test_services_list.py` (`test_1`, `python`) | `tests/test_mcp.py` (`test_1`, `test_3`, `test_4`, `python`) | TOOLS, FORGE-FEATURE-1/PY | no | |
| MCPGUIDE | The guides name the MCP server | The constitution's Built in line, the services and tools-file sentences in the agent's guide, the worker brief's tools rule, the deploy guide's `mcp` sentence, the guide paragraph and the synced skill copies, on new and existing repos. | 5 | `src/forge/templates/skill.md`, `src/forge/templates/brief.md`, `src/forge/templates/conventions/deploy.md`, `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `docs/guide.md`, `tests/test_mcp_guide.py` (new) | `tests/test_mcp_guide.py::test_5` (new) | FORGE-FEATURE-1/GUIDE | no | |

MCPGUIDE shares no file with the other parts and needs no code from them, so it can run beside
AGENTS once FORGE-FEATURE-1/GUIDE merges.

New moving parts: the MCP library, `@modelcontextprotocol/sdk` in the TypeScript starter and
`mcp` in the Python starter, each pinned to one exact version (item 1). The tools list in core is
a plain in-memory list that each feature fills at start, as the permissions list is (item 3); no
service, store or cache.

## Notes

- **Order with FORGE-FEATURE-1.** Its COMMAND, PAGING, DETAIL and ACCESS parts are on main. This
  story waits for its three open parts: WEB (AGENTS changes the projects list page and its flows,
  which WEB marks and copies; TOOLS changes `feature_api.py` and `feature_tests.py`, which WEB
  extends), PY (TOOLSPY changes the Python copy that PY adds), and GUIDE (MCPGUIDE adds to the
  same skill, brief and guide paragraphs). All four parts ship in one release.
- **Order in this story.** AGENTS first: the agent key and the switch list are what the MCP
  server reads. TOOLS next; it pins the tools file and the tool names. TOOLSPY after TOOLS: both
  change `tests/test_mcp.py` and `tests/test_services_list.py`. AGENTS must keep
  FORGE-FEATURE-1's feature live run green: WEB's copy of the projects list page now carries the
  Agent access dialog and its flow for each new feature.
- **Migration order.** AGENTS's migrations and any other open migration can merge in either
  order. The part that merges later gives its Prisma folder a later timestamp and chains its
  Alembic revision to the head on main.
- **Part sizes.** AGENTS changes both APIs and the web app, so it may pass 400 lines; split the
  regenerated `openapi.json` and `api-types.ts` out of the count, and ask for
  `forge fix allow-large` with that reason before you split it.
- **Owner decisions (27 Oct 2026, settled).** Every client app built with Forge ships an MCP
  server from the start, so agents, such as Gantry Cloud agents through Mainline's gateway, can
  use the app's features as tools. Tools come from each feature's zod or Pydantic schemas: list,
  get, create, update, delete and restore; the feature command adds a new feature's tools; a
  developer can add tools by hand and hide a default tool; clear names and descriptions, such as
  `projects_list`. Auth is an agent account that an app owner adds on the Members screen with a
  role (Admin or Member) and a key that shows once and can be revoked; the MCP server acts as
  that account, its role's permissions apply as on the screens, and its changes show in the
  change history as that agent; no acting for a person. It runs inside the API process at
  `/mcp` (Streamable HTTP) and reuses the API's services and permission checks;
  `services.toml` marks the service with its MCP path; no second container. Delete and restore
  tools are generated but off until an owner turns them on for the feature, one switch per
  feature stored in the app; list, get, create and update are on. A simple per-key rate limit
  with a clear refusal, from each starter's existing mechanism. Tests: the tool list and each
  tool through the running MCP service in both starters' live runs, and a refusal for a missing
  or revoked key, a missing permission, a tool that is off, and the rate limit. Existing apps get
  the guide text and the feature-command change with `forge sync`, but no new service files or
  app code. One web change: the Members screen gets Add agent account and the agent's key, and
  each feature gets the delete and restore switch.
- **Planner choices the owner did not make.** (1) The starter's roles are Admin and Member, with
  no Owner role, so an admin adds agent accounts, manages keys and turns the switches. (2) An
  agent account's email is `<name>-<6 random characters>@agents.invalid` with no password, so
  the Members screen, the history and its CSV need no new column; the key's hash is on the
  membership, one key per agent, and Create key replaces the old one. (3) The switch is an
  `Agent access` dialog on each feature's list screen, stored as one list column on the
  organisation; its route checks only the form of the feature name. (4) The limit is 120 calls a
  minute per key, in memory per running copy, and the TypeScript MCP route skips the per-address
  default limit, because the gateway sends all agents' calls from one address. (5) `tools/list`
  shows only the tools that the agent can call now. (6) The feature command in an app made from
  an older starter builds the feature without tools and says so, instead of a refusal. (7) The
  MCP server is stateless with JSON responses, so it needs no session store and works with more
  than one copy of the API. (8) The field is `mcp = "/mcp"` on the API's service in each
  starter's own `services.toml`; plain init keeps the skeleton file without it, and close does
  not check it.
- **For Mainline (context only).** Assumptions: Mainline reads the `mcp` field to show the
  server under Connectors, and its gateway sends `Authorization: Bearer <agent key>` to
  `<service address>/mcp`.
- No client repo is named anywhere in this story's code, tests, texts or commits.
