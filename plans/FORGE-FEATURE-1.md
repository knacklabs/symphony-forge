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
- Each feature has four permissions: view, create, edit and delete. Admins have all four.
  Members can view, create and edit, but not delete. The app checks the permission on every
  screen and every API call. A plan can change which role has which permission for a feature,
  in one place in that feature's code.
- Its table keeps deleted items. Each create, change and delete adds a row to the Change history
  screen with who, when and what changed.
- A field can be text, long text, number, money, date, yes or no, email, a status list, or a link
  to one item of another feature. The agent adds other kinds of field by hand.
- The new feature comes with its own API and screen tests, and they pass at once.
- The projects feature in a new app gets these first: the paging, search and status filter in
  the web address, the detail screen with its recent changes, the four permissions, and a Change
  history row for each create, change and delete.
- In an app that did not start from the starter, the command says that it needs a starter app
  and changes nothing.
- Existing apps keep their code. On upgrade they get the command and the guide text. An existing
  app that started from the current starter can use the command at once. An app made from an
  older starter, without organisations or change history, gets a refusal that names what is
  missing.
Design: docs/design/FORGE-FEATURE-1/ (bbee968f36f83fc86a9b0c81bc1c0927dbfe1304)

## Why

FDEs must ship client features without technical choices. Today each new feature is built by
hand in the TypeScript or the Python starter. The agent decides the table, the checks, the
access, the screens, the export and the tests again for each feature, and each feature comes out
a little different. The starter's projects feature already has soft delete, checked input, CSV
export with the formula guard, organisation access and its tests. One command that copies it,
renamed and with the plan's fields, makes each new feature the same and passing from the first
commit. On 25 October 2026 the owner chose this command, the field kinds, starter apps only,
four permissions for each feature, a Change history row for each change, and keyset paging.

## Done when

1. **When a plan names a new feature and its fields, the worker's first step builds it in a TypeScript or a Python starter app with one command.**
2. **The new feature has a list with search, filters, column sort and Previous and Next paging kept in the web address, a detail screen with its recent changes, a form, and a CSV export that keeps formulas as text, for its own organisation only.**
3. **Each feature checks a view, create, edit and delete permission on every screen and API call; admins have all four and members all but delete, and one place in the feature's code changes this.**
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

Trade-off: members can no longer delete projects in a new app. Only admins can.

Trade-off: the change and its Change history row are two writes, not one transaction. If the
second write fails, the change stays without its row.

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
  with the item id in the URL. The first `text` or `email` field is the search, with the
  placeholder `Search by <label>`; a feature with neither has no search box. No other kind gets a
  filter. List columns: the first text field (a link to the detail screen), each `status`,
  `link`, `date` and `money` field, then Updated. Every column header sorts. This comes from the
  `filter`, `search` and `column` keys of the kind table, not from code.
- **The detail screen and recent changes (DETAIL).** `/<plural>/:id`, as SCREENS.md shows it.
  The change history table gets `subjectId uuid NULL` and `subjectName text NULL`, and the index
  `(organisationId, subjectId, createdAtUtc DESC)`, in one new migration in each starter (the
  TypeScript migration folder and the next Alembic revision on main, chained to the head at
  build time). `HistoryService.record(principal, action: string, summary: string, subject?: { id: string; name: string })`
  (Python `record(account, action: str, summary: str, subject: Subject | None = None)`) and
  `listForSubject(principal, subjectId, limit)`. Route `GET /api/v1/<plural>/:id/changes`
  returns the newest 5 as `{ id, actorEmail, summary, createdAtUtc }[]`. The Change history
  screen and its CSV show `<subjectName>: <summary>` when `subjectName` is set.
- **Change history rows (DETAIL).** Each create, change and delete calls `record` after the
  write, with the action `<singular>.created`, `.changed` or `.deleted`, the subject (id and
  title), and the summary `Created the <singular>`,
  `<Label> changed from <old> to <new>` (one entry per changed field, joined by `; `, values as
  the CSV shows them; a replace that changes nothing adds no row), or `Deleted the <singular>`.
  The title is the first text field's value, or the id when the feature has none. A `ponytail:`
  comment says the two writes are not one transaction.
- **Permissions (ACCESS).** Roles map to permissions in code.
  - TypeScript, `libs/core/src/common/permissions.ts`, exported from `@app/core`:
    `definePermissions(map: Record<MemberRole, readonly string[]>)` adds a module's map to one
    in-memory list and returns it; `permissionsFor(role: MemberRole): string[]`;
    `RequirePermission(permission: string)`, a guard decorator that refuses a caller whose role
    lacks it with `403 { code: 'PERMISSION_DENIED', message: 'You do not have permission to do this.', details: null }`.
    Every route of a feature controller has exactly one `@RequirePermission(...)`.
  - The one place per feature: `libs/<plural>/src/<plural>.permissions.ts`, for projects
    `export const PROJECT_PERMISSIONS = definePermissions({ admin: ['projects.view', 'projects.create', 'projects.edit', 'projects.delete'], member: ['projects.view', 'projects.create', 'projects.edit'] });`
    The module imports it, so the map is in place before the first request. A plan changes a
    feature's mapping by editing only this file.
  - Routes: list, detail, changes and export need `<plural>.view`; create needs `.create`;
    replace needs `.edit`; delete needs `.delete`.
  - `/api/v1/auth/me`, sign-up and sign-in return `permissions: string[]` (from
    `permissionsFor(role)`) beside `role`; the shared `Account` type gets the field.
  - Web, `apps/web/src/lib/permissions.ts`: `useCan(permission: string): boolean`, from the
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
  part that first uses it: `card.tsx` by DETAIL (the detail screen's cards); `textarea.tsx`,
  `checkbox.tsx` and `popover.tsx` by WEB (the form controls for long text, yes or no, and the
  link Combobox with the existing `command.tsx`). The command copies a component that the app
  lacks from the Forge starter tree into `apps/web/src/components/ui/`.
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
  Refusals, each with its next action, all checked before the command writes anything:
  not a starter app (item 6); a feature folder of that name already there; a field name that is
  not camelCase or is one of `id`, `organisationId`, `createdAtUtc`, `updatedAtUtc`,
  `createdByAccountId`, `modifiedByAccountId`, `deletedAtUtc`, `deletedByAccountId`; an unknown
  kind; a link to a feature that the app does not have.
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
    status as text with a named CHECK, foreign keys `ON DELETE RESTRICT`. The starting values:

  | Kind | sql | check | index (filter, search or every field) |
  |---|---|---|---|
  | text | `text` | `CONSTRAINT "{table}_{column}_length" CHECK (char_length("{column}") BETWEEN 1 AND 200)` | search: `""` |
  | long-text | `text` | `CONSTRAINT "{table}_{column}_length" CHECK (char_length("{column}") <= 10000)` | none |
  | number | `integer` | `CONSTRAINT "{table}_{column}_min" CHECK ("{column}" >= 0)` | none |
  | money | `integer` (whole cents, for today's `formatMoney`; marked as the placeholder that FORGE-DATABASE-1 replaces with `numeric(19,4)` and a currency column) | none | none |
  | date | `date` | none | none |
  | yes-no | `boolean DEFAULT false` | none | filter: `CREATE INDEX "idx_{table}_{column}" ON "{table}" ("{org}", "{column}", "{updated}" DESC, "id" DESC) WHERE "{deleted}" IS NULL;` |
  | email | `text` | `CONSTRAINT "{table}_{column}_format" CHECK (char_length("{column}") <= 254 AND "{column}" ~ '^[^@[:space:]]+@[^@[:space:]]+$')` | search: `""` |
  | status | `text DEFAULT '{first}'` | `CONSTRAINT "{table}_{column}_allowed" CHECK ("{column}" IN ({options}))` | filter: as yes-no |
  | link | `uuid`, with a foreign key to `{target}` `ON DELETE RESTRICT` | none | filter: as yes-no; index: `CREATE INDEX "idx_{table}_{column}_fk" ON "{table}" ("{column}");` |

  `[table]`: the id keys are the uuidv7 id that FORGE-DATABASE-1/IDS gives the starter's tables
  (copied from the projects id after IDS merges, and marked as a placeholder);
  `list_index = 'CREATE INDEX "idx_{table}_list" ON "{table}" ("{org}", "{updated}" DESC, "id" DESC) WHERE "{deleted}" IS NULL;'`
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
  `apps/api/src/app.module.ts` with its `HistoryModule` line, `libs/core/src/common/csv.ts`,
  `libs/core/src/common/permissions.ts`, a migration that creates `set_updated_at()`,
  `apps/web/src/app.tsx` with its `/history` route and `apps/web/src/components/app-shell.tsx`
  with its Members item. It is a Python starter app when `apps/api/app/main.py` (with its
  history router line), `apps/api/app/organisations/`, `apps/api/app/history/` (with
  `subject_id` in its model), `apps/api/app/core/csv.py`, `apps/api/app/core/permissions.py`,
  a revision that creates `set_updated_at()`, `apps/api/migrations/versions/` and the same two
  web files are there. Wiring lines go next to these lines, never next to a projects line. The
  first missing one gives the refusal
  `forge task feature needs a starter app (one made with forge init --starter), and this app has no <path>.`
  with `Next: build this feature by hand in this app.` Nothing is written. No other guard.
- **Generated test names.** The copies of the projects test files keep the projects case names
  with the feature's words: `creates, lists, reads, updates, and deletes an invoice through the API`,
  `pages invoices with next and previous cursors`, `filters invoices by search and filters`,
  `invoices export as CSV`, `another organisation gets 404 for an invoice`,
  `rejects an invalid invoice with field errors`,
  `each invoices endpoint refuses a member without its permission`,
  `records each invoice change in the change history`, and the flows
  `create, view, edit, and delete an invoice`, `a reloaded invoices list link keeps its search, filters and page`,
  `an invoice's detail screen shows its recent changes` and
  `a member does not see the invoice actions they lack`. The projects names are the same with
  `project`. The Python HTTP cases use the same names in the snake form that FORGE-DEFAULTS-1
  pins.

### Done-when details

1. One step from the plan (COMMAND for TypeScript, PY for Python, GUIDE for the rules).
   - TypeScript output: `libs/<plural>/**` (module, controller, service, DTO, permissions,
     index, `package.json`, `project.json`, `tsconfig.json`), `apps/api/prisma/schema/<plural>.prisma`,
     one migration folder `apps/api/prisma/migrations/<UTC yyyyMMddHHmmss>_<plural>/migration.sql`,
     the shared schemas and types appended to `libs/shared/src/index.ts`, any missing UI
     component, and the wiring: the module in `app.module.ts`, `apps/api/package.json` and the
     references of `apps/api/tsconfig.json`, its importer in `pnpm-lock.yaml` (copied from the
     projects importer, so `pnpm install --frozen-lockfile` passes with no network), its `dist`
     in `scripts/test-build.mjs`, and the back-relation lines in `model Account`, `model
     Organisation` and, for a link, the linked model. The migration holds the table with each
     field's `sql` and `check`, the foreign keys, `[table]`'s `list_index`, each field's
     `filter_index`, `search_index` and `index` where they apply, the
     `updated_at_trigger`, and the soft delete trigger line
     `CREATE TRIGGER soft_delete_only BEFORE DELETE ON "<Model>" FOR EACH ROW EXECUTE FUNCTION soft_delete_only();`.
     Where Prisma's schema cannot say an index (a partial `WHERE`), the schema has the nearest
     `@@index` and the migration has the full statement. A link field adds `@app/<target>` to
     the new module's `package.json` and `tsconfig.json`, and the service checks the linked item
     with the target module's public service (`get(account, id)`), so no query reads another
     module's table.
   - Python output (PY): `apps/api/app/<plural>/` (`__init__.py`, `models.py`, `schema.py`,
     `service.py`, `routes.py`, `permissions.py`), one Alembic revision in
     `apps/api/migrations/versions/` named `<next number>_<plural>.py` whose `down_revision` is
     the current head (the one revision no other names as its down revision) with the same SQL
     from the kind table, the router in `main.py`, the model import in `migrations/env.py`, the
     `<plural> internals` contract in `apps/api/pyproject.toml`, and the zod schema copy and the
     `components['schemas']` types in the Python `libs/shared/src/index.ts`. The web files are
     the same as in a TypeScript app (WEB).
   - Test `tests/test_feature_command.py::test_1_a_plan_line_builds_the_feature_in_one_step`,
     parameters `typescript` and `python`: in a new repo made with `forge init --starter` (or
     `--starter python`), `forge task feature clients --one client --field name:text` then
     `forge task feature jobs --one job --field name:text --field description?:long-text
     --field status:status(planned|active|done) --field client?:link(clients)
     --field hoursBudget?:number --field budget?:money --field dueDate?:date
     --field contactEmail?:email --field billable:yes-no` (the SCREENS.md example, one field of
     each kind) each exit 0 and print the files they wrote; every printed file exists; the
     wiring files have the new lines next to the history lines; a second run of the same line
     refuses with the folder message and changes nothing (`git status --porcelain` is the same
     before and after). Adopted case: the same two lines in the adopted starter app write the
     same files with the same text, apart from the migration's timestamp or revision number.
   - GUIDE adds to the same test: the forge skill after `forge init` (new repo) and after
     upgrade and sync (the adopted-v1.2.2 client) holds the planner line, and the worker brief
     that `forge work` writes holds the first-step line.
2. Works like projects (WEB for the screens; COMMAND and PY serve the API).
   - API: the keyset list, with search and filters, in the shared zod list schema (Pydantic in
     Python), with the same `.strict()` refusal of unknown keys; detail; changes; create;
     replace; soft delete; `GET /api/v1/<plural>/export` through `sendCsv` (Python: the
     `app.core` CSV helper), declared before `:id`. Every query is scoped to
     `account.organisationId`; another organisation gets `404 <SINGULAR>_NOT_FOUND`.
   - Web: `apps/web/src/features/<plural>/**` with the list page, the detail page, the delete
     AlertDialog, the form Dialog with its discard AlertDialog, the hooks and their unit test,
     all as SCREENS.md shows them with the feature's names; the route in `app.tsx`, a sidebar
     item and a Ctrl+K item in `app-shell.tsx` (shown only with the view permission), and its
     title in the page title map. The form has one control per field from the kind table's
     `input`, in the line's order. A link field's filter, Combobox and cell read the linked
     feature's list hook in the web app; the API returns only the id.
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
     after a plan edits the mapping. With the default mapping, the member gets 403 on delete
     only, and the admin gets no 403 on any route.
   - The flow `a member does not see the <singular> actions they lack`: the member sees the
     list, the detail screen with Edit and the form, and no Delete button and no
     `Open the change history` link.
   - Test `tests/test_feature_access.py::test_3_each_feature_checks_its_permissions`,
     parameters `projects-typescript` and `projects-python` (ACCESS), `feature-typescript`
     (WEB) and `feature-python` (PY), live: the run's reports hold the endpoint case and the
     flow for projects, or for the item 1 jobs. Not live, in the same test: every route method
     in the projects controller and in the generated controller has exactly one
     `@RequirePermission` (Python: one `require_permission` dependency). Adopted case: not live;
     after upgrade and sync, the adopted starter app's permissions files and controllers are the
     same as a new app's.
4. Table, Change history rows, the kind table and passing tests (COMMAND pins the non-live
   checks; WEB and PY add the live runs).
   - The table has `organisationId` and the audit columns `createdByAccountId`,
     `modifiedByAccountId`, `deletedAtUtc` and `deletedByAccountId`, as projects; create,
     update and delete set them; delete sets `deletedAtUtc`, and the trigger refuses a hard
     delete. The service records each create, change and delete as the Change history rule
     above says.
   - The generated test files are renamed copies of the projects test files that PAGING, DETAIL
     and ACCESS add: `apps/api/test/<plural>.e2e-spec.ts`, `apps/web/e2e/<plural>.spec.ts`,
     `apps/web/src/features/<plural>/hooks/<plural>-hooks.test.tsx`, and in Python
     `apps/api/tests/test_<plural>.py`. Their values come from the kind table's `sample`,
     `changed` and `bad`.
   - Test `tests/test_feature_command.py::test_4_the_feature_keeps_history_and_its_tests_pass_at_once`,
     parameters `typescript` and `python`. Not live: the test reads the shipped `kinds.toml`
     and checks that the generated migration (and in Python the Alembic revision and
     `models.py`) has each field's `sql` or `sqlalchemy` value with the NOT NULL rule, its
     `check`, `[table]`'s `list_index` and `updated_at_trigger`, the filter, search and
     every-field indexes, the audit columns, the soft delete trigger, and no `CREATE TYPE`. Live:
     one cached run per starter (shared with test_2 and test_3, as `live_run` does) of the app's
     `node scripts/test.mjs` after the item 1 lines exits 0, and the reports hold every generated
     case name above, `records each job change in the change history` among them (it creates,
     changes and deletes a job as the admin, then reads `/api/v1/history` and the job's changes
     and finds the three summaries). The Python app's own test script runs `api-types` first.
     Adopted case: the non-live check in the adopted starter app.
5. Projects source (PAGING, DETAIL, ACCESS; each part changes both APIs and the web app).
   - PAGING: the keyset list query, `search` (optional, trimmed, at most 200) and `status`
     (optional `projectStatusSchema`) in `projectListQuerySchema` and the Python schema; the
     projects page with the search box, the status Select, column sort, Previous and Next and
     the total, all in the URL; rows with no Edit or Delete icons, each opening the detail
     screen (the name is the link, and the row can be clicked); the `New project` button; the
     form's submit button `Create project` (`Save changes` for an edit). The existing cases that
     read `page`, `limit` or `pagination` change to the keyset form (the list case, the bad
     query case and the list query docs case in `api.e2e-spec.ts`, and their Python twins). The
     projects cases move to their own files, with no name change: the API cases in
     `apps/api/test/projects.e2e-spec.ts`, the flows in `apps/web/e2e/projects.spec.ts`, and in
     Python `apps/api/tests/test_projects.py`. New cases: `pages projects with next and
     previous cursors`, `filters projects by search and filters`, and the flow
     `a reloaded projects list link keeps its search, filters and page`, which replaces
     `a reloaded or shared list link shows the same view` (update that name in
     `BROWSER_FLOWS` in `tests/test_starter_tree.py`). `create, edit, and delete a project`
     becomes `create, view, edit, and delete a project`, through the detail screen.
   - DETAIL: `ProjectDetailPage` at `/projects/:id` with the breadcrumb, the Details card, the
     Recent changes card, Edit (the form Dialog) and Delete (the AlertDialog), as SCREENS.md
     shows them; the history subject columns and `listForSubject`; the changes route; the
     Change history rows for projects; the Change history screen's subject name. New cases:
     `records each project change in the change history` and the flow
     `a project's detail screen shows its recent changes`.
   - ACCESS: the projects permissions, `permissions` on the account, `useCan`, and the hidden
     Delete and history link. A case that has a member delete a project, if one exists, now
     expects 403. The permission cases are item 3's.
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
  Done-when details, one `forge task feature` line per new thing, with every field from the
  brief's `## Things it keeps track of`, in the kinds the command takes, and the role mapping
  when it is not the default (admins all four, members all but delete); many-to-many links,
  files and computed fields go in the part as hand work. A link's target comes first, in the
  same line order. The part's Scope lists the folders the command writes.
- `src/forge/templates/brief.md`, Build simple: when your part's details give a
  `forge task feature` line, run it first, set the plan's role mapping in the feature's one
  permissions file, run the app's tests, and commit its files before any other change; then
  rename labels and add the hand work. Do not hand-build a feature the command can build. In an
  app with `libs/core/src/common/permissions.ts` (Python: `app/core/permissions.py`), guard
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
| PAGING | Projects list with keyset paging and URL filters | Keyset paging, search and the status filter in both APIs and the shared schemas; the projects list as SCREENS.md shows it, with Previous, Next and the total; rows that open the detail route; the button and form labels; the projects cases in their own files. | 2, 5 | `starter/libs/shared/src/index.ts`, `starter/libs/projects/src/**`, `starter/apps/web/src/features/projects/**`, `starter/apps/web/src/app.tsx`, `starter/apps/api/test/api.e2e-spec.ts`, `starter/apps/api/test/projects.e2e-spec.ts` (new), `starter/apps/web/e2e/starter-shell.spec.ts`, `starter/apps/web/e2e/projects.spec.ts` (new), `starter-python/apps/api/app/projects/**`, `starter-python/apps/api/tests/test_api.py`, `starter-python/apps/api/tests/test_projects.py` (new), `starter-python/libs/shared/src/index.ts`, `starter-python/libs/shared/openapi.json` and `starter-python/libs/shared/src/api-types.ts` (regenerated), `tests/test_starter_tree.py` and `tests/test_python_starter.py` (case names only), `.github/workflows/starter-smoke.yml` | `tests/test_feature_projects.py` (`test_5`, `typescript` and `python`, new) | | yes | |
| DETAIL | Projects detail screen and change history | The detail screen with its Details and Recent changes cards, Edit and the Delete AlertDialog; the Card component; the history subject columns, migrations and `listForSubject`; the changes route; a Change history row for each projects create, change and delete; the subject name on the Change history screen; in both APIs. | 4, 5 | `starter/apps/web/src/components/ui/card.tsx` (new), `starter/apps/web/src/features/projects/**`, `starter/apps/web/src/features/history/**`, `starter/apps/web/src/app.tsx`, `starter/libs/history/**`, `starter/apps/api/prisma/schema/history.prisma`, `starter/apps/api/prisma/migrations/<new>_history_subjects/` (new), `starter/libs/projects/**`, `starter/apps/api/package.json` and `starter/pnpm-lock.yaml` (`@app/history` for projects), `starter/libs/shared/src/index.ts`, `starter/apps/api/test/projects.e2e-spec.ts`, `starter/apps/web/e2e/projects.spec.ts`, `starter-python/apps/api/app/history/**`, `starter-python/apps/api/app/projects/**`, `starter-python/apps/api/migrations/versions/<next>_history_subjects.py` (new), `starter-python/apps/api/tests/test_projects.py`, `starter-python/libs/shared/**` (shared copy and regenerated types) | `tests/test_feature_projects.py` (`test_5`, the DETAIL case names) | PAGING | yes | |
| ACCESS | Projects permissions | The permissions helpers and guard in both APIs, `permissions` on the account, `useCan` in the web app, the projects permissions file and one check on each projects route, and the hidden Delete and history link. | 3, 5 | `starter/libs/core/src/common/permissions.ts` (new), `starter/libs/core/src/index.ts`, `starter/libs/auth/**` (account `permissions` only), `starter/libs/shared/src/index.ts` (`Account` only), `starter/libs/projects/**`, `starter/apps/web/src/lib/permissions.ts` (new), `starter/apps/web/src/features/projects/**`, `starter/apps/web/src/components/app-shell.tsx`, `starter/apps/api/test/projects.e2e-spec.ts`, `starter/apps/web/e2e/projects.spec.ts`, `starter-python/apps/api/app/core/permissions.py` (new), `starter-python/apps/api/app/core/__init__.py`, `starter-python/apps/api/app/auth/**` (account `permissions` only), `starter-python/apps/api/app/projects/**`, `starter-python/apps/api/tests/test_projects.py`, `starter-python/libs/shared/**` (shared copy and regenerated types) | `tests/test_feature_access.py` (`test_3`, `projects-typescript` and `projects-python`, new) | DETAIL | yes | |
| COMMAND | The feature command and the TypeScript API copy | `forge task feature` with its line, refusals and starter check, the field-kind table with placeholder database values, the marks in the TypeScript API projects files, and the TypeScript API, permissions, Prisma, migration, shared schema and wiring copy. | 1, 4, 6 | `src/forge/cli.py` (one route), `src/forge/feature.py` (new), `src/forge/templates/feature/kinds.toml` (new), `starter/libs/projects/src/**` (marks only), `starter/libs/shared/src/index.ts` (marks only), `starter/apps/api/test/projects.e2e-spec.ts` (marks only), `.github/workflows/starter-smoke.yml` | `tests/test_feature_command.py` (`test_1`, `test_4` not-live checks, `test_6`, `typescript`, new) | ACCESS, FORGE-DATABASE-1/PG18, FORGE-DATABASE-1/IDS, FORGE-DATABASE-1/IDSPY | no | |
| WEB | The feature's screens | The marks in the web projects files, the Textarea, Checkbox and Popover components, and the web copy: list, detail, delete dialog, form with one control per field, hooks and their test, the route, sidebar and Ctrl+K items; the live TypeScript run with the generated cases. | 2, 3, 4 | `src/forge/feature.py` (the web copy only), `src/forge/templates/feature/kinds.toml` (the `input`, `cell`, `filter_options` and `column` keys only), `starter/apps/web/src/components/ui/textarea.tsx`, `checkbox.tsx` and `popover.tsx` (new), `starter/apps/web/src/features/projects/**` and `starter/apps/web/e2e/projects.spec.ts` (marks only) | `tests/test_feature_command.py` (`test_2`, `test_4` live, `typescript`); `tests/test_feature_access.py` (`test_3`, `feature-typescript`) | COMMAND | yes | |
| PY | The Python API copy | The marks in the Python projects files, the Python starter check, and the Python API, permissions, Alembic revision, shared copy and wiring; the Python parameters of the feature tests, `test_2` and `test_6` included. | 1, 3, 4 | `src/forge/feature.py` (the Python copy only), `src/forge/templates/feature/kinds.toml` (`sqlalchemy` and `pydantic` keys only), `starter-python/apps/api/app/projects/**` and `starter-python/apps/api/tests/test_projects.py` (marks only), `starter-python/libs/shared/src/index.ts` (marks only) | `tests/test_feature_command.py` (`test_1`, `test_2`, `test_4`, `test_6`, `python`); `tests/test_feature_access.py` (`test_3`, `feature-python`) | WEB | no | |
| GUIDE | Planner and worker rules | The planner rule in the skill, the first-step and permission rules in the worker brief, and the guide paragraph, on new and existing repos. | 1 | `src/forge/templates/skill.md`, `src/forge/templates/brief.md`, `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `docs/guide.md` | `tests/test_feature_command.py` (`test_1`: the skill and brief checks on a new and an adopted repo) | COMMAND | no | |

New moving parts: none (the permissions list in core is a plain in-memory map that each module
fills at start, for item 3; no service, store or cache)

## Notes

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
  with recent changes, the permissions and Change history rows, the marks in the projects
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
  story owns; no cache server; a Change history row for each create, change and delete, projects
  first; four permissions per feature in code (admins all four, members all but delete), one
  check on every endpoint and screen, a test per endpoint, one place per feature to change the
  mapping, projects first; keyset paging with Previous, Next and an approximate total, the
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
  `kinds.toml` and the money and number keys that follow its money helper. Its pinned
  `list_index` and filter indexes order by `{created}`; this story's default sort is Updated,
  newest first (SCREENS.md), so those values need `{updated}`. This story adds the `{updated}`
  placeholder for that.
- **No cache.** No cache server and no cache layer in the generated code; list queries use the
  indexes above.
- No client repo is named anywhere in this story's code, tests, texts or commits.
