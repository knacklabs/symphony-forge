# Build a client feature from the starter in one step

7 parts · Risks: none one-way · New moving parts: none

## What changes for you

- When a plan adds a new thing to a client app, such as invoices or customers, the plan names it
  and its fields. The worker's first step runs one Forge command that builds it. You never type
  the command and you make no technical choices.
- The new feature works like the starter's projects feature. Its list has a search box, filters,
  sorting by column, and Previous and Next buttons with an approximate total, such as "About
  1,200 projects". The search, filters, sort and page stay in the web address. Each row opens a
  detail screen. The New button opens a form, and Export CSV downloads the list. Only people of
  the same organisation see its items.
- The detail screen shows every field, who made and last changed the item, and its last five
  changes. Edit and Delete are on the detail screen, not on the list.
- Each feature has five permissions: view, create, edit, delete and restore. Admins have all
  five. Members can view, create and edit, but not delete or restore.
- An admin can show the deleted items on the list and restore one from its detail screen. The
  restore adds a Change history row. Members never see deleted items. The app checks the permission on every
  screen and every API call. A plan can change which role has which permission for a feature,
  in one place in that feature's code.
- Its table keeps deleted items. Each create, change and delete adds a row to the Change history
  screen with who, when and what changed.
- A field can be text, long text, number, money, date, yes or no, email, a status list, or a link
  to one item of another feature. The agent adds other kinds of field by hand.
- The new feature comes with its own API and screen tests, and they pass at once.
- The projects feature in a new app gets these first: the paging, search and status filter in
  the web address, the detail screen with its recent changes, the five permissions, restore for
  admins, and a Change history row for each create, change, delete and restore.
- In an app that did not start from the starter, the command says that it needs a starter app
  and changes nothing.
- Existing apps keep their code. On upgrade they get the command and the guide text. An existing
  app that started from the current starter can use the command at once. An app made from an
  older starter, without organisations or change history, gets a refusal that names what is
  missing.
Design: docs/design/FORGE-FEATURE-1/ (972948e687aa96ad4ad5bab953cd9bc6cece276a)

## Why

FDEs must ship client features without technical choices. Today each new feature is built by
hand in the TypeScript or the Python starter. The agent decides the table, the checks, the
access, the screens, the export and the tests again for each feature, and each feature comes out
a little different. The starter's projects feature already has soft delete, checked input, CSV
export with the formula guard, organisation access and its tests. One command that copies it,
renamed and with the plan's fields, makes each new feature the same and passing from the first
commit. On 25 October 2026 the owner chose this command, the field kinds, starter apps only,
five permissions for each feature, restore for admins, a Change history row for each change,
and keyset paging.

## Done when

1. **When a plan names a new feature and its fields, the worker's first step builds it in a TypeScript or a Python starter app with one command.**
2. **The new feature has a list with search, filters, column sort and Previous and Next paging kept in the web address, a detail screen with its recent changes, a form, and a CSV export that keeps formulas as text, for its own organisation only.**
3. **Each feature checks a view, create, edit, delete and restore permission on every screen and API call; admins have all five and can show and restore deleted items, members have all but delete and restore and never see deleted items, and one place in the feature's code changes this.**
4. **The new feature's table keeps deleted items, each create, change and delete adds a Change history row, each column's type and index come from one field-kind table, and its tests pass as soon as the command runs.**
5. **In a new app, projects have the same list, detail screen, permissions and Change history rows.**
6. **In an app that did not start from the starter, the command refuses, says what is missing, and changes nothing.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none one-way. Each part reverts with its pull request. The command writes files in the
worker's branch only; the worker commits them, and a revert removes them. The new feature's
migration adds a table and changes no existing table. The starter's new history migration adds
two empty columns to the change history table.

Trade-off: the command copies the projects feature from the starter that ships with the
installed Forge, not from the app's own projects code. An app can rename or remove its projects
feature, and the copy still works. An app made from an older starter, which has no organisations
or change history, gets the refusal. The owner accepted this on 25 October 2026.

Trade-off: members can no longer delete projects in a new app. Only admins can delete and
restore.

Trade-off: the list's total is exact up to 10,000 items. Above that the list says "More than
10,000".

Trade-off: the database rules story sets the column types and indexes in the same one table.
Until it lands, the money kind keeps today's money format in whole cents.

Trade-off: no cache server. The list screens read the database through the table's indexes.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new test file starts with `STORY = "FORGE-FEATURE-1"`. Each test runs the forge command or,
for the app's own behaviour, runs that app's own `node scripts/test.mjs`, and never imports
forge. One test per Done-when item, named `test_<n>_...`; a part that adds a side (Python, or
the generated feature) adds a parameter to the same test, not a new test. Live tests carry
`@pytest.mark.platform` and `@pytest.mark.timeout(1800)` and use `_run_live_starter` and
`_require_cases` from `tests/test_starter_tree.py`, as `tests/test_python_starter.py` does.
`starter-smoke.yml` runs `tests/test_feature_*.py` in both jobs (the TypeScript job takes the
`typescript` parameters, the Python job the `python` ones, by `-k`), and its `paths` add
`src/forge/feature.py`, `src/forge/templates/feature/**` and the same test glob.

The existing-repo case for a rule uses an **adopted starter app**: the
`tests/fixtures/adopted-v1.2.2/client` repo set up as `adopt_earlier` in
`tests/test_close_always_tests.py` does, with the current starter's files (TypeScript, or Python
with the TypeScript `apps/web`, as `init._starter_files` lists them) copied in and committed
before the upgrade's sync. This is an app that started from the starter and moved to this
release.

**Design.** `docs/design/FORGE-FEATURE-1/SCREENS.md` is the source for every screen text, state,
component and layout: the Projects list, Project detail, Delete project and Project form. PAGING,
DETAIL and ACCESS build them for projects; WEB makes the command copy them, and fills the parts
that SCREENS.md marks **Filled:** from the feature's fields. The example in SCREENS.md (Name,
Description, Hours budget, Budget, Due date, Billable, Contact email, Status, Client) is the
generated output for the item 1 line; the starter's own projects keep their two fields, name and
status, and show the screens with those two.

**Both starters in step.** `forge init --starter python` copies the TypeScript `apps/web`, and
the Python live run runs every flow in it. So each part that changes the web app's HTTP contract
(PAGING, DETAIL, ACCESS) changes the TypeScript API, the Python API and the web app in the same
part, and main never has a web app that one API cannot serve. COMMAND, WEB and PY change only
`feature.py`, `kinds.toml`, marks and new UI components, which no live run of the starters uses.

**Layout (FORGE-LIBS-1).** Every part builds on the library layout that FORGE-LIBS-1 pins; where
a path here differs from the merged tree, follow the merged tree. The projects module is
`libs/projects/contracts` (`@app/projects-contracts`: zod schemas, types and the public service
interface), `libs/projects/server` (`@app/projects-server`) and `libs/projects/web`
(`@app/projects-web`: pages and hooks under `libs/projects/web/src`). Shared code is
`libs/shared/util` (`@app/shared-util`, the format helpers and the CSV cell guard) and
`libs/shared/ui` (`@app/shared-ui`, the shadcn components in
`libs/shared/ui/src/components/ui/`, added with `npx shadcn@4.21.4 add <name> --cwd libs/shared/ui`).
Core is `libs/core/server` (`@app/core-server`) and `libs/core/web` (`@app/core-web`).
`apps/web` keeps `app.tsx`, `app-shell.tsx` and `main.tsx`. Each module's tables sit in its own
Postgres schema (`projects`, `history`; core tables in `core`). A module uses another module only
through that module's contracts: an interface and a token, injected with `@Inject(<TOKEN>)`. The
Python API keeps `apps/api/app/<module>/`; the Python web app has the same web libraries and its
own `libs/<module>/contracts`, with types from `@app/shared-api-types`
(`libs/shared/api-types`). Paths below use this layout.

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

- **Keyset paging (PAGING).** The list query has `sortBy` (a list column, default
  `updatedAtUtc`), `sortOrder` (default `desc`), `after` or `before` (an opaque cursor; at most
  one of the two), `search` and one key per filter field; no `page` and no `limit`. The page size
  is 20. The order is (sort column, `id`) in `sortOrder`, with empty values last. The cursor is
  the base64url of the JSON `[<sort value>, <id>, <sortBy>, <sortOrder>]`; a cursor that does not
  decode, or whose sort does not match the query, gets the usual `400` field error on `after` or
  `before`. `before` reads backwards and returns the rows in list order. The response is
  `{ items, page: { nextCursor: string | null, previousCursor: string | null, total: number, totalIsCapped: boolean } }`.
  `total` counts the matching rows up to 10,000 (a count over a `LIMIT 10001` subquery);
  `totalIsCapped` is true above that. Projects lose `page`, `limit` and `pagination`.
  Web: the URL holds `after=<cursor>` (or `before=<cursor>` after Previous) with the search,
  filters and sort; a change to the search, a filter or the sort drops the cursor. Under the
  table: `<total> projects` (`1 project`) below 100, `About <total rounded to two significant
  figures> projects` from 100, `More than 10,000 projects` when capped; Previous is off when
  `previousCursor` is null, Next when `nextCursor` is null.
- **Filters and columns from field kinds (PAGING pins them for projects; WEB copies the rule).**
  Each `yes-no`, `status` and `link` field gets one list filter, a Select: yes-no
  `<Label> or not | <Label> | Not <label>` with URL values `yes` and `no`; status
  `All <label in plural> | <each option>`; link `All <target plural> | <each linked item by name>`
  with the item id in the URL. The first `text` field (the name, which every feature has) is the
  search, with the placeholder `Search by <label>`. No other kind gets a filter. A link filter
  and the form's link Combobox are a searchable Select that asks the linked feature's list API
  page by page (its `search` and `after`), so a target with many items works; a list cell and
  the detail row show the linked item's name from the linked feature's detail API (a
  `ponytail:` comment names the ceiling: up to 20 cached detail reads per page; a name lookup
  route is the upgrade). The feature's web library calls those APIs with `@app/core-web`'s API
  client and the target's `@app/<target>-contracts` types, never the target's web library,
  which the boundary rules refuse. List columns: the first text field (a link to the detail screen), each `status`,
  `link`, `date` and `money` field, then Updated. Every column header sorts. This comes from the
  `filter`, `search` and `column` keys of the kind table, not from code.
- **The detail screen and recent changes (DETAIL).** `/<plural>/:id`, as SCREENS.md shows it.
  The change history table gets `subjectId uuid NULL` and `subjectName text NULL`, and the index
  `(organisationId, subjectId, createdAtUtc DESC)`, in one new migration in each starter (the
  TypeScript migration folder and the next Alembic revision on main, chained to the head at
  build time; the table is in the `history` schema). The history contracts interface
  `HistoryApi` (token `HISTORY_API`, in `@app/history-contracts`) gets
  `record(principal, action: string, summary: string, subject?: { id: string; name: string }, tx?: unknown)`
  and `listForSubject(principal, subjectId, limit)`; the transaction is typed `unknown` in the
  contract, so the contract names no Prisma type, and `HistoryService` uses it as its Prisma
  transaction client (Python `record(account, action: str, summary: str, subject: Subject | None = None)`
  on the caller's session). Projects and every copied feature inject `HISTORY_API`. Route `GET /api/v1/<plural>/:id/changes`
  returns the newest 5 as `{ id, actorEmail, summary, createdAtUtc }[]`. The Change history
  screen and its CSV show `<subjectName>: <summary>` when `subjectName` is set.
- **Change history rows (DETAIL; ACCESS adds restore).** Each create, change, delete and
  restore writes the record and calls `record` in one database transaction, as the database
  rules plan says: TypeScript `this.prisma.$transaction(async (tx) => { ...; await this.history.record(..., tx); })`,
  where `record` takes the caller's transaction as `tx?: unknown` (the contract above; Python:
  the caller's `Session`, with one `commit()` by the caller),
  so history still writes only its own table. A failed history write rolls back the change. The
  action is `<singular>.created`, `.changed`, `.deleted` or `.restored`, with the subject (id
  and title), and the summary `Created the <singular>`, `<Label> changed from <old> to <new>`
  (one entry per changed field, joined by `; `, values as the CSV shows them; a replace that
  changes nothing adds no row), `Deleted the <singular>` or `Restored the <singular>`. The title
  is the first text field's value. Search index updates, which FORGE-SEARCH-1 plans, stay
  separate writes.
- **Restore (ACCESS).** SCREENS.md wins here. The list query gets `deleted` (optional `yes`):
  for a caller with `<plural>.restore` it shows the deleted items among the active ones, each
  with its `Deleted` Badge; for a caller without `.restore` the API ignores the key and shows
  only active items. A caller with `.restore` can also read a deleted item's detail;
  everyone else gets `404` for a deleted item, as today. `POST /api/v1/<plural>/:id/restore`
  needs `.restore`: it clears `deletedAtUtc` and `deletedByAccountId`, sets
  `modifiedByAccountId`, and writes the `Restored the <singular>` row in the same transaction; an
  item that is not deleted gets `404 <SINGULAR>_NOT_FOUND`. Web: the `Show deleted` Switch on
  the list and the Alert with its `Restore` button on a deleted item's detail screen, both shown only with
  `.restore`, with the texts and states the updated `docs/design/FORGE-FEATURE-1/` gives.
  Members never see deleted items.
- **Permissions (ACCESS).** Roles map to permissions in code.
  - TypeScript, `libs/core/server/src/common/permissions.ts`, exported from `@app/core-server`:
    `definePermissions(map: Record<MemberRole, readonly string[]>)` adds a module's map to one
    in-memory list and returns it; `permissionsFor(role: MemberRole): string[]`;
    `RequirePermission(permission: string)`, a guard decorator that refuses a caller whose role
    lacks it with `403 { code: 'PERMISSION_DENIED', message: 'You do not have permission to do this.', details: null }`.
    Every route of a feature controller has exactly one `@RequirePermission(...)`.
  - The one place per feature: `libs/<plural>/server/src/<plural>.permissions.ts`, for projects
    `export const PROJECT_PERMISSIONS = definePermissions({ admin: ['projects.view', 'projects.create', 'projects.edit', 'projects.delete', 'projects.restore'], member: ['projects.view', 'projects.create', 'projects.edit'] });`
    The module imports it, so the map is in place before the first request. A plan changes a
    feature's mapping by editing only this file.
  - Routes: list, detail, changes and export need `<plural>.view`; create needs `.create`;
    replace needs `.edit`; delete needs `.delete`; restore needs `.restore`. The list's
    `deleted=yes` key needs no route check: the service applies it only for a caller with
    `.restore`.
  - `/api/v1/auth/me`, sign-up and sign-in return `permissions: string[]` (from
    `permissionsFor(role)`) beside `role`; the shared `Account` type gets the field.
  - Web, `libs/core/web/src/permissions.ts`, exported from `@app/core-web`: `useCan(permission: string): boolean`, from the
    signed-in account's `permissions`. A screen whose view permission the person lacks shows the
    not-found page; a button or link whose permission the person lacks is not shown. The
    `Open the change history` link shows only for an admin, as SCREENS.md says. The web code is
    the same for both starters, because both APIs return `permissions`.
  - Python, `app/core/permissions.py`: `define_permissions(map)`, `permissions_for(role)`, and
    the dependency `require_permission("projects.delete")`, which loads the account as
    `admin_only` does, refuses with the same `403 PERMISSION_DENIED`, and checks CSRF on a
    non-GET request. The one place per feature is `app/<plural>/permissions.py`.
- **shadcn/ui components.** Each one is added, from the shadcn/ui registry as the starter's
  other components are (they use the installed `radix-ui` package, so no new dependency), by the
  part that first uses it, into `libs/shared/ui/src/components/ui/`: `card.tsx` by DETAIL (the detail screen's cards); `textarea.tsx`,
  `checkbox.tsx` and `popover.tsx` by WEB (the form controls for long text, yes or no, and the
  link Combobox with the existing `command.tsx`); `switch.tsx` and `alert.tsx` by ACCESS (the
  `Show deleted` Switch and the deleted item's Alert). The command copies a component that the app
  lacks from the Forge starter tree into `libs/shared/ui/src/components/ui/`.
- **The command line (COMMAND).**
  `forge task feature <plural> --one <singular> --field <name>:<kind> [--field ...]`.
  `<plural>` and `<singular>` are lower-case words joined by hyphens (`invoices`, `work-orders`;
  `--one invoice`, `--one work-order`). Forge makes every other form from them: `Invoice`,
  `Invoices`, `invoice`, `invoices`, `INVOICE` (TypeScript), `invoice`/`invoices` (Python
  packages and tables, `work_order`), `/invoices` (route and API path), `invoices.view` and the
  other permission names. `<name>` is camelCase (`dueDate`), with `?` at its end for an
  optional field (`dueDate?`). `<kind>` is one of `text`, `long-text`, `number`, `money`,
  `date`, `yes-no`, `email`, `status(<a>|<b>|...)` (the first option is the default) and
  `link(<plural of another feature>)` (the column is `<name>Id`). `table` is not a kind. Screen
  labels come from the field names (`dueDate` gives `Due date`); plurals of labels add `s`, or
  `es` after s, x, z, ch and sh; the worker fixes labels by hand when the plan asks for other
  words. The generated permissions file has the default mapping; the worker edits it when the
  plan gives another one.
  **Shell-safe.** `?`, `(`, `)` and `|` are shell characters, so the plan, the skill, the brief,
  the guide and the command's own messages always write each `--field` value in single quotes:
  `--field 'description?:long-text' --field 'status:status(planned|active|done)'`. The command
  reads the same syntax; quotes are only for the shell. (Quoted values are simpler than a fields
  file: no extra file to write, keep and delete.)
  **One text field.** Each feature needs at least one `text` field. The first one is its name:
  the list's first column and the keyboard link to the detail screen, the detail heading, the
  search, and the title in history summaries. A line with no text field is refused.
  Refusals, each with its next action, all checked before the command writes anything:
  not a starter app (item 6); a feature folder of that name already there; a field name that is
  not camelCase or is one of `id`, `organisationId`, `createdAtUtc`, `updatedAtUtc`,
  `createdByAccountId`, `modifiedByAccountId`, `deletedAtUtc`, `deletedByAccountId`; an unknown
  kind; a link to a feature that the app does not have; no `text` field
  (`A feature needs one text field for its name.` with
  `Next: add a field such as --field 'name:text'.`).
  On success it prints the files it wrote, one per line, then
  `Next: run the app's tests, then commit these files with your task.` A Python app also gets
  `corepack pnpm run api-types` in that line, before the tests.
- **The field-kind table (COMMAND creates it; FORGE-DATABASE-1/KINDS owns its database values).**
  `src/forge/templates/feature/kinds.toml`, one `[<kind>]` table for each of the nine kinds and
  one `[table]` table for what the command writes once for each new table. It is the only place
  that holds a column type, a check, an index or a per-kind snippet; `feature.py` reads every
  per-kind value from it and holds no column type, constraint, index or kind list of its own
  (review checks this). The format is the one FORGE-DATABASE-1 pins, so that story changes only
  values:
  - Database keys, owned by FORGE-DATABASE-1: `sql`, `prisma` and `sqlalchemy` (type and default
    only; the command writes `NOT NULL`, no `?` and `nullable=False` unless the field ends in
    `?`, and a `yes-no` field is NOT NULL even with `?`); `check`, `filter_index`,
    `search_index` and `index` (whole SQL statements or constraint clauses, or `""`; `index` is
    written for every field of its kind); for `money`, `currency_sql`, `currency_prisma` and
    `currency_sqlalchemy` (`""` here, so the command writes no currency column until that story
    sets them); `[table]` keys `id_sql`, `id_prisma`, `id_sqlalchemy`, `list_index` and
    `updated_at_trigger`.
  - Keys this story owns: `filter`, `search`, `column`, `zod`, `pydantic`, `input`, `cell`,
    `csv` (the export cell, also used in history summaries), `filter_options`, and `sample`,
    `changed` and `bad` (a valid value, a second valid value and an invalid value for the
    generated tests).
  - Placeholders the command fills in each starter's naming: `{table}`, `{column}`, `{org}`,
    `{created}`, `{updated}`, `{deleted}`, `{target}`, `{options}` (`'draft', 'sent'`),
    `{first}` and `{currency}`. SQL names are always in double quotes. There is no enum
    placeholder: a status list is `text` with a named CHECK, never a Postgres enum.
  - Every database value carries the comment
    `# placeholder: the database rules story sets this value`. The placeholders follow the
    owner's database rules already: no `varchar(n)` (text with a named length CHECK), no float,
    status as text with a named CHECK, foreign keys to `core` only, `ON DELETE RESTRICT`.
    Each feature's tables go in its own Postgres schema, named after the feature (the plural in
    snake form: `jobs`, `work_orders`), so every table name in the SQL is `"{schema}"."{table}"`
    and `{schema}` joins the placeholders. The starting values:

  | Kind | sql | check | index (filter, search or every field) |
  |---|---|---|---|
  | text | `text` | `CONSTRAINT "{table}_{column}_length" CHECK (char_length("{column}") BETWEEN 1 AND 200)` | search: `""` |
  | long-text | `text` | `CONSTRAINT "{table}_{column}_length" CHECK (char_length("{column}") <= 10000)` | none |
  | number | `numeric(19,4)`, as the database rules plan pins (the API carries it as a decimal string, so this story's `zod`, `pydantic`, `cell` and `sample` keys for number take a decimal string) | none (no sign check) | none |
  | money | `integer` (whole cents, for today's `formatMoney`; marked as the placeholder that FORGE-DATABASE-1 replaces with `numeric(19,4)` and a currency column) | none | none |
  | date | `date` | none | none |
  | yes-no | `boolean DEFAULT false` | none | filter: `CREATE INDEX "idx_{table}_{column}" ON "{table}" ("{org}", "{column}", "{updated}" DESC, "id" DESC) WHERE "{deleted}" IS NULL;` |
  | email | `text` | `CONSTRAINT "{table}_{column}_format" CHECK (char_length("{column}") <= 254 AND "{column}" ~ '^[^@[:space:]]+@[^@[:space:]]+$')` | none (only the first text field is the search) |
  | status | `text DEFAULT '{first}'` | `CONSTRAINT "{table}_{column}_allowed" CHECK ("{column}" IN ({options}))` | filter: as yes-no |
  | link | `uuid`, with no foreign key (the linked feature is another business module) | none | filter: as yes-no; index: `CREATE INDEX "idx_{table}_{column}_link" ON "{schema}"."{table}" ("{column}");` |

  `[table]`: the id keys are the uuidv7 id that FORGE-DATABASE-1/IDS gives the starter's tables
  (copied from the projects id after IDS merges, and marked as a placeholder);
  `list_index = 'CREATE INDEX "idx_{table}_list" ON "{schema}"."{table}" ("{org}", "{updated}" DESC, "id" DESC) WHERE "{deleted}" IS NULL;'`
  (every `ON "{table}"` in the values above reads `ON "{schema}"."{table}"` the same way)
  for the default sort, Updated newest first; and `updated_at_trigger` as IDS writes it for the
  starter's tables. The `filter`, `search` and `column` keys follow the filters-and-columns rule
  above.
- **Marks in the starter's projects files (COMMAND for the API files, WEB for the web files, PY
  for the Python files).** Each place in a projects file that lists the projects fields sits
  between a line `// forge:fields` and a line `// forge:end-fields` (`# forge:fields` in Python,
  `{/* forge:fields */}` in JSX). The command copies each projects file, renames every
  Project/project form to the feature's forms, and puts one rendered snippet per field between
  each pair of marks, from the kind table. The marks stay in new apps' projects files and in the
  copies, so a later agent sees where a field goes. Every other line, the paging, the
  permissions file and the history calls included, is a plain renamed copy. The Prisma model and
  the migration are not copies: the command writes them from the kind table, because projects
  keep their own Postgres enum and numbered columns (FORGE-DATABASE-1 leaves the starter's own
  status lists and lengths as they are).
- **The copy source.** The starter tree of the installed Forge (`sync.TEMPLATES / "starter"`;
  for Python `"starter-python"` plus the TypeScript `apps/web`), not the app's own projects
  module. This is the simpler one: Forge's own tests run this tree, so its marks and shape are
  known, and it still works after an app renames or removes its projects feature, as the
  prototype guide tells the agent to do. The app's own copy can be changed, renamed or gone.
- **The starter check (COMMAND pins it; PY adds the Python list).** The app is a TypeScript
  starter app when every one of these is there: `apps/api/prisma/schema/organisations.prisma`,
  `apps/api/prisma/schema/history.prisma` with its `subjectId` line,
  `apps/api/src/app.module.ts` with its `OrganisationsModule` import line and its
  `OrganisationsModule,` entry in `imports` (the starter's app module imports organisations, and
  organisations imports history, so the app module has no `HistoryModule` line),
  `libs/core/server/src/common/csv.ts`, `libs/core/server/src/common/permissions.ts`,
  `libs/history/contracts` (with `HISTORY_API`), `libs/shared/ui`, `eslint.config.mjs` with its
  module `scope:` lines, a migration that
  creates `set_updated_at()`, `apps/web/src/app.tsx` with its `/history` route and
  `apps/web/src/components/app-shell.tsx` with its Members item. It is a Python starter app
  when `apps/api/app/main.py` (with its `from app.history import router as history_router`
  and `app.include_router(history_router)` lines), `apps/api/app/organisations/`,
  `apps/api/app/history/` (with `subject_id` in its model), `apps/api/app/core/csv.py`,
  `apps/api/app/core/permissions.py`, a revision that creates `set_updated_at()`,
  `apps/api/migrations/versions/` and the same two web files are there. Wiring lines go next to
  these lines, never next to a projects line. Item 1's test runs the command in a freshly made
  starter app, so a new app passes this check. The first missing one gives the refusal
  `forge task feature needs a starter app (one made with forge init --starter), and this app has no <path>.`
  with `Next: build this feature by hand in this app.` Nothing is written. No other guard.
- **Generated test names.** The copies of the projects test files keep the projects case names
  with the feature's words: `creates, lists, reads, updates, and deletes an invoice through the API`,
  `pages invoices with next and previous cursors`, `filters invoices by search and filters`,
  `invoices export as CSV`, `another organisation gets 404 for an invoice`,
  `rejects an invalid invoice with field errors`,
  `each invoices endpoint refuses a member without its permission`,
  `records each invoice change in the change history`, `an admin restores a deleted invoice`,
  and the flows `an admin shows deleted invoices and restores one`,
  `create, view, edit, and delete an invoice`, `a reloaded invoices list link keeps its search, filters and page`,
  `an invoice's detail screen shows its recent changes` and
  `a member does not see the invoice actions they lack`. The projects names are the same with
  `project`. The Python HTTP cases use the same names in the snake form that FORGE-DEFAULTS-1
  pins.

### Done-when details

1. One step from the plan (COMMAND for TypeScript, PY for Python, GUIDE for the rules).
   - TypeScript output, three libraries copied from the projects ones:
     `libs/<plural>/contracts` (the zod schemas, types and the `<Plural>Api` interface with its
     `<PLURAL>_API` token in its `src/index.ts`), `libs/<plural>/server` (module, controller,
     service, DTO, permissions) and `libs/<plural>/web` (pages and hooks in `src`), each with its
     `package.json`, `project.json` (tags `type:contracts`, `type:server` or `type:web`, and
     `scope:<plural>`) and `tsconfig.json`; `apps/api/prisma/schema/<plural>.prisma` with
     `@@schema("<schema>")`; one migration folder
     `apps/api/prisma/migrations/<UTC yyyyMMddHHmmss>_<plural>/migration.sql` that starts with
     `CREATE SCHEMA "<schema>"`; any missing UI component; and the wiring: the schema name in
     `base.prisma`'s `schemas` list, the module in `app.module.ts`, the packages in
     `apps/api/package.json`, `apps/web/package.json` and the references of both apps'
     `tsconfig.json`, the pages in `apps/web/src/app.tsx`, the feature's `depConstraints` line
     `scope:<plural>` → `scope:<plural>`, `scope:core`, `scope:shared`, `type:contracts` in
     `eslint.config.mjs` (under the module lines' comment), its three importers in
     `pnpm-lock.yaml` (copied from the projects importers, so `pnpm install --frozen-lockfile`
     passes with no network), its three `dist` folders in `scripts/test-build.mjs`, and the
     back-relation lines in `model Account` and `model Organisation` (core links keep their
     foreign keys). Projects get the same `ProjectsApi` interface and `PROJECTS_API` token (one
     method, `get(principal, id)`), so the copy has them. The migration holds the table with each
     field's `sql` and `check`, the foreign keys to `core`, `[table]`'s `list_index`, each field's
     `filter_index`, `search_index` and `index` where they apply, the
     `updated_at_trigger`, and the soft delete trigger line
     `CREATE TRIGGER soft_delete_only BEFORE DELETE ON "<Model>" FOR EACH ROW EXECUTE FUNCTION soft_delete_only();`.
     Where Prisma's schema cannot say an index (a partial `WHERE`), the schema has the nearest
     `@@index` and the migration has the full statement. A link field adds
     `@app/<target>-contracts` to the new server library's `package.json` and `tsconfig.json`,
     and the service checks the linked item through the target's contracts service
     (`@Inject(<TARGET>_API)`, `get(account, id)`) before it writes it, so no query reads another
     module's table and no foreign key crosses the two schemas.
   - Python output (PY): `apps/api/app/<plural>/` (`__init__.py`, `models.py` with
     `__table_args__` naming the feature's schema and `ForeignKey("core.<table>.id")` for core
     links only, `schema.py`, `service.py`, `routes.py`, `permissions.py`; a link is checked
     through the target module's public service), one Alembic revision in
     `apps/api/migrations/versions/` named `<next number>_<plural>.py` whose `down_revision` is
     the current head (the one revision no other names as its down revision) with the same SQL
     from the kind table, the router in `main.py`, the model import in `migrations/env.py`, the
     `<plural> internals` contract in `apps/api/pyproject.toml`, and the Python
     `libs/<plural>/contracts` (the zod schemas, with types from `@app/shared-api-types`). The
     revision starts with `CREATE SCHEMA "<schema>"`. The web library and its wiring are the same
     as in a TypeScript app (WEB).
   - Test `tests/test_feature_command.py::test_1_a_plan_line_builds_the_feature_in_one_step`,
     parameters `typescript` and `python`: in a new repo made with `forge init --starter` (or
     `--starter python`), the two lines `forge task feature clients --one client --field 'name:text'`
     and `forge task feature jobs --one job --field 'name:text' --field 'description?:long-text'
     --field 'status:status(planned|active|done)' --field 'client?:link(clients)'
     --field 'hoursBudget?:number' --field 'budget?:money' --field 'dueDate?:date'
     --field 'contactEmail?:email' --field 'billable:yes-no'` (the SCREENS.md example, one field
     of each kind) run as shell lines, exactly as written, through `bash -c` and, where it is
     installed, `zsh -c` (with the forge command on `PATH`), so the test proves the line the
     planner writes and not an argument list. Each exits 0 and prints the files it wrote; every
     printed file exists; the wiring files have the new lines next to the starter check's anchor
     lines. Refusals in the same app, each leaving `git status --porcelain` as it was: a second
     run of the jobs line (the folder message); and one line for each malformed field: a field
     name that is not camelCase (`'Due-date:date'`), a reserved name (`'id:text'`), an unknown
     kind (`'size:large'`), a link to a missing feature (`'owner:link(people)'`), and no text
     field (`'paid:yes-no'` alone); each prints its own message and next action. Adopted case:
     the same two lines in the adopted starter app write the same files with the same text,
     apart from the migration's timestamp or revision number.
   - GUIDE adds to the same test: the forge skill after `forge init` (new repo) and after
     upgrade and sync (the adopted-v1.2.2 client) holds the planner line, and the worker brief
     that `forge work` writes holds the first-step line.
2. Works like projects (WEB for the screens; COMMAND and PY serve the API).
   - API: the keyset list, with search and filters, in the shared zod list schema (Pydantic in
     Python), with the same `.strict()` refusal of unknown keys; detail; changes; create;
     replace; soft delete; `GET /api/v1/<plural>/export` through `sendCsv` (Python: the
     `app.core` CSV helper), declared before `:id`. Every query is scoped to
     `account.organisationId`; another organisation gets `404 <SINGULAR>_NOT_FOUND`.
   - Web: `libs/<plural>/web/src/**` with the list page, the detail page, the delete
     AlertDialog, the form Dialog with its discard AlertDialog, the hooks and their unit test,
     all as SCREENS.md shows them with the feature's names; the route in `app.tsx`, a sidebar
     item and a Ctrl+K item in `app-shell.tsx` (shown only with the view permission), and its
     title in the page title map. The form has one control per field from the kind table's
     `input`, in the line's order. A link field works as the filters-and-columns rule says; the
     API returns only the id.
   - Test `tests/test_feature_command.py::test_2_the_new_feature_works_like_projects`,
     parameters `typescript` and `python`, live: after the item 1 lines in a new starter app,
     the app's own run passes and its reports hold the generated cases for create to delete,
     paging, search and filters, another organisation's 404, invalid input, the export with the
     formula guard (a `name` of `=1+1` comes back as `'=1+1`), and the flows for create to
     delete, the reloaded link and the recent changes. Adopted case: not live; the adopted
     starter app's generated files equal the new repo's (item 1's adopted case), so the live
     proof covers it.
3. Permissions (ACCESS for projects, COMMAND, WEB and PY for the copies).
   - The generated API case `each <plural> endpoint refuses a member without its permission`
     is table-driven: it lists every route with its permission, signs in a member (an invite
     from the admin, as `invites.e2e-spec.ts` does), reads the member's `permissions` from
     `/auth/me`, and for each route expects `403 PERMISSION_DENIED` when the member lacks the
     permission and no 403 when the member has it. So it covers every route and stays right
     after a plan edits the mapping. With the default mapping, the member gets 403 on delete,
     and restore only, and the admin gets no 403 on any route.
   - The flow `a member does not see the <singular> actions they lack` reads the member's
     permissions too: without view, the list and detail routes show the not-found page and the
     sidebar item is gone; without create, no New button; without edit, no Edit button; without
     delete, no Delete button; without restore, no `Show deleted` filter. The
     `Open the change history` link is never shown to a member.
   - Restore: the generated API case `an admin restores a deleted <singular>` deletes an item,
     finds it, with the active items, in the list with `deleted=yes`, restores it, finds it in
     the normal list again and finds `Restored the <singular>` in its changes; a member's restore
     is refused by the endpoint case above, a member's `deleted=yes` list holds no deleted item,
     and a member gets 404 for the deleted item's detail.
     The flow `an admin shows deleted <plural> and restores one` uses the `Show deleted` filter
     and the detail screen's Restore button.
   - **Denied view, create and edit.** With the default mapping the member lacks only delete and restore,
     so the live runs also build a third feature, `forge task feature notes --one note
     --field 'title:text'`, and the Forge test then sets `member: []` in its one permissions
     file (`libs/notes/server/src/notes.permissions.ts`, Python `app/notes/permissions.py`) before the
     app's run. The same generated case for notes then expects 403 for the member on every route:
     list, detail, changes and export (view), create, replace (edit), delete and restore; and
     the notes
     flow sees the not-found page. A route guarded by the wrong permission fails here.
   - Test `tests/test_feature_access.py::test_3_each_feature_checks_its_permissions`,
     parameters `projects-typescript` and `projects-python` (ACCESS), `feature-typescript`
     (WEB) and `feature-python` (PY), live: the run's reports hold the endpoint case and the
     flow for projects, or for the item 1 jobs and for notes, and the restore case and flow for
     projects or jobs. Projects keep the default mapping,
     so their live case proves the denied delete and restore; the notes feature proves denied view, create
     and edit through the same copied case, and the check below proves that projects name the
     right permission on each route. Not live, in the same test: every
     route method in the projects controller and in the generated controllers has exactly one
     `@RequirePermission`, and its permission is the one the route needs (list, detail, changes
     and export `.view`, create `.create`, replace `.edit`, delete `.delete`, restore
     `.restore`); Python: one
     `require_permission` dependency with the same names. Adopted case: not live;
     after upgrade and sync, the adopted starter app's permissions files and controllers are the
     same as a new app's.
4. Table, Change history rows, the kind table and passing tests (COMMAND pins the non-live
   checks; WEB and PY add the live runs).
   - The table has `organisationId` and the audit columns `createdByAccountId`,
     `modifiedByAccountId`, `deletedAtUtc` and `deletedByAccountId`, as projects; create,
     update and delete set them; delete sets `deletedAtUtc`, and the trigger refuses a hard
     delete. The service records each create, change, delete and restore in the same
     transaction, as the Change history rule above says.
   - The generated test files are renamed copies of the projects test files that PAGING, DETAIL
     and ACCESS add: `apps/api/test/<plural>.e2e-spec.ts`, `apps/web/e2e/<plural>.spec.ts`,
     `libs/<plural>/web/src/hooks/<plural>-hooks.test.tsx`, and in Python
     `apps/api/tests/test_<plural>.py`. Their values come from the kind table's `sample`,
     `changed` and `bad`.
   - Test `tests/test_feature_command.py::test_4_the_feature_keeps_history_and_its_tests_pass_at_once`,
     parameters `typescript` and `python`. Not live: the test reads the shipped `kinds.toml`
     and checks that the generated migration (and in Python the Alembic revision and
     `models.py`) has each field's `sql` or `sqlalchemy` value with the NOT NULL rule, its
     `check`, `[table]`'s `list_index` (on the organisation column, the last-change column
     `updatedAtUtc` / `updated_at_utc` descending and `id` descending, not on the created
     column) and `updated_at_trigger`, the filter, search and
     every-field indexes, the audit columns, the soft delete trigger, `CREATE SCHEMA` and every
     table name in the feature's schema, the link index `idx_<table>_<column>_link` with no
     foreign key to the linked feature, and no `CREATE TYPE`; and that the three libraries carry
     their `type:` and `scope:<plural>` tags and `eslint.config.mjs` has the feature's
     `depConstraints` line. Live:
     one cached run per starter (shared with test_2 and test_3, as `live_run` does) of the app's
     `node scripts/test.mjs` after the item 1 lines exits 0, and the reports hold every generated
     case name above, `records each job change in the change history` among them (it creates,
     changes, deletes and restores a job as the admin, then reads `/api/v1/history` and the
     job's changes and finds the four summaries). The Python app's own test script runs
     `api-types` first.
     Adopted case: the non-live check in the adopted starter app.
5. Projects source (PAGING, DETAIL, ACCESS; each part changes both APIs and the web app).
   - PAGING: the keyset list query, `search` (optional, trimmed, at most 200) and `status`
     (optional `projectStatusSchema`) in `projectListQuerySchema` and the Python schema; the
     projects page with the search box, the status Select, column sort, Previous and Next and
     the total, all in the URL; the `New project` button; the form's submit button
     `Create project` (`Save changes` for an edit). The rows keep their Edit and Delete icons in
     PAGING, so the create, edit and delete flow works until DETAIL moves those actions to the
     detail screen. The existing cases that read projects `page`, `limit` or `pagination`, or
     click the old `Create project` list button, change to the new form: the list, bad query and
     list query docs cases in `api.e2e-spec.ts`, the projects list check in
     `organisations.e2e-spec.ts`, the projects reads in `invites.e2e-spec.ts` and
     `soft-delete.e2e-spec.ts`, the flows in `starter-shell.spec.ts` and `join.spec.ts`, and
     their Python twins in `test_api.py`, `test_organisations.py`, `test_invites.py` and
     `test_soft_delete.py`. The members list keeps its numbered pages. The
     projects cases move to their own files, with no name change: the API cases in
     `apps/api/test/projects.e2e-spec.ts`, the flows in `apps/web/e2e/projects.spec.ts`, and in
     Python `apps/api/tests/test_projects.py`. New cases: `pages projects with next and
     previous cursors`, `filters projects by search and filters`, and the flow
     `a reloaded projects list link keeps its search, filters and page`, which replaces
     `a reloaded or shared list link shows the same view` (update that name in
     `BROWSER_FLOWS` in `tests/test_starter_tree.py`).
   - DETAIL: `ProjectDetailPage` at `/projects/:id` with the breadcrumb, the Details card, the
     Recent changes card, Edit (the form Dialog) and Delete (the AlertDialog), as SCREENS.md
     shows them; rows lose their Edit and Delete icons and open the detail screen (the name is
     the link, and the row can be clicked), and `create, edit, and delete a project` becomes
     `create, view, edit, and delete a project`, through the detail screen; the history subject
     columns and `listForSubject`; the changes route; the Change history rows for projects; the
     Change history screen's subject name. New cases:
     `records each project change in the change history` and the flow
     `a project's detail screen shows its recent changes`.
   - ACCESS: the projects permissions, `permissions` on the account, `useCan`, the hidden
     Delete and history link, and restore: the `deleted` list query, the restore route with its
     history row in the same transaction, the `Show deleted` filter and the Restore button, in
     both APIs and the web app. New cases: `an admin restores a deleted project` and the flow
     `an admin shows deleted projects and restores one`. The member delete in `invites.e2e-spec.ts` (`a member` deletes
     the admin's project) and its Python twin in `test_invites.py` now expect
     `403 PERMISSION_DENIED`, and the case reads the member's `permissions` from `/auth/me`. The
     permission cases are item 3's.
   - Test `tests/test_feature_projects.py::test_5_projects_have_the_list_detail_and_history`,
     live, parameters `typescript` and `python`: the starter's run holds the new PAGING and
     DETAIL cases. Adopted case: after upgrade and sync, the adopted starter app's projects files
     are unchanged (sync writes no app file).
6. Refusal (COMMAND; PY adds the Python check list).
   - Test `tests/test_feature_command.py::test_6_outside_a_starter_app_the_command_refuses`:
     in a new repo made with plain `forge init`, `forge task feature jobs --one job
     --field name:text` exits non-zero with the needs-a-starter-app line and
     `Next: build this feature by hand in this app.`, and `git status --porcelain` is empty.
     Adopted case: the adopted-v1.2.2 client (no starter files) after upgrade gets the same
     refusal; and the adopted starter app with `libs/history` and `history.prisma` removed (the
     shape of an app made from the v1.2.21 starter) refuses and names
     `apps/api/prisma/schema/history.prisma`.

### Skill, brief and guide (GUIDE)

- `src/forge/templates/skill.md`, Planning a story: when a story adds a new thing that a client
  app keeps track of and the app is a starter app, the planner writes, in the first part's
  Done-when details, one `forge task feature` line per new thing, each `--field` value in single
  quotes, with at least one text field (the name), with every field from the
  brief's `## Things it keeps track of`, in the kinds the command takes, and the role mapping
  when it is not the default (admins all five, members all but delete and restore); many-to-many links,
  files and computed fields go in the part as hand work. A link's target comes first, in the
  same line order. The part's Scope lists the folders the command writes.
- `src/forge/templates/brief.md`, Build simple: when your part's details give a
  `forge task feature` line, run it first, set the plan's role mapping in the feature's one
  permissions file, run the app's tests, and commit its files before any other change; then
  rename labels and add the hand work. Do not hand-build a feature the command can build. In an
  app with `libs/core/server/src/common/permissions.ts` (Python: `app/core/permissions.py`), guard
  each new route with one permission check.
- `docs/guide.md`: one paragraph with the command line, the field kinds, the permissions, the
  starter-app rule, the kind table's place, and that the agent runs it from the plan.
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
| PAGING | Projects list with keyset paging and URL filters | Keyset paging, search and the status filter in both APIs and the projects contracts; the projects list as SCREENS.md shows it, with Previous, Next and the total; rows that open the detail route; the button and form labels; the projects cases in their own files. | 2, 5 | `starter/libs/projects/contracts/**`, `starter/libs/projects/server/**`, `starter/libs/projects/web/**`, `starter/apps/web/src/app.tsx`, `starter/apps/api/test/api.e2e-spec.ts`, `starter/apps/api/test/organisations.e2e-spec.ts`, `starter/apps/api/test/invites.e2e-spec.ts` and `starter/apps/api/test/soft-delete.e2e-spec.ts` (projects paging and button lines only), `starter/apps/api/test/projects.e2e-spec.ts` (new), `starter/apps/web/e2e/starter-shell.spec.ts`, `starter/apps/web/e2e/join.spec.ts` (button name only), `starter/apps/web/e2e/projects.spec.ts` (new), `starter-python/apps/api/app/projects/**`, `starter-python/apps/api/tests/test_api.py`, `starter-python/apps/api/tests/test_organisations.py`, `starter-python/apps/api/tests/test_invites.py` and `starter-python/apps/api/tests/test_soft_delete.py` (projects paging lines only), `starter-python/apps/api/tests/test_projects.py` (new), `starter-python/libs/projects/contracts/**`, `starter-python/libs/shared/api-types/**` (regenerated), `tests/test_starter_tree.py` and `tests/test_python_starter.py` (case names only), `.github/workflows/starter-smoke.yml` | `tests/test_feature_projects.py` (`test_5`, `typescript` and `python`, new) | FORGE-LIBS-1/WEB | yes | |
| DETAIL | Projects detail screen and change history | The detail screen with its Details and Recent changes cards, Edit and the Delete AlertDialog; the Card component; the history subject columns, migrations, `listForSubject` and the `tx` argument on `HistoryApi`; the changes route; a Change history row for each projects create, change and delete; the subject name on the Change history screen; in both APIs. | 4, 5 | `starter/libs/shared/ui/src/components/ui/card.tsx` (new), `starter/libs/projects/**`, `starter/libs/history/**`, `starter/apps/web/src/app.tsx`, `starter/apps/api/prisma/schema/history.prisma`, `starter/apps/api/prisma/migrations/<new>_history_subjects/` (new), `starter/pnpm-lock.yaml` (`@app/history-contracts` for projects), `starter/apps/api/test/projects.e2e-spec.ts`, `starter/apps/web/e2e/projects.spec.ts`, `starter-python/apps/api/app/history/**`, `starter-python/apps/api/app/projects/**`, `starter-python/apps/api/migrations/versions/<next>_history_subjects.py` (new), `starter-python/apps/api/tests/test_projects.py`, `starter-python/libs/projects/contracts/**`, `starter-python/libs/history/contracts/**`, `starter-python/libs/shared/api-types/**` (regenerated) | `tests/test_feature_projects.py` (`test_5`, the DETAIL case names) | PAGING, FORGE-LIBS-1/WEB | yes | |
| ACCESS | Projects permissions and restore | The permissions helpers and guard in both APIs, `permissions` on the account, `useCan` in core web, the projects permissions file and one check on each projects route, the hidden Delete and history link, and the admin's deleted list and restore with its history row. | 3, 5 | `starter/libs/core/server/src/common/permissions.ts` (new), `starter/libs/core/server/src/index.ts`, `starter/libs/core/web/src/permissions.ts` (new), `starter/libs/core/web/src/index.ts`, `starter/libs/auth/**` (account `permissions` only, in its server and contracts), `starter/libs/projects/**` (the projects list query's `deleted` key in its contracts included), `starter/libs/shared/ui/src/components/ui/switch.tsx` and `alert.tsx` (new), `starter/apps/web/src/components/app-shell.tsx`, `starter/apps/api/test/projects.e2e-spec.ts`, `starter/apps/api/test/invites.e2e-spec.ts` (the member delete only), `starter/apps/web/e2e/projects.spec.ts`, `starter-python/apps/api/tests/test_invites.py` (the member delete only), `starter-python/apps/api/app/core/permissions.py` (new), `starter-python/apps/api/app/core/__init__.py`, `starter-python/apps/api/app/auth/**` (account `permissions` only), `starter-python/apps/api/app/projects/**`, `starter-python/apps/api/tests/test_projects.py`, `starter-python/libs/auth/contracts/**` and `starter-python/libs/projects/contracts/**`, `starter-python/libs/shared/api-types/**` (regenerated) | `tests/test_feature_access.py` (`test_3`, `projects-typescript` and `projects-python`, new) | DETAIL, FORGE-LIBS-1/WEB | yes | |
| COMMAND | The feature command and the TypeScript API copy | `forge task feature` with its line, refusals and starter check, the field-kind table with placeholder database values, the marks in the projects contracts and server files, the projects `ProjectsApi` contract and token, and the TypeScript contracts, server, permissions, Prisma schema, migration with its own Postgres schema, tags, `depConstraints` line, build folders and wiring copy. | 1, 4, 6 | `src/forge/cli.py` (one route), `src/forge/feature.py` (new), `src/forge/templates/feature/kinds.toml` (new), `starter/libs/projects/contracts/**` (marks, `ProjectsApi` and `PROJECTS_API`), `starter/libs/projects/server/**` (marks and the token provider), `starter/apps/api/test/projects.e2e-spec.ts` (marks only), `.github/workflows/starter-smoke.yml` | `tests/test_feature_command.py` (`test_1`, `test_4` not-live checks, `test_6`, `typescript`, new) | ACCESS, FORGE-LIBS-1/WEB, FORGE-LIBS-1/SCHEMAS, FORGE-LIBS-1/SCHEMASPY, FORGE-DATABASE-1/PG18, FORGE-DATABASE-1/IDS, FORGE-DATABASE-1/IDSPY | no | |
| WEB | The feature's screens | The marks in the projects web library, the Textarea, Checkbox and Popover components, and the web library copy: list, detail, delete dialog, form with one control per field, hooks and their test, the pages in `app.tsx`, sidebar and Ctrl+K items; the live TypeScript run with the generated cases. | 2, 3, 4 | `src/forge/feature.py` (the web copy only), `src/forge/templates/feature/kinds.toml` (the `input`, `cell`, `filter_options` and `column` keys only), `starter/libs/shared/ui/src/components/ui/textarea.tsx`, `checkbox.tsx` and `popover.tsx` (new), `starter/libs/projects/web/**` and `starter/apps/web/e2e/projects.spec.ts` (marks only) | `tests/test_feature_command.py` (`test_2`, `test_4` live, `typescript`); `tests/test_feature_access.py` (`test_3`, `feature-typescript`) | COMMAND, FORGE-LIBS-1/WEB, FORGE-LIBS-1/SCHEMAS, FORGE-LIBS-1/SCHEMASPY | yes | |
| PY | The Python API copy | The marks in the Python projects files, the Python starter check, and the Python API with its own Postgres schema, permissions, Alembic revision, Python contracts library on `@app/shared-api-types`, and wiring; the Python parameters of the feature tests, `test_2` and `test_6` included. | 1, 3, 4 | `src/forge/feature.py` (the Python copy only), `src/forge/templates/feature/kinds.toml` (`sqlalchemy` and `pydantic` keys only), `starter-python/apps/api/app/projects/**` and `starter-python/apps/api/tests/test_projects.py` (marks only), `starter-python/libs/projects/contracts/**` (marks only) | `tests/test_feature_command.py` (`test_1`, `test_2`, `test_4`, `test_6`, `python`); `tests/test_feature_access.py` (`test_3`, `feature-python`) | WEB, FORGE-LIBS-1/WEB, FORGE-LIBS-1/SCHEMAS, FORGE-LIBS-1/SCHEMASPY | no | |
| GUIDE | Planner and worker rules | The planner rule in the skill, the first-step and permission rules in the worker brief, and the guide paragraph, on new and existing repos. | 1 | `src/forge/templates/skill.md`, `src/forge/templates/brief.md`, `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `docs/guide.md` | `tests/test_feature_command.py` (`test_1`: the skill and brief checks on a new and an adopted repo) | COMMAND, FORGE-LIBS-1/WEB | no | |

New moving parts: none (the permissions list in core is a plain in-memory map that each module
fills at start, for item 3; no service, store or cache)

## Notes

- **Order with FORGE-LIBS-1.** Every part waits for FORGE-LIBS-1/WEB, so it builds on the
  library layout; COMMAND, WEB and PY also wait for FORGE-LIBS-1/SCHEMAS and SCHEMASPY, so the
  copy follows one Postgres schema per module and the link rule. FORGE-LIBS-1 pins the link
  index name `idx_{table}_{column}_link`; FORGE-DATABASE-1/KINDS keeps that name when it sets the
  final values.
- **Order.** PAGING, then DETAIL, then ACCESS, one after another: each changes the projects
  files that the next one builds on. Each of the three changes both APIs and the web app, so
  main never has a web app that the Python API cannot serve. COMMAND waits for ACCESS and for
  FORGE-DATABASE-1's starter-table parts (PG18, IDS and IDSPY): the database story's
  starter-table parts merge before this story's COMMAND part, so the copy takes the uuidv7 ids,
  the time columns and the `set_updated_at()` trigger from the starter. WEB and GUIDE after
  COMMAND: WEB extends `feature.py`, and GUIDE adds its checks to COMMAND's test_1. PY last,
  after WEB (the Python live run runs the web flows). FORGE-DATABASE-1/KINDS waits for PY and
  then sets the final database values. All parts ship in one release.
- **Migration order.** DETAIL's history migration and FORGE-DATABASE-1's migrations can merge
  in either order. Whichever part merges later gives its Prisma folder a later timestamp and
  chains its Alembic revision to the head on main.
- **Part sizes.** PAGING, DETAIL and ACCESS each change both APIs and the web app, so each may
  pass 400 lines; split the generated `openapi.json` and `api-types.ts` out of the count, and
  ask for `forge fix allow-large` with that reason before you split a part. COMMAND is the
  largest Forge change: if it goes over 400 lines, move the shared-schema copy into WEB.
- **What a new and an existing client repo get.** New repos (`forge init --starter` and
  `--starter python`): the projects list with keyset paging and URL filters, the detail screen
  with recent changes, the permissions, restore for admins and Change history rows, the marks in the projects
  files, the projects test files, and the command, which works at once. Plain `forge init`: the
  command, which refuses. Existing repos, on upgrade and sync: the command and the skill, brief
  and guide texts; no app file changes. An existing app that started from the current starter
  can use the command at once; an app made from an older starter or another stack gets the
  refusal, which names what is missing.
- **Owner decisions (25 Oct 2026, settled).** The agent runs the command from the plan and the
  FDE never types it; it copies the starter's projects feature, renamed, with the plan's fields,
  in both starters; the nine field kinds and no many-to-many, file or computed fields; starter
  apps only, with a refusal that names what is missing and changes nothing, also for older
  starter apps; no extra guards for unlikely races or security edge cases; one shipped
  field-kind table for column types and indexes, whose database values the database rules
  story owns; no cache server; a Change history row for each create, change, delete and
  restore, written in the same database transaction as the record (search updates stay
  separate writes, as FORGE-SEARCH-1 plans), projects first; five permissions per feature in
  code (admins all five, members all but delete and restore), one check on every endpoint and
  screen, a test per endpoint, one place per feature to change the mapping, projects first;
  admins can show deleted items and restore one, members never see deleted items; no
  row-level security: app scoping and the per-endpoint refusal tests stay; keyset paging with Previous, Next and an approximate total, the
  cursor in the URL; the detail screen with recent changes and an admin-only history link;
  delete for admins only, from the detail screen, in an AlertDialog; the screens in
  `docs/design/FORGE-FEATURE-1/`.
- **Planner choices the owner did not make.** (1) The command sits under `forge task`, because
  the command cap is full. (2) The copy is from the installed Forge's starter tree, with marks
  for the field places in the projects files, not from the app's own projects code. (3) The API
  returns the caller's permissions on the account, so the same web code works with both APIs.
  (4) A screen without its view permission shows the not-found page. (5) Previous uses a
  `before=<cursor>` in the URL; the total counts up to 10,000. (6) The starter's projects keep
  their two fields; the nine-field example in SCREENS.md is what the command makes for the
  item 1 line. (7) The recent changes come from two new columns on the change history table.
  (8) A replace that changes no field adds no history row. (9) A field can be optional with
  `?`; the line gives both the plural and the singular.
- **Single-company apps.** A single-company app keeps the same code, with one organisation that
  Forge makes at setup; the command needs no change for it.
- **For the database rules story.** FORGE-DATABASE-1/KINDS sets the final database values in
  `kinds.toml` and the money keys that follow its money helper. Its `list_index` and filter
  indexes use the last-change time, which matches this story's default sort (Updated, newest
  first) and the `{updated}` placeholder. The number kind is `numeric(19,4)` with no sign
  check. Contact email fields stay not unique; the sign-in email's lower-case check is that
  story's.
- **Design follow-up.** The designer is updating `docs/design/FORGE-FEATURE-1/` for restore
  (the deleted list and the deleted item's detail). The Design line keeps the old tree id until
  the owner gives the new one. SCREENS.md's number message (`Enter a whole number, 0 or more.`)
  does not fit a `numeric(19,4)` number with no sign check; the design update should change it.
- **Cold read round 1.**
  1. Starter check anchor: amended; the check uses the `OrganisationsModule` lines that a new
     app has, and item 1's test runs on a fresh starter app.
  2. Test files outside Scope: amended; PAGING and ACCESS Scopes name the organisations,
     invites, soft delete and join tests of both starters, with what each changes.
  3. PAGING removed edit and delete early: amended; rows keep their Edit and Delete icons in
     PAGING, and DETAIL moves them to the detail screen.
  4. Shell-unsafe line: amended; every `--field` value is in single quotes in the plan, skill,
     brief and guide, and test_1 runs the lines through `bash -c` and `zsh -c`.
  5. No text field: amended; a feature needs one text field, its name, and the command refuses
     a line without one.
  6. Denied view, create and edit unproven: amended; a notes feature with `member: []` runs the
     same table-driven case on every route, and the static check names each route's permission.
  7. Advisory, linked items beyond one page: decided; the link filter and Combobox are a
     searchable Select that pages through the target's list API, and cells read the target's
     detail hook.
  8. Advisory, malformed-field refusals: decided; test_1 adds one refusal line for each
     malformed kind and checks that nothing changes.
- **No cache.** No cache server and no cache layer in the generated code; list queries use the
  indexes above.
- No client repo is named anywhere in this story's code, tests, texts or commits.
