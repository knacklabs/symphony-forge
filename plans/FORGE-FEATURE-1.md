# Build a client feature from the starter in one step

6 parts · Risks: none one-way · New moving parts: none

## What changes for you

- When a plan adds a new thing to a client app, such as invoices or customers, the plan names it
  and its fields. The worker's first step runs one Forge command that builds it. You never type
  the command and you make no technical choices.
- The new feature works like the starter's projects feature: a list screen with search and
  filters that stay in the web address, a detail screen, a form, an Export CSV button, and
  access for the admins and members of the same organisation only.
- Its table keeps deleted items, and it records who made, last changed and deleted each item and
  when.
- A field can be text, long text, number, money, date, yes or no, email, a status list, or a link
  to one item of another feature. The agent adds other kinds of field by hand.
- The new feature comes with its own API and screen tests, and they pass at once.
- The projects feature in a new app also gets a detail screen, and its search and status filter
  stay in the web address.
- In an app that did not start from the starter, the command says that it needs a starter app
  and changes nothing.
- Existing apps keep their code. On upgrade they get the command and the guide text. An existing
  app that started from the current starter can use the command at once.

Design: none (the new screens copy the projects screens and their shadcn/ui components; the
projects detail screen uses the same card, label and button components and no new look)

## Why

FDEs must ship client features without technical choices. Today each new feature is built by
hand in the TypeScript or the Python starter. The agent decides the table, the checks, the
screens, the export and the tests again for each feature, and each feature comes out a little
different. The starter's projects feature already has soft delete, records of who changed what,
checked input, CSV export with the formula guard, organisation access and its tests. One command
that copies it, renamed and with the plan's fields, makes each new feature the same and passing
from the first commit. On 25 October 2026 the owner chose this command, the field kinds, and
starter apps only.

## Done when

1. **When a plan names a new feature and its fields, the worker's first step builds it in a TypeScript or a Python starter app with one command.**
2. **The new feature has list, detail and form screens, search and filters that stay in the web address, a CSV export that keeps formulas as text, and access only for the admins and members of its organisation.**
3. **The new feature's table keeps deleted items and records who made, changed and deleted each item, and each column's type and index come from one field-kind table.**
4. **The new feature's API and screen tests pass as soon as the command runs.**
5. **In a new app, projects have a detail screen, and their search and status filter stay in the web address.**
6. **In an app that did not start from the starter, the command refuses, says it needs a starter app, and changes nothing.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none one-way. Each part reverts with its pull request. The command writes files in the
worker's branch only; the worker commits them, and a revert removes them. The new feature's
migration adds a table and changes no existing table.

Trade-off: the command copies the projects feature from the starter that ships with the
installed Forge, not from the app's own projects code. An app can rename or remove its projects
feature, and the copy still works. An app made from an older starter, which has no organisations
or change history, gets the refusal.

Trade-off: the column types and indexes are starting values. A later story sets the database
rules and the exact values in the same one table.

Trade-off: no cache server. The list screens read the database through the table's indexes.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new test file starts with `STORY = "FORGE-FEATURE-1"`. Each test runs the forge command or,
for the generated app's own behaviour, runs that app's own `node scripts/test.mjs`, and never
imports forge. One test per Done-when item, named `test_<n>_...`; a part that adds the Python
side adds a parameter to the same test, not a new test. Live tests carry `@pytest.mark.platform`
and `@pytest.mark.timeout(1800)` and use `_run_live_starter` and `_require_cases` from
`tests/test_starter_tree.py`, as `tests/test_python_starter.py` does. `starter-smoke.yml` runs
`tests/test_feature_*.py` in both jobs (the TypeScript job takes the `typescript` parameters, the
Python job the `python` ones, by `-k`), and its `paths` add `src/forge/feature.py`,
`src/forge/templates/feature/**` and the same test glob.

The existing-repo case for a rule uses an **adopted starter app**: the
`tests/fixtures/adopted-v1.2.2/client` repo set up as `adopt_earlier` in
`tests/test_close_always_tests.py` does, with the current starter's files (TypeScript, or Python
with the TypeScript `apps/web`, as `init._starter_files` lists them) copied in and committed
before the upgrade's sync. This is an app that started from the starter and moved to this
release.

### Where the command lives

The command is `forge task feature`, under the existing `task` group. `forge --help` lists 25
commands today, and `tests/test_rules.py::test_5_forge_stays_small` caps them at 25, so a new
top-level command would break principle 6. A group's subcommand does not count against the cap.
`task` fits: the worker runs it as the first step of its task. Add
`"task feature": "feature"` to `ROUTES` in `src/forge/cli.py`; the command's `COMMANDS` entry,
arguments and handler live in the new module `src/forge/feature.py` (under 1,200 lines).
`changes_state` is `False`: the command writes app files and no Forge record. It commits nothing;
the worker commits the files with the rest of its task.

### Words this story pins

The part named first owns each name; later parts use it and list that part under After.

- **The command line (COMMAND).**
  `forge task feature <plural> --one <singular> --field <name>:<kind> [--field ...]`.
  `<plural>` and `<singular>` are lower-case words joined by hyphens (`invoices`, `work-orders`;
  `--one invoice`, `--one work-order`). Forge makes every other form from them: `Invoice`,
  `Invoices`, `invoice`, `invoices`, `INVOICE` (TypeScript), `invoice`/`invoices` (Python
  packages and tables, `work_order`), `/invoices` (route and API path). `<name>` is camelCase
  (`dueDate`), with `?` at its end for an optional field (`dueDate?`). `<kind>` is one of
  `text`, `long-text`, `number`, `money`, `date`, `yes-no`, `email`, `status(<a>|<b>|...)`
  (the first option is the default) and `link(<plural of another feature>)` (the column is
  `<name>Id`). Screen labels come from the field names (`dueDate` gives `Due date`); the worker
  renames labels by hand when the plan asks for other words.
  Refusals, each with its next action, all checked before the command writes anything:
  not a starter app (item 6); a feature folder of that name already there; a field name that is
  not camelCase or is one of `id`, `organisationId`, `createdAtUtc`, `updatedAtUtc`,
  `createdByAccountId`, `modifiedByAccountId`, `deletedAtUtc`, `deletedByAccountId`; an unknown
  kind; a link to a feature that the app does not have.
  On success it prints the files it wrote, one per line, then
  `Next: run the app's tests, then commit these files with your task.` A Python app also gets
  `corepack pnpm run api-types` in that line, before the tests.
- **The field-kind table (COMMAND).** `src/forge/templates/feature/kinds.toml`, one
  `[<kind>]` table per kind. It is the only place that holds a type, a check, an index or a
  per-kind snippet; `feature.py` reads every per-kind value from it and holds no column type,
  constraint, index or kind name list of its own (review checks this). Keys:
  `prisma` (the Prisma field type and attributes), `sql` (the Postgres column type in the
  migration), `sqlalchemy` (the mapped column type), `check` (a SQL `CHECK` on the column, or
  `""`), `filter_index` (the index when the field is a list filter, or `""`), `search_index`
  (the index when the field is the list search, or `""`), `filter` (`true` when the field
  becomes a list filter), `search` (`true` when the field can be the list search), `zod` and
  `pydantic` (the input rule), `input` (the form control), `cell` (how the list and detail show
  it, with the `@app/shared` format helpers), `csv` (the export cell), and `sample` and `bad`
  (a valid and an invalid value for the generated tests). For `status` and `link`, `{options}`,
  `{enum}` and `{target}` stand for the field's options, enum name and linked table.
  The database values (`prisma`, `sql`, `sqlalchemy`, `check`, `filter_index`, `search_index`)
  are **placeholders for the database rules story**: each line carries the comment
  `# placeholder: the database rules story sets this value`. The starting values work today:

  | Kind | Column | Check | Index when a filter or the search |
  |---|---|---|---|
  | text | `VARCHAR(200)` | none | search: none |
  | long-text | `TEXT` | none | none |
  | number | `DOUBLE PRECISION` | none | none |
  | money | `INTEGER` (cents) | none | none |
  | date | `DATE` | none | none |
  | yes-no | `BOOLEAN NOT NULL DEFAULT false` | none | filter: btree on (organisation, field) |
  | email | `VARCHAR(254)` | none | search: none |
  | status | its own Postgres enum, default the first option | none | filter: btree on (organisation, field) |
  | link | `UUID` with a foreign key to the linked table, `ON DELETE RESTRICT` | none | filter: btree on (organisation, field) |

  `filter` is `true` for `yes-no`, `status` and `link`; `search` is `true` for `text` and
  `email`. Money is whole cents, as `formatMoney` takes them.
- **Indexes (COMMAND).** The list screen's default sort is newest first, as projects. Each new
  table gets one index on `(organisationId, createdAtUtc)` for that sort, the indexes that
  projects has on its account columns, the kind's `filter_index` for each filter field, and the
  kind's `search_index` for the search field. The search field is the first field whose kind has
  `search = true`; a feature with none has no search box. No other index.
- **Marks in the starter's projects files (COMMAND for the API files, WEB for the web files, PY
  for the Python files).** Each place in a projects file that lists the projects fields sits
  between a line `// forge:fields` and a line `// forge:end-fields` (`# forge:fields` in Python,
  `{/* forge:fields */}` in JSX). The command copies each projects file, renames every
  Project/project form to the feature's forms, and puts one rendered snippet per field between
  each pair of marks, from the kind table. The marks stay in new apps' projects files and in the
  copies, so a later agent sees where a field goes. Every other line is a plain renamed copy.
- **The copy source.** The starter tree of the installed Forge (`sync.TEMPLATES / "starter"`;
  for Python `"starter-python"` plus the TypeScript `apps/web`), not the app's own projects
  module. This is the simpler one: Forge's own tests run this tree, so its marks and shape are
  known, and it still works after an app renames or removes its projects feature, as the
  prototype guide tells the agent to do. The app's own copy can be changed, renamed or gone.
- **The starter check (COMMAND pins it; PY adds the Python list).** The app is a TypeScript
  starter app when every one of these is there: `apps/api/prisma/schema/organisations.prisma`,
  `apps/api/prisma/schema/history.prisma`, `apps/api/src/app.module.ts` with its
  `HistoryModule` line, `libs/core/src/common/csv.ts`, `apps/web/src/app.tsx` with its
  `/history` route and `apps/web/src/components/app-shell.tsx` with its Members item. It is a
  Python starter app when `apps/api/app/main.py` (with its history router line),
  `apps/api/app/organisations/`, `apps/api/app/history/`, `apps/api/app/core/csv.py`,
  `apps/api/migrations/versions/` and the same two web files are there. Wiring lines go next to
  these lines, never next to a projects line. The first missing one gives the refusal
  `forge task feature needs a starter app (one made with forge init --starter), and this app has no <path>.`
  with `Next: build this feature by hand in this app.` Nothing is written. No other guard.
- **Generated test names.** The copies of the projects test files keep the projects case names
  with the feature's words: `creates, lists, reads, updates, and deletes an invoice through the API`,
  `invoices export as CSV`, `another organisation gets 404 for an invoice`,
  `rejects an invalid invoice with field errors`, and the flows
  `create, view, edit, and delete an invoice` and `a reloaded invoices list link keeps its search and filters`.
  The Python HTTP cases use the same names in the snake form that FORGE-DEFAULTS-1 pins.

### Done-when details

1. One step from the plan (COMMAND for TypeScript, PY for Python, GUIDE for the rules).
   - TypeScript output: `libs/<plural>/**` (module, controller, service, DTO, index,
     `package.json`, `project.json`, `tsconfig.json`), `apps/api/prisma/schema/<plural>.prisma`,
     one migration folder `apps/api/prisma/migrations/<UTC yyyyMMddHHmmss>_<plural>/migration.sql`,
     the shared schema and types appended to `libs/shared/src/index.ts`, and the wiring: the
     module in `app.module.ts`, `apps/api/package.json` and the references of
     `apps/api/tsconfig.json`, its importer in `pnpm-lock.yaml` (copied from the projects
     importer, so `pnpm install --frozen-lockfile` passes with no network), its `dist` in
     `scripts/test-build.mjs`, and the back-relation lines in `model Account`, `model
     Organisation` and, for a link, the linked model. The migration holds the `CREATE TYPE` for
     each status field, the table, its foreign keys, the indexes above and the soft delete
     trigger line `CREATE TRIGGER soft_delete_only BEFORE DELETE ON "<Model>" FOR EACH ROW
     EXECUTE FUNCTION soft_delete_only();`. A link field adds `@app/<target>` to the new
     module's `package.json` and `tsconfig.json`, and the service checks the linked item with
     the target module's public service (`get(account, id)`), so no query reads another module's
     table.
   - Python output (PY): `apps/api/app/<plural>/` (`__init__.py`, `models.py`, `schema.py`,
     `service.py`, `routes.py`), one Alembic revision in `apps/api/migrations/versions/` named
     `<next number>_<plural>.py` whose `down_revision` is the current head (the one revision no
     other names as its down revision), the router in `main.py`, the model import in
     `migrations/env.py`, the `<plural> internals` contract in `apps/api/pyproject.toml`, and
     the zod schema copy and the `components['schemas']` types in the Python
     `libs/shared/src/index.ts`. The web files are the same as in a TypeScript app (WEB).
   - Test `tests/test_feature_command.py::test_1_a_plan_line_builds_the_feature_in_one_step`,
     parameters `typescript` and `python`: in a new repo made with `forge init --starter` (or
     `--starter python`), `forge task feature customers --one customer --field name:text` then
     `forge task feature invoices --one invoice --field title:text --field notes?:long-text
     --field quantity:number --field total:money --field dueDate:date --field paid:yes-no
     --field contact?:email --field state:status(draft|sent|void) --field customer:link(customers)`
     each exit 0 and print the files they wrote; every printed file exists; the wiring files
     have the new lines next to the history lines; a second run of the same line refuses with
     the folder message and changes nothing (`git status --porcelain` is the same before and
     after). Adopted case: the same two lines in the adopted starter app write the same files
     with the same text, apart from the migration's timestamp or revision number.
   - GUIDE adds to the same test: the forge skill after `forge init` (new repo) and after
     upgrade and sync (the adopted-v1.2.2 client) holds the planner line, and the worker brief
     that `forge work` writes holds the first-step line.
2. Works like projects (WEB for the screens; COMMAND and PY serve the API).
   - API: list with `page`, `limit`, `sortBy`, `sortOrder`, `search` (case-insensitive
     contains on the search field) and one query key per filter field, all in the shared zod
     list schema (Pydantic in Python), with the same `.strict()` refusal of unknown keys; detail;
     create; replace; soft delete; `GET /api/v1/<plural>/export` through `sendCsv` (Python:
     the `app.core` CSV helper), declared before `:id`. Every query is scoped to
     `account.organisationId`. Admins and members both use every route, as projects; another
     organisation gets `404 <SINGULAR>_NOT_FOUND`.
   - Web: `apps/web/src/features/<plural>/**` with the list page (search box, a select per
     filter field, sort and page, all read from and written to the URL as the projects page
     does), the detail page at `/<plural>/:id`, the form dialog, the hooks and their unit test;
     the route in `app.tsx`, a sidebar item and a Ctrl+K item in `app-shell.tsx`, and its title
     in the page title map. A link field's select and cell read the linked feature's list hook
     in the web app; the API returns only the id.
   - Test `tests/test_feature_command.py::test_2_the_new_feature_works_like_projects`,
     parameters `typescript` and `python`, live: after the item 1 lines in a new starter app,
     the app's own run passes and its reports hold the generated API cases (create to delete,
     another organisation's 404, export with the formula guard: a `title` of `=1+1` comes back
     as `'=1+1`, invalid input refused) and both generated flows. Adopted case: not live; the
     adopted starter app's generated files equal the new repo's (item 1's adopted case), so the
     live proof covers it.
3. Table, audit columns and the kind table (COMMAND; PY for Python).
   - The table has `organisationId` and the audit columns `createdByAccountId`,
     `modifiedByAccountId`, `deletedAtUtc` and `deletedByAccountId`, as projects; create, update
     and delete set them; delete sets `deletedAtUtc`, and the trigger refuses a hard delete.
   - Test `tests/test_feature_command.py::test_3_columns_and_indexes_come_from_the_kind_table`,
     parameters `typescript` and `python`, not live: the test reads the shipped `kinds.toml` and
     checks that the generated migration (and in Python the Alembic revision and `models.py`)
     has each field's `sql` or `sqlalchemy` value, its `check`, one
     `(organisationId, createdAtUtc)` index, the filter fields' `filter_index`, the search
     field's `search_index`, the audit columns and the trigger line. Adopted case: the same
     check in the adopted starter app.
4. Tests pass at once (WEB for TypeScript, PY for Python).
   - The generated test files are renamed copies of the projects test files that SOURCE and
     SOURCEPY add: `apps/api/test/<plural>.e2e-spec.ts`, `apps/web/e2e/<plural>.spec.ts`,
     `apps/web/src/features/<plural>/hooks/<plural>-hooks.test.tsx`, and in Python
     `apps/api/tests/test_<plural>.py`. Their input values come from the kind table's `sample`
     and `bad`.
   - Test `tests/test_feature_command.py::test_4_the_new_feature_tests_pass_at_once`,
     parameters `typescript` and `python`, live: one cached run per starter (shared with
     test_2, as `live_run` does) of the app's `node scripts/test.mjs` after the item 1 lines
     exits 0, and the reports hold every generated case name above. The Python app's own test
     script runs `api-types` first. Adopted case: as item 2.
5. Projects source (SOURCE for TypeScript and web, SOURCEPY for Python).
   - `projectListQuerySchema` gets `search` (optional, trimmed, at most 200) and `status`
     (optional `projectStatusSchema`); the service filters on them; the projects page gets a
     search box and a status select, read from and written to the URL with page and sort; a new
     `ProjectDetailPage` at `/projects/:id` shows the fields and the who and when lines with the
     format helpers, with Edit and Delete; the list's name links to it.
   - The projects cases move to their own files, with no name change: the API cases in
     `apps/api/test/projects.e2e-spec.ts` and the flows in `apps/web/e2e/projects.spec.ts`
     (Python: `apps/api/tests/test_projects.py`). New cases: `filters projects by search and
     status` (API), and the flows `a project's detail screen shows who changed it` and
     `a reloaded projects list link keeps its search and filters` (the second replaces
     `a reloaded or shared list link shows the same view`; update that name in
     `BROWSER_FLOWS` in `tests/test_starter_tree.py`).
   - Test `tests/test_feature_projects.py::test_5_projects_have_a_detail_screen_and_url_filters`,
     live, parameters `typescript` and `python`: the starter's run holds the new cases.
     Adopted case: after upgrade and sync, the adopted starter app's projects files are
     unchanged (sync writes no app file).
6. Refusal (COMMAND; PY adds the Python check list).
   - Test `tests/test_feature_command.py::test_6_outside_a_starter_app_the_command_refuses`:
     in a new repo made with plain `forge init`, `forge task feature invoices --one invoice
     --field title:text` exits non-zero with the needs-a-starter-app line and
     `Next: build this feature by hand in this app.`, and `git status --porcelain` is empty.
     Adopted case: the adopted-v1.2.2 client (no starter files) after upgrade gets the same
     refusal; and the adopted starter app with `libs/history` and `history.prisma` removed (the
     shape of an app made from the v1.2.21 starter) refuses and names
     `apps/api/prisma/schema/history.prisma`.

### Skill, brief and guide (GUIDE)

- `src/forge/templates/skill.md`, Planning a story: when a story adds a new thing that a client
  app keeps track of and the app is a starter app, the planner writes, in the first part's
  Done-when details, one `forge task feature` line per new thing, with every field from the
  brief's `## Things it keeps track of`, in the kinds the command takes; many-to-many links,
  files and computed fields go in the part as hand work. A link's target comes first, in the
  same line order. The part's Scope lists the folders the command writes.
- `src/forge/templates/brief.md`, Build simple: when your part's details give a
  `forge task feature` line, run it first, run the app's tests, and commit its files before any
  other change; then rename labels and add the hand work. Do not hand-build a feature the
  command can build.
- `docs/guide.md`: one paragraph with the command line, the field kinds, the starter-app rule,
  the kind table's place, and that the agent runs it from the plan.
- New repos get these texts at init; existing repos get them on upgrade with sync.

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
| SOURCE | Projects detail screen and URL filters | The projects search and status filter in the shared list schema and the TypeScript API, the search box and status select in the URL, the projects detail screen, and the projects cases moved to their own test files with the new cases. | 5 | `starter/libs/shared/src/index.ts`, `starter/libs/projects/src/projects.service.ts`, `starter/apps/web/src/features/projects/**`, `starter/apps/web/src/app.tsx`, `starter/apps/api/test/api.e2e-spec.ts` (projects cases out), `starter/apps/api/test/projects.e2e-spec.ts` (new), `starter/apps/web/e2e/starter-shell.spec.ts` (projects flows out), `starter/apps/web/e2e/projects.spec.ts` (new), `tests/test_starter_tree.py` (`BROWSER_FLOWS` name only), `.github/workflows/starter-smoke.yml` | `tests/test_feature_projects.py` (`test_5`, `typescript`, new) | | yes | |
| SOURCEPY | Projects filters in the Python API | The same list query in the Python API and the Python shared copy, and the projects HTTP cases moved to their own test file with the new case. | 5 | `starter-python/apps/api/app/projects/**`, `starter-python/apps/api/tests/test_api.py` (projects cases out), `starter-python/apps/api/tests/test_projects.py` (new), `starter-python/libs/shared/src/index.ts`, `starter-python/libs/shared/openapi.json` and `starter-python/libs/shared/src/api-types.ts` (regenerated) | `tests/test_feature_projects.py` (`test_5`, `python`) | SOURCE | no | |
| COMMAND | The feature command and the TypeScript API copy | `forge task feature` with its line, refusals and starter check, the field-kind table, the marks in the TypeScript API projects files, and the TypeScript API, Prisma, migration, shared schema and wiring copy. | 1, 3, 6 | `src/forge/cli.py` (one route), `src/forge/feature.py` (new), `src/forge/templates/feature/kinds.toml` (new), `starter/libs/projects/src/**` and `starter/apps/api/prisma/schema/projects.prisma` (marks only), `starter/libs/shared/src/index.ts` (marks only), `starter/apps/api/test/projects.e2e-spec.ts` (marks only), `.github/workflows/starter-smoke.yml` | `tests/test_feature_command.py` (`test_1`, `test_3`, `test_6`, `typescript`, new) | SOURCE | no | |
| WEB | The feature's screens | The marks in the web projects files and the web copy: list with search and filters in the URL, detail, form, hooks and their test, the route, sidebar and Ctrl+K items, and the live TypeScript run with the generated cases. | 2, 4 | `src/forge/feature.py` (the web copy only), `starter/apps/web/src/features/projects/**` and `starter/apps/web/e2e/projects.spec.ts` (marks only) | `tests/test_feature_command.py` (`test_2`, `test_4`, `typescript`) | COMMAND | yes | |
| PY | The Python API copy | The marks in the Python projects files, the Python starter check, and the Python API, Alembic revision, shared copy and wiring; the Python parameters of the feature tests. | 1, 3, 4 | `src/forge/feature.py` (the Python copy only), `src/forge/templates/feature/kinds.toml` (Python keys only), `starter-python/apps/api/app/projects/**` and `starter-python/apps/api/tests/test_projects.py` (marks only), `starter-python/libs/shared/src/index.ts` (marks only) | `tests/test_feature_command.py` (`test_1`, `test_2`, `test_3`, `test_4`, `test_6`, `python`) | WEB, SOURCEPY | no | |
| GUIDE | Planner and worker rules | The planner rule in the skill, the first-step rule in the worker brief, and the guide paragraph, on new and existing repos. | 1 | `src/forge/templates/skill.md`, `src/forge/templates/brief.md`, `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `docs/guide.md` | `tests/test_feature_command.py` (`test_1`: the skill and brief checks on a new and an adopted repo) | COMMAND | no | |

New moving parts: none

## Notes

- **Order.** SOURCE first, then SOURCEPY and COMMAND side by side (SOURCEPY needs SOURCE's shared
  list schema names; COMMAND copies SOURCE's projects files). WEB and GUIDE after COMMAND: WEB
  extends `feature.py`, and GUIDE adds its checks to COMMAND's test_1. PY last, after WEB (the
  Python live run runs the web flows) and SOURCEPY. All parts ship in one release.
- **Part sizes.** COMMAND is the largest: `feature.py`'s parse, checks, rename and TypeScript
  API copy, and `kinds.toml`. If it goes over 400 lines, move the shared-schema copy into WEB
  (it already edits `feature.py`) before asking for `forge fix allow-large`.
- **What a new and an existing client repo get.** New repos (`forge init --starter` and
  `--starter python`): the projects detail screen and URL filters, the marks in the projects
  files, the projects test files, and the command, which works at once. Plain `forge init`: the
  command, which refuses. Existing repos, on upgrade and sync: the command and the skill, brief
  and guide texts; no app file changes. An existing app that started from the current starter
  can use the command at once; an app made from an older starter or another stack gets the
  refusal.
- **Owner decisions (25 Oct 2026, settled).** The agent runs the command from the plan and the
  FDE never types it; it copies the starter's projects feature, renamed, with the plan's fields,
  in both starters; the nine field kinds and no many-to-many, file or computed fields; starter
  apps only, with a refusal that changes nothing; no extra guards for unlikely races or
  security edge cases; the command chooses column types from the field kind and indexes from
  the list's filters, default sort and search, from one shipped field-kind table; no cache
  server.
- **Planner choices the owner did not make.** (1) The command sits under `forge task`, because
  the command cap is full. (2) The copy is from the installed Forge's starter tree, with marks
  for the field places in the projects files, not from the app's own projects code. (3) "Change
  history" for a feature means the audit columns projects has (who made, last changed and
  deleted each item, and when); the copy writes no row to the Change history screen, as projects
  writes none. (4) Admins and members have the same access to a feature, as to projects. (5)
  Projects have no detail screen and no URL filters today, so SOURCE adds them to projects first,
  and the copy takes them from there. (6) Filters come from the yes-no, status and link fields;
  the search is the first text or email field; the line gives both the plural and the singular.
  (7) A field can be optional with `?`.
- **Open item for the database rules story.** The `prisma`, `sql`, `sqlalchemy`, `check`,
  `filter_index` and `search_index` values in `kinds.toml` are placeholders with working
  starting values. That story sets the exact values and adds its review rule; this story's
  test_3 still passes then, because it reads the values from the table.
- **No cache.** No cache server and no cache layer in the generated code; list queries use the
  indexes above.
- No client repo is named anywhere in this story's code, tests, texts or commits.
