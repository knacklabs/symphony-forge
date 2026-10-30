# Client apps can split into services and frontends later without a rewrite

5 parts · Risks: none one-way · New moving parts: none

## What changes for you

- A new TypeScript client app keeps each module's code in three libraries: its contracts (the
  forms' rules, the data types and the module's public service), its server code and its
  screens. General helpers go in one shared library, and the shared screen parts go in another.
- The tests fail when a module uses another module's server code or screens directly. A module
  uses another module only through that module's contracts.
- A new Python client app keeps its API as it is. Its web app gets the same screen libraries and
  the same rule, with its data types still made from the API's OpenAPI file.
- In both starters, each module keeps its tables in its own Postgres schema. The organisation,
  account and sign-in tables are in one `core` schema. A link from one business module to
  another stores the item's id with an index and no foreign key, and a review reports a foreign
  key between two business-module schemas.
- At setup, the agent asks up to five growth questions when the client notes touch a topic and do
  not answer it: the users and records in year one and year three, heavy background work, other
  systems that call in or are called, rules on where the data stays, and parts that can become
  their own product. The answers go in the constitution as growth notes, which later stories read.
- Screens, API routes and data stay the same. Existing client apps keep their layout, tables and
  schemas on upgrade. They get only the guide and the review text.

Design: none (no screen changes; it moves code into libraries, adds lint and review rules, and puts each module's tables in a schema)

## Why

The TypeScript starter's `libs/shared` mixes every module's form rules and types with general
helpers, and each module's screens sit in the web app's `features` folder. All the modules' tables
are in one schema, with foreign keys between them. So a later split into services or separate
frontends means a rewrite. If the libraries and schemas follow the module lines from day one, a
later split moves whole libraries and schemas. This story must land before FORGE-FEATURE-1's
parts, which copy each feature into these libraries, and before FORGE-DATABASE-1's COLUMNS part,
which changes the same tables.

## Done when

1. **A new TypeScript app has `shared/util`, `core/server` and, for each module, `contracts` and `server` libraries, and its lint fails when a module imports another module's server library or a web library imports a server library.**
2. **A new TypeScript app's screens are in each module's `web` library, with the shadcn components and shell parts in `shared/ui` and the API client in `core/web`, its lint fails when one module's web library imports another's, and its browser flows pass unchanged.**
3. **A new Python app's API files stay as they are, its web app uses the same web libraries with types made from its OpenAPI file, and its lint fails when one module's web library imports another's.**
4. **In both starters, each module's tables are in its own Postgres schema and the core tables in `core`, a link between business modules has an index and no foreign key, and a review reports a foreign key between two business-module schemas.**
5. **At setup, the agent asks each growth question only when the client notes touch its topic and do not answer it, and writes the answers as growth notes in the constitution.**
6. **An existing app's code, tables and schemas are unchanged after upgrade, and it gets only the guide and review text.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none one-way. Each part reverts with its pull request. The schema migrations change only
the starters, which a new app copies at setup; no existing app gets them.

Trade-off: a link between two business modules has no foreign key, so the database does not stop
a link to a missing item. The module checks the link through the other module's public service,
and records are soft deleted, so a missing row is rare. Links to an organisation or an account
keep their foreign key.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new test file starts with `STORY = "FORGE-LIBS-1"`. Tests run the forge command or the
starters' own commands (lint, typecheck, their API and browser suites) in a copy of the starter,
and never import forge. One test per Done-when rule, named `test_<n>_...`. Live tests carry
`@pytest.mark.platform` and `@pytest.mark.timeout(1800)` and use `live_run` and `_require_cases`
from `tests/test_starter_tree.py`, so each stack runs once per session.

**Plan against the merged starter.** SERVER starts after FORGE-SINGLECO-1/COMPANYAPI and
COMPANYPY, WEB after FORGE-SINGLECO-1/COMPANYWEB. They edit the files this story
moves. Read the merged tree first; where a path below differs from it, follow the merged tree and
move the new files the same way.

**Large moves.** SERVER and WEB are mostly `git mv` and import-line changes. Each keeps the
starter and the Python starter building on its own. When a part goes over the size limit, run
`forge fix allow-large "A pure move of the starter's libraries; most lines are renames and import paths"`.
Use `git mv` so that review sees renames.

### Words this story pins

The part named first owns each name; later parts use it and list that part under After.

- **Libraries and packages (SERVER, WEB).** One folder for each library, one package name for
  each, `exports` with only `.` (except shared/ui, below):

  | Folder | Package | Holds | Tags |
  |---|---|---|---|
  | `libs/shared/util` | `@app/shared-util` | `format.ts`; `csv-field.ts` (the CSV cell quoting and formula guard, out of `core`'s `csv.ts`); `envelope.ts` (`ApiEnvelope<T>`, the response shape that `core/server` sends and `core/web` reads); `errorReportSchema` and `ErrorReportInput`. No business words. | `type:util`, `scope:shared` |
  | `libs/shared/ui` | `@app/shared-ui` | `src/components/ui/*` (shadcn), `src/lib/utils.ts`, `src/hooks/use-mobile.ts`, `src/components/theme-provider.tsx`, `src/components/auth-page-frame.tsx` | `type:ui`, `scope:shared` |
  | `libs/core/server` | `@app/core-server` | all of today's `libs/core/src` (database, guards, principal, envelope, logger, mail, CSV sender, error reports) | `type:server`, `scope:core` |
  | `libs/core/web` | `@app/core-web` | `api-client.ts`, `form-errors.ts`, `error-report.ts`, `route-error-page.tsx`, and `query-client.ts` (the `QueryClient` from `main.tsx`) | `type:web`, `scope:core` |
  | `libs/<module>/contracts` | `@app/<module>-contracts` | the module's zod schemas, types and public service interface | `type:contracts`, `scope:<module>` |
  | `libs/<module>/server` | `@app/<module>-server` | today's `libs/<module>/src` | `type:server`, `scope:<module>` |
  | `libs/<module>/web` | `@app/<module>-web` | the module's pages and hooks, out of `apps/web/src/features/<module>` | `type:web`, `scope:<module>` |

  Modules: `auth`, `organisations`, `history`, `projects`. The members page, invite dialog and
  their hooks go to `organisations/web`, because the members routes live in `organisations`. The
  invite schemas go to `auth/contracts`, because the invites controller lives in `auth`. The
  not-found and settings pages are not modules: they go to `apps/web/src/pages/`. `apps/web` keeps
  `main.tsx`, `app.tsx` (the route table, which imports every module's pages), `app-shell.tsx`
  and `index.css`. The `apps/web/src/features` folder goes. `apps/api` keeps its tag `type:api`
  and gets `scope:app`; `apps/web` gets `type:app-web` and `scope:app`.
  The workspace globs become `apps/*` and `libs/*/*`. The test-build script's `dist` list and its
  compiled-consumer check follow the new folders.
- **Boundary rules (SERVER pins them, WEB adds the web lines).** In `eslint.config.mjs`,
  `@nx/enforce-module-boundaries` `depConstraints`:
  - `type:util` → `type:util`; `type:ui` → `type:ui`, `type:util`;
    `type:contracts` → `type:contracts`, `type:util`;
    `type:server` → `type:server`, `type:contracts`, `type:util`;
    `type:web` → `type:web`, `type:ui`, `type:contracts`, `type:util`;
    `type:api` → `type:server`, `type:contracts`, `type:util`;
    `type:app-web` → `type:web`, `type:ui`, `type:contracts`, `type:util`.
  - `scope:shared` → `scope:shared`; `scope:core` → `scope:core`, `scope:shared`;
    one line for each module: `scope:<module>` → `scope:<module>`, `scope:core`,
    `scope:shared`, `type:contracts`; `scope:app` → every tag (`*`).
  - With both sets, a module reaches another module only through its contracts, no module web
    library imports another, and no web library imports a server library. A new module adds its
    own `scope:` line. A comment above the module lines says so.
- **Public service through contracts (SERVER).** Two server libraries use another module's
  service today: `auth` uses `OrganisationsService` (`createForAccount`, `invite`, `openInvite`,
  `joinFromInvite`, `membershipFor`) and `organisations` uses `HistoryService.record`. The
  contracts state each used service as an interface and a token: `OrganisationsApi` and
  `ORGANISATIONS_API = 'OrganisationsApi'` in `@app/organisations-contracts`, `HistoryApi` and
  `HISTORY_API = 'HistoryApi'` in `@app/history-contracts`, with plain argument and return types
  (no Prisma types). The service `implements` the interface; its Nest module is `@Global()` and
  provides `{ provide: <TOKEN>, useExisting: <Service> }` and exports the token. The caller
  injects `@Inject(<TOKEN>) private readonly organisations: OrganisationsApi` and drops its
  import of the other module's Nest module. `apps/api` imports every module. This is the only
  code change beyond moves; a later split gives the token an HTTP client.
- **Module schemas (SCHEMAS pins, SCHEMASPY follows).** Schemas `core`, `history` and
  `projects`. `core` holds the auth and organisations modules' tables and enums (Account,
  Session, PasswordResetToken, Organisation, Membership, Invite; Python `account`, `session`,
  `password_reset_token`, `organisation`, `membership`, `invite`). `projects` holds Project and
  its status enum. `history` holds ChangeRecord: the history module owns this table and it grows
  with every admin action of every module, so its own schema keeps `core` small and lets a later
  story move the history to its own store. The migration tables (`_prisma_migrations`,
  `alembic_version`) stay in `public`. The schema name is the module's folder name; a new module
  uses its own name.
- **Links (SCHEMAS).** A column that links to an item of another business module is `uuid` with
  `CREATE INDEX "idx_{table}_{column}_link"` and no foreign key. The module checks the link
  through the other module's contracts service before it writes it. A link to `core`
  (organisation, account) keeps its foreign key. The starters have no link between business
  modules today, so no column changes; the rule goes in the convention pages and the review.
- **Review rule (GUIDE).** In `src/forge/templates/review.md`: "A foreign key from a table in one
  business module's schema to a table in another business module's schema is a P1 finding. A
  link between business modules stores the id with an index, and the module checks it through
  the other module's public service. A foreign key to the `core` schema is not a finding."
- **Growth notes (GUIDE).** The constitution outline in `src/forge/templates/skill.md` gets
  `## Growth notes` after `## Architecture choices`, one line per answered question:
  `- <the question in plain words>: <the answer> (<the note it came from>)`.

### Done-when details

1. SERVER. Move `libs/<module>/src` to `libs/<module>/server/src` and `libs/core/src` to
   `libs/core/server/src` with their `package.json`, `project.json` and `tsconfig.json` (new
   names, tags and `references` paths). Split `libs/shared/src/index.ts`: each module's schemas
   and types into `libs/<module>/contracts/src/index.ts` (projects: `projectStatusSchema`,
   `projectSchema`, `projectListQuerySchema`, `Project*`; auth: sign-up, sign-in, password and
   invite schemas, `Account`; organisations: `memberListQuerySchema`, `changeRoleSchema`,
   `Member*`; history: `HistoryEntry`) and the rest into `libs/shared/util`. `core/server`'s
   `csv.ts` imports the cell guard from `@app/shared-util`. Every `@app/shared`, `@app/core` and
   `@app/<module>` import in `apps/api`, `apps/web` and the libraries changes to the new
   package. The format lint rule's `files` and `ignores` and the API tests' imports follow the
   new paths; its message names `@app/shared-util`.
   `apps/web/package.json` and `apps/web/tsconfig.json` swap `@app/shared` and its reference
   for the new packages.
   The Python half (SERVER keeps the Python starter green): `init._starter_files` for `python`
   also copies the TypeScript `libs/shared/util`; the Python starter gets its own
   `libs/<module>/contracts` (the zod schemas, with types from the OpenAPI file, under the same
   package names and exports as the TypeScript ones); the generated files move to
   `libs/shared/api-types` (`@app/shared-api-types`, with `openapi.json` and `src/api-types.ts`)
   and the `api-types` script writes there; the Python `libs/shared/src` goes (its `format.ts` is
   byte-identical to the TypeScript one); the Python workspace lists `apps/web` and `libs/*/*`,
   and `typecheck` builds the new libraries. No Python API file changes.
   Test `tests/test_libs_layout.py::test_1_server_code_is_split_by_module` (platform, live): the
   tree has each server, contracts and util folder in the table with its tags, and no `libs/shared/src` or
   `libs/<module>/src`; in a copy of the starter, `corepack pnpm run lint` passes clean and fails
   with `@nx/enforce-module-boundaries` for (a) `libs/projects/server/src/reach-in.ts` importing
   `@app/auth-server`, (b) the same file importing `../../../auth/server/src/auth.service`, and
   (c) `libs/projects/contracts/src/reach-in.ts` importing `@app/projects-server`; and the
   live API suite passes. This test replaces `tests/test_modular_starter.py::test_2`; delete that
   file and move its install fixture here.
2. WEB. Move the files as the table says. The shadcn files import `cn` and `useIsMobile`
   relatively inside `shared/ui`. `@app/shared-ui` exports `./components/ui/*`, `./lib/utils`,
   `./hooks/*` and `./components/*`. `apps/web/components.json` moves to `libs/shared/ui` with its
   aliases pointed at those folders, so `npx shadcn@4.21.4 add <name> --cwd libs/shared/ui`
   writes there; frontend.md and brief.md's shadcn sentence name `--cwd libs/shared/ui` for an
   app that has `libs/shared/ui`. `apps/web/src/index.css` stays (review and the worker brief
   name it) and adds `@source "../../../libs";` so Tailwind sees the classes in the libraries.
   The hooks lint block covers `libs/*/web/src/**` and `libs/shared/ui/src/**`, without
   `libs/shared/ui/src/components/ui/**`. `apps/web/vitest.config.ts` includes
   `../../libs/*/*/src/**/*.test.{ts,tsx}`; `format.test.ts` moves to `libs/shared/util/src/`.
   The `@/` alias stays for `apps/web/src` only.
   Test `tests/test_libs_layout.py::test_2_screens_live_in_module_web_libraries` (platform,
   live): no `apps/web/src/features` and no `apps/web/src/components/ui`; lint fails with
   `@nx/enforce-module-boundaries` for (a) `libs/projects/web/src/reach-in.ts` importing
   `@app/organisations-web` and (b) `libs/core/web/src/reach-in.ts` importing
   `@app/core-server`; the live run's browser flows (`BROWSER_FLOWS`) all pass; the built CSS has
   a class that only a module web library uses. `tests/test_starter_tree.py::test_2` reads the
   shell, router and shadcn files from their new folders.
3. SERVER and WEB together (each keeps both starters green). SERVER's Python half is in item 1.
   WEB: `init._starter_files` for `python` also copies `libs/shared/ui`, `libs/core/web` and
   `libs/*/web`. The Python lint has no Nx, so `starter-python/eslint.config.mjs` adds, for `libs/*/web/src/**`,
   `no-restricted-imports` with `patterns: [{ group: ['@app/*-web', '!@app/core-web', '@app/*-server'], message: 'A module web library uses another module only through its contracts.' }, { group: ['../../../*/web/**', '../../../*/server/**'], message: 'A module web library uses another module only through its contracts.' }]`.
   No Python API file changes in this part.
   Test `tests/test_libs_layout.py::test_3_the_python_web_app_uses_the_same_libraries`
   (platform, live): after `forge init --starter python`, the first commit has the copied web
   libraries byte for byte and the Python contracts, and no `apps/api/app` file differs from the
   starter; in the app, lint fails with that message for `libs/projects/web/src/reach-in.ts`
   importing `@app/organisations-web` and for `../../../organisations/web/src/index`; the live
   Python run passes its browser flows. SERVER keeps `tests/test_python_starter.py` passing
   (`REACT_PATHS`, the `api-types` paths), and this test is WEB's.
   `tests/test_python_starter.py` (`REACT_PATHS`, the `api-types` path checks) follows.
4. SCHEMAS. `base.prisma`'s datasource gets `schemas = ["core", "history", "projects"]`; each
   model and enum gets `@@schema("...")` (multiSchema is in Prisma 7 without a preview flag;
   check it on 7.10.1). New migration `apps/api/prisma/migrations/20261026000150_module_schemas/`:
   `CREATE SCHEMA` for each, then `ALTER TABLE ... SET SCHEMA` and `ALTER TYPE ... SET SCHEMA`
   for each table and enum. Foreign keys, indexes and the soft-delete trigger move with their
   table; the `soft_delete_only()` function stays in `public`. Its timestamp sorts after
   FORGE-DATABASE-1's ids migration (`20261026000100`) and before its columns migration
   (`20261026000200`). `prisma migrate diff --from-migrations ... --to-schema ...` prints an empty
   migration. The API tests' raw SQL names tables with their schema (`core."Account"`,
   `projects."Project"`).
   SCHEMASPY. Each model gets `__table_args__` with `{"schema": "<schema>"}` (in the tuple form
   where the model has constraints) and each `ForeignKey` names `core.<table>.id`; each enum gets
   `schema=`. New revision `migrations/versions/0008_module_schemas.py` with the same
   statements. The one Python revision order is: `0005_history`, `0006_extensions`,
   `0007_ids_and_updated_at` (FORGE-DATABASE-1), `0008_module_schemas` (this story, with
   `down_revision = "0007_ids_and_updated_at"`), then FORGE-DATABASE-1's columns revision as `0009_columns` with
   `down_revision = "0008_module_schemas"`. One head, no fork; `env.py` passes `include_schemas=True`.
   Test `tests/test_module_schemas.py::test_4_each_module_keeps_its_tables_in_its_own_schema`
   (platform, live), parametrized `react` and `python`: each starter's API suite has the case
   `each module keeps its tables in its own schema` (it reads `information_schema.tables` and
   checks every app table's schema, and that no foreign key goes between `history` and
   `projects`), and the live run requires it; the Prisma drift check is empty (`react`); Alembic
   autogenerate gives no change (`python`). GUIDE adds the review case to the same test: on a new
   and an adopted repo, the review prompt that `forge close` sends a stub reviewer has the review
   rule's sentence (as `tests/test_react_review_rules.py` does).
5. GUIDE. One paragraph in skill.md's App constitution section, after the defaults paragraph:
   "On a new app, check the client notes for five growth topics: the users and records in year
   one and year three, heavy background work, other systems that call in or that the app calls,
   rules on where the data stays, and parts that can become their own product. Ask about a topic
   only when the notes touch it and do not answer it, one question at a time. Write each answer
   under ## Growth notes in the constitution. A later story reads these notes before it plans
   modules, jobs or links." An adopted app is not asked: the paragraph starts "On a new app".
   Test `tests/test_growth_notes.py::test_5_setup_asks_growth_questions_only_where_the_notes_leave_them_open`,
   parametrized `new init` and `previous release upgrade and sync` (the fixture of
   `tests/test_notes_first_discovery.py`): both hosts' synced guide has the paragraph and the
   outline's `## Growth notes` line. The adopted case checks the same synced text, which keeps
   the review rule's one existing-repo case; the paragraph itself limits the questions to a new
   app.
6. Every part. Convention pages say the new layout once and add: "An app made before this layout
   keeps its own folders and schema; follow the folders it has." Test
   `tests/test_libs_layout.py::test_6_existing_apps_keep_their_layout`, parametrized as test_5:
   an adopted repo with `libs/shared/src/index.ts`, `libs/projects/src/projects.service.ts`,
   `apps/web/src/features/projects/pages/projects-page.tsx` and a Prisma model with no
   `@@schema` has the same bytes after `forge sync`, and the synced `conventions/stack.md` has
   the sentence above; the new-init case has `libs/shared/util` and no `libs/shared/src`.

### Forge files that name these paths

Each part changes the Forge-side text for the paths it moves:

- SERVER: `conventions/stack.md` (folder list), `conventions/backend.md` (folders, packages,
  tags, the contracts service), `conventions/api.md` (schemas in `@app/<module>-contracts`,
  `sendCsv` from `@app/core-server`, the decorator path), `conventions/frontend.md`'s
  `libs/shared` line, `src/forge/standards.md` (the `libs/...` sentence), brief.md's
  `@app/shared`/`@app/core` sentence, skill.md's fixed rules lines (`@app/shared` becomes
  `@app/shared-util`; "Each module owns its tables, in its own schema file" stays until
  SCHEMAS), and the tests that read those sentences: `tests/test_zod_rules.py`,
  `tests/test_zod_starter.py`, `tests/test_built_in_defaults_guide.py`,
  `tests/test_defaults_formats.py`, `tests/test_standards.py`, `tests/test_starter_tree.py`
  (`test_1`'s libs list and tag check), `tests/test_modular_starter.py` (deleted).
- SERVER also: `src/forge/init.py`, `conventions/python.md` (folder list, `api-types` paths),
  `tests/test_python_starter.py`, `tests/test_python_guide.py`.
- WEB: `conventions/frontend.md` (the web folder tree, the `components/ui` path, the shadcn
  command), brief.md's shadcn sentence, `src/forge/init.py` (the web libraries), `tests/test_shadcn_only.py` (that sentence),
  `tests/test_starter_tree.py` (`test_2`), `tests/test_react_starter.py` (the memo walk covers
  `libs/*/web` and `libs/shared/ui`). The shadcn close check matches any `components/ui` folder,
  so `app_baseline.py` does not change. "In an app that has libs/organisations" stays true.
- SCHEMAS and SCHEMASPY: `conventions/database.md` and `conventions/backend.md` (schemas and
  links), skill.md's fixed rule ("Each module keeps its tables in its own Postgres schema; a link
  between business modules stores the id with an index and no foreign key") and the Python fixed
  rule, brief.md (the same sentence in the database lines), `conventions/python.md`.
- GUIDE: `review.md`, skill.md (paragraph and outline line).
- `.github/workflows/starter-smoke.yml`: its `paths` and the TypeScript job's pytest list replace
  `tests/test_modular_starter.py` with `tests/test_libs_layout.py tests/test_module_schemas.py`
  (SERVER adds the first, SCHEMAS the second), with `-k "not python"`; the Python job adds both
  files with `-k python` (WEB, SCHEMASPY).
- Synced copies under `.claude/skills/` and `.codex/skills/` are rewritten by `forge sync`.

### New and existing repos

- New repo (init, TypeScript or Python starter): gets the libraries, the boundary rules, the
  schemas and their migration, the guide paragraph and the review rule. Tests 1 to 5.
- Existing repo (upgrade): no app file, schema or migration changes; it gets the convention
  pages, skill and brief text and the review rule on sync. Tests 4 (review case), 5 and 6.

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
| SERVER | Server code split by module | `shared/util`, `core/server`, each module's `contracts` and `server` libraries, the two contracts services, the type and scope tags and boundary rules, the new import lines everywhere, the Python contracts and `libs/shared/api-types` with `shared/util` copied in, the Forge texts that name these paths | 1, 3, 6 | `src/forge/templates/starter/libs/**`, `starter/apps/api/**`, `starter/apps/web/src/**` (import lines only), `starter/apps/web/package.json`, `starter/apps/web/tsconfig.json`, `starter/eslint.config.mjs`, `starter/pnpm-workspace.yaml`, `starter/pnpm-lock.yaml`, `starter/scripts/test-build.mjs`, `starter/README.md`, `src/forge/init.py`, `src/forge/templates/starter-python/{libs/**,package.json,pnpm-workspace.yaml,pnpm-lock.yaml,README.md}`, `src/forge/templates/conventions/{stack,backend,api,frontend,python}.md`, `src/forge/standards.md`, `src/forge/templates/brief.md`, `src/forge/templates/skill.md`, `.github/workflows/starter-smoke.yml`, synced skill copies | `tests/test_libs_layout.py` (`test_1`, `test_6`, new); `tests/test_modular_starter.py` (deleted); `tests/test_python_starter.py`; `tests/test_python_guide.py`; the tests listed under SERVER above | FORGE-SINGLECO-1/COMPANYAPI, FORGE-SINGLECO-1/COMPANYPY | no | |
| WEB | Screens in module web libraries | `shared/ui`, `core/web`, each module's `web` library, the pages folder, the web boundary lines, shadcn's new home, the Tailwind source line, the web libraries copied into Python apps and the Python web lint rule | 2, 3 | `starter/apps/web/**`, `starter/libs/shared/ui/**`, `starter/libs/core/web/**`, `starter/libs/*/web/**`, `starter/eslint.config.mjs`, `starter/pnpm-lock.yaml`, `starter/README.md`, `src/forge/init.py`, `src/forge/templates/starter-python/{eslint.config.mjs,package.json,pnpm-lock.yaml,README.md}`, `src/forge/templates/conventions/{frontend,python}.md`, `src/forge/templates/brief.md`, `.github/workflows/starter-smoke.yml` | `tests/test_libs_layout.py` (`test_2`, `test_3`); `tests/test_starter_tree.py` (`test_2`); `tests/test_react_starter.py`; `tests/test_shadcn_only.py`; `tests/test_python_starter.py` | SERVER, FORGE-SINGLECO-1/COMPANYWEB | no | |
| SCHEMAS | Module schemas in the TypeScript starter | multiSchema, `@@schema` on each model and enum, the schema migration, schema-qualified raw SQL in the API tests, the schema case, the link rule texts | 4 | `starter/apps/api/prisma/schema/*.prisma`, `starter/apps/api/prisma/migrations/20261026000150_module_schemas/` (new), `starter/apps/api/test/**`, `src/forge/templates/conventions/{database,backend}.md`, `src/forge/templates/skill.md`, `src/forge/templates/brief.md`, `.github/workflows/starter-smoke.yml`, synced skill copies | `tests/test_module_schemas.py` (`test_4`, `react`, new); `tests/test_built_in_defaults_guide.py` (the fixed rule line) | WEB, FORGE-DATABASE-1/IDS | no | |
| SCHEMASPY | Module schemas in the Python starter | `schema=` on each table and enum, `core.` foreign keys, the Alembic revision, the schema case, the Python fixed rule | 4 | `starter-python/apps/api/app/*/models.py`, `starter-python/apps/api/migrations/env.py`, `starter-python/apps/api/migrations/versions/0008_module_schemas.py` (new), `starter-python/apps/api/tests/**`, `src/forge/templates/conventions/python.md`, `src/forge/templates/skill.md`, synced skill copies | `tests/test_module_schemas.py` (`test_4`, `python`); `tests/test_python_guide.py` (the fixed rule line) | SCHEMAS, FORGE-DATABASE-1/IDSPY | no | |
| GUIDE | Growth notes and the foreign-key review rule | The growth paragraph and outline line, the review rule and its case | 4, 5 | `src/forge/templates/skill.md`, `src/forge/templates/review.md`, synced skill copies | `tests/test_growth_notes.py` (`test_5`, new); `tests/test_module_schemas.py` (`test_4` review case) | SCHEMASPY | no | |

The parts run in one chain, SERVER, WEB, SCHEMAS, SCHEMASPY, GUIDE, because each shares files
with the next (`eslint.config.mjs`, the lock files, `init.py`, `brief.md`, `python.md`,
`skill.md`, the workflow and the test files). Each part keeps both starters green on main.
SCHEMAS also waits for FORGE-DATABASE-1's IDS and SCHEMASPY for its IDSPY, so the schema
migration runs after the ids migration in both starters; FORGE-DATABASE-1's COLUMNS and
COLUMNSPY wait for SCHEMAS and SCHEMASPY. FORGE-FEATURE-1's parts wait for WEB (and its
COMMAND, WEB and PY parts for SCHEMAS and SCHEMASPY).

New moving parts: none

## Notes

- Owner decisions (25 Oct 2026, settled): libs/shared splits into shared/util (no business words)
  and shared/ui (web only); core splits into core/server and core/web; each module gets
  contracts, server and web libraries; Nx type and scope tags enforce that a module reaches
  another only through its contracts, module web libraries never import each other, and web
  never imports server; only the layout and rules (no Module Federation, no service clients, no
  broker); the Python API stays as is and its web app keeps OpenAPI types in the shared library
  group; existing apps keep their layout. Each module has its own Postgres schema from day one
  in both starters, with core tables in `core` and migrations that move the existing tables; a
  link between business modules has an index and no foreign key and is checked through the
  other module's public service; links to core keep their foreign key; a cross-schema foreign
  key between business modules is a review finding; five growth questions at setup, asked only
  where the notes touch a topic and do not answer it, written as growth notes; keep it simple.
- Planner choices the owner did not make: (1) the history table gets its own `history` schema,
  not `core` (reason in the pinned words); (2) server libraries reach another module's service
  through an interface and token in its contracts, because the owner's rule allows only contracts
  across modules and two services are used across modules today; (3) the route table, app shell
  and theme file stay in `apps/web`, since the route table imports every module and `core/web`
  may not; "router shell" in `core/web` is the route error page and the query client;
  (4) not-found and settings pages go to `apps/web/src/pages`; (5) the Python OpenAPI types go to
  `libs/shared/api-types`, inside the shared group, so `shared/util` keeps no business words;
  (6) the Python web rule uses ESLint's `no-restricted-imports`, with package and relative
  patterns, since the Python starter has no Nx; (7) `shared/ui` exports subpaths so shadcn's add command writes into it; (8) the starters
  have no id helpers or in-process events today, so `shared/util` and `core/server` get none; a
  story that needs them puts them there; (9) the growth test also runs on an adopted repo, to
  keep the review rule's one existing-repo case, and checks only the synced text.
- Owner decision (26 Oct 2026, settled): the vendor-SDK lint is not in this story; a later story
  adds it as an ast-grep rule.
