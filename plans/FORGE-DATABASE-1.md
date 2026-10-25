# Database rules for every client app

9 parts · Risks: none one-way · New moving parts: three Postgres extensions and one trigger function in the starters

## What changes for you

- Each client repo gets a database skill for both agents. It tells the agent which column type,
  key, constraint and index to use for each kind of data, how lists page and search, how to build
  dashboards, change history and job tables, and when to use each Postgres extension.
- The agent can turn on only an extension that AWS RDS, Google Cloud SQL, Azure and Neon all
  offer. Any other extension needs your OK for that client, and the app's constitution records it.
- The app starts with no cache server. The tables and their indexes carry the speed.
- Both starters move from Postgres 17 to Postgres 18. pg_stat_statements, pg_trgm and btree_gin
  are on from the first day.
- In new apps, the database gives each new row a time-ordered id and sets its last-changed time.
- The starters' own tables follow the new rules too. Status lists become text with a named check,
  names become text, a sign-in email is unique without regard to upper and lower case, and all
  times keep their time zone.
- In new apps, money is an exact decimal with four decimal places and its own currency code
  column, not whole cents. The shared money helper shows each currency with its own decimal
  places.
- The feature step takes each column type, constraint and index from one field-kind table, so
  two builders make the same choice.
- A review holds a new table, column, index or extension that breaks the skill.
- Existing apps get the skill and the review rule on upgrade. The rules apply only to their new
  tables. Forge does not change their current tables, their Postgres version or their money
  columns.

Design: none (no new screen or control; a money field keeps the feature step's one amount input with the currency code shown in front, and the app's one default currency fills the currency column)

## Why

Builders choose column types, keys, indexes and extensions by hand for each feature, so the
choices differ from one builder to the next. The starters run Postgres 17.6 and use random ids.
The database convention page stores money as whole cents and covers only Prisma, but the Python
starter uses SQLAlchemy. On 25 October 2026 the owner set the database rules, the extension
list, Postgres 18 with time-ordered ids, and money as an exact decimal with a currency code.

## Done when

1. **A new client repo gets the database skill for both agents, and an existing repo gets it on upgrade with no change to its tables, its Postgres version or its money columns.**
2. **Both starters run Postgres 18 with pg_stat_statements, pg_trgm and btree_gin on.**
3. **In both starters, the database gives each new row a time-ordered id and sets its last-changed time on each update, and the starter's own tables follow the skill: status as text with a named check, names as text, a sign-in email unique on its lower case, and times as timestamptz.**
4. **Money is stored as an exact decimal with four decimal places and a currency code column, and the shared money helper shows each currency with its own decimal places.**
5. **The feature step fills each column type, constraint and index from the one field-kind table, and the table's values match the skill.**
6. **A review holds a new table, column, index or extension that breaks the skill, in a new and in an existing app. An extension that the four hosts do not all offer passes only with the owner's OK in the app's constitution.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none one-way. Each part reverts with its pull request. The new migrations change only the
starters, which a new app copies at set-up; no existing app gets them.

Trade-off: on some hosts the app's database user cannot turn on pg_stat_statements. Then the
first deploy of a new app stops with Postgres's own error, and Postgres undoes that migration.
The fix is to turn the extension on once as the host's admin user, mark the failed migration as
rolled back (`prisma migrate resolve --rolled-back 20261026000000_extensions`; the Python
starter needs no step), then deploy again. The skill has the same steps.

Trade-off: an existing app whose constitution says money is stored in cents keeps cents in its
new tables too, because the constitution wins over the skill.

Trade-off: the projects list keeps its numbered pages in this story. The move to next and
previous links belongs to the feature step's story.

Trade-off: an amount and its currency code are two columns for each money field. A table with
three amounts has three currency columns.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new test file starts with `STORY = "FORGE-DATABASE-1"`. Each test runs the forge command, or
reads the files that `forge init` and `forge sync` write; no test imports forge. Live cases run
only under the existing `LIVE` switch, through `live_run` (tests/test_starter_tree.py) and
`live_python_starter` (tests/test_python_starter.py), as tests/test_defaults_soft_delete.py does.
CI runs them: PG18 adds `tests/test_database_*.py -k "not python"` to the `starter-smoke` job and
`tests/test_database_*.py -k python` to the `python-starter-smoke` job in
`.github/workflows/starter-smoke.yml`, so every later part's live cases run there too. Each
parameter of the Python starter has `python` in its id; no other id does.
"Adopted case" means the `tests/fixtures/adopted-v1.2.2/client` repo moved to this release, as
`test_4` in tests/test_defaults_soft_delete.py sets it up.

All paths under `starter/` mean `src/forge/templates/starter/`, and `starter-python/` means
`src/forge/templates/starter-python/`.

No extra guards for unlikely races or security edge cases (owner rule). No cache server and no
cache layer anywhere in this story.

### Shared names

- **The skill (pinned by SKILL).** Source `src/forge/templates/skills/database/SKILL.md`. Sync
  writes it to `.claude/skills/database/SKILL.md` and `.codex/skills/database/SKILL.md` in every
  repo, from `app_baseline.ships` (two more entries beside app-baseline; no pyproject change,
  because `src/forge/templates` is package data). Front matter `name: database`, description:
  `Database rules for Forge client apps on Postgres. Use before adding or changing a table,
  column, index, constraint, migration, extension, list query, report or job table, in Prisma or
  SQLAlchemy.` Review, brief and skill.md name the path `.codex/skills/database/SKILL.md`.
- **The extension OK line (pinned by SKILL).** In the app's `docs/product/CONSTITUTION.md`,
  under Architecture choices: `- Postgres extension <name>: the owner allows it on <date> (<why>)`.
  The skill and skill.md tell the agent to ask the owner and write this line; the review rule
  (REVIEW) accepts an extension off the list only when this line names it.
- **The finding title (pinned by REVIEW).** `Database: <the table or column>`. `score.normalise`
  floors it as it floors `Module tables: ` (gain at least 4, work at most 2, the suffix
  `(floor: database)`).
- **The field-kind table.** `src/forge/templates/feature/kinds.toml`, the file FORGE-FEATURE-1's
  COMMAND part creates. FEATURE-1 owns its non-database keys and `feature.py`; this story owns
  the database values (`prisma`, `sql`, `sqlalchemy`, `check`, `filter_index`, `search_index`),
  the new keys below, and every value of the `money` and `number` kinds. A number can hold
  decimals and negative values (hours, a temperature), so it has no sign check. KINDS replaces the
  placeholder values and deletes each `# placeholder: the database rules story sets this value`
  comment. Format:
  - One `[<kind>]` table for each of the nine kinds: `text`, `long-text`, `number`, `money`,
    `date`, `yes-no`, `email`, `status`, `link`. One more table, `[table]`, holds what the
    command writes once for each new table; it is not a kind, and `table` is an unknown kind on
    the command line.
  - `sql`, `prisma` and `sqlalchemy` hold the type and its default only. The command writes
    `NOT NULL` (SQL), no `?` (Prisma) and `nullable=False` (SQLAlchemy) unless the field ends in
    `?`. A `yes-no` field is NOT NULL even with `?`.
  - `check`, `filter_index`, `search_index` and the new `index` hold whole SQL statements or
    constraint clauses, or `""`. `index` is written for every field of its kind, filter or not.
  - Placeholders the command fills in each starter's naming (TypeScript: `Invoice`, `dueDate`,
    `organisationId`, `updatedAtUtc`, `deletedAtUtc`; Python: `invoice`, `due_date`,
    `organisation_id`, `updated_at_utc`, `deleted_at_utc`): `{table}`, `{column}`, `{org}`,
    `{updated}` (the list's default sort is last change, newest first, as FORGE-FEATURE-1 sets
    it), `{deleted}`, `{target}` (the linked table), `{options}` (`'draft', 'sent'`),
    `{first}` (the first option) and `{currency}` (the money field's currency column:
    `totalCurrency`, `total_currency`). SQL names are always in double quotes. `{enum}` goes.
  - `money` also has `currency_sql`, `currency_prisma` and `currency_sqlalchemy`: the command
    adds a NOT NULL `{currency}` column of that type after each money column (nullable when the
    money field ends in `?`).
  - `[table]` has `list_index` and `updated_at_trigger`.
- **The values (pinned here; SKILL writes them in the skill's column table, KINDS in
  kinds.toml).**

  | Kind | sql | prisma | sqlalchemy | check | filter_index / search_index / index |
  |---|---|---|---|---|---|
  | text | `text` | `String` | `Text` | `CONSTRAINT "{table}_{column}_length" CHECK (char_length("{column}") BETWEEN 1 AND 200)` | search: `CREATE INDEX "idx_{table}_{column}_search" ON "{table}" USING gin ("{org}", "{column}" gin_trgm_ops) WHERE "{deleted}" IS NULL;` |
  | long-text | `text` | `String` | `Text` | `CONSTRAINT "{table}_{column}_length" CHECK (char_length("{column}") <= 10000)` | none |
  | number | `numeric(19,4)` | `Decimal @db.Decimal(19, 4)` | `Numeric(19, 4)` | none (a plan adds a check for a field when the client needs one) | none |
  | money | `numeric(19,4)`; currency `text` | `Decimal @db.Decimal(19, 4)`; currency `String` | `Numeric(19, 4)`; currency `Text` | `CONSTRAINT "{table}_{currency}_code" CHECK ("{currency}" ~ '^[A-Z]{3}$')` | none |
  | date | `date` | `DateTime @db.Date` | `Date` | none | none |
  | yes-no | `boolean DEFAULT false` | `Boolean @default(false)` | `Boolean, server_default=false()` | none | filter: `CREATE INDEX "idx_{table}_{column}" ON "{table}" ("{org}", "{column}", "{updated}" DESC, "id" DESC) WHERE "{deleted}" IS NULL;` |
  | email | `text` | `String` | `Text` | `CONSTRAINT "{table}_{column}_format" CHECK (char_length("{column}") <= 254 AND "{column}" ~ '^[^@[:space:]]+@[^@[:space:]]+$')` | search: as text |
  | status | `text DEFAULT '{first}'` | `String @default("{first}")` | `Text, server_default="{first}"` | `CONSTRAINT "{table}_{column}_allowed" CHECK ("{column}" IN ({options}))` | filter: as yes-no |
  | link | `uuid` | `String @db.Uuid` | `Uuid` | none | filter: as yes-no; index: `CREATE INDEX "idx_{table}_{column}_fk" ON "{table}" ("{column}");` |

  `[table]`: `list_index = 'CREATE INDEX "idx_{table}_list" ON "{table}" ("{org}", "{updated}" DESC, "id" DESC) WHERE "{deleted}" IS NULL;'`
  and `updated_at_trigger = 'CREATE TRIGGER "{table}_set_updated_at" BEFORE UPDATE ON "{table}" FOR EACH ROW EXECUTE FUNCTION set_updated_at();'`.
  The link foreign key stays `ON DELETE RESTRICT`, as FEATURE-1 writes it. The email kind is a
  contact field, so it is not unique; the skill's identity-email rule is for sign-in emails.
  The Prisma schema states each index in full, partial `WHERE` included: the TypeScript starter's
  `base.prisma` turns on Prisma's `partialIndexes` preview feature (in Prisma since 7.4; the starters pin
  7.10.1), and each `@@index` carries its `where` clause, its `type: Gin` and its `ops`. CHECK
  constraints and triggers live only in the migration SQL, because Prisma neither states nor
  compares them. So the drift check in item 5 (`prisma migrate diff` from the migrations to the
  schema) prints an empty migration. IDS adds the preview line.
- **The trigger function (pinned by IDS and IDSPY).** `set_updated_at()`, one per starter,
  created in the ids migration: `BEGIN NEW."updatedAtUtc" = now(); RETURN NEW; END` in the
  TypeScript starter and `NEW.updated_at_utc` in the Python starter. Each starter table with an
  updated-at column gets the `<table>_set_updated_at` trigger.
- **The money helper (pinned by MONEY).** `formatMoney(amount: string, currency: string): string`
  in `libs/shared/src/format.ts` of both starters (byte-identical files). `amount` is the decimal
  string the API returns for a `numeric(19,4)` column: Prisma `Decimal` and Python `Decimal` both
  serialize to a JSON string, never a JS number. The same file exports
  `DEFAULT_CURRENCY = 'USD'` (and `index.ts` exports it), the app's one default currency. The
  Python API has the same `DEFAULT_CURRENCY = "USD"` in `app/core/config.py`, and MONEY's test
  checks that the two are equal. An app that bills in another currency changes both.

### The skill's content

One page, under about 220 lines, tables first, plain English. It opens with three lines: the
rules apply to the tables a change adds, with their columns, constraints, indexes and triggers;
a change to an existing table follows that table's own style, and existing tables are never
migrated to these rules unless a story asks; where the app's constitution differs, it wins. Sections, in this order:

1. **Columns by kind of data.** A table: Kind of data | Postgres | Prisma | SQLAlchemy | Rule.
   The nine kinds' rows use the values above, word for word, so KINDS's test can match them.
   Extra rows: id (`uuid DEFAULT uuidv7()`; Prisma `String @id @default(dbgenerated("uuidv7()")) @db.Uuid`;
   SQLAlchemy `mapped_column(Uuid, primary_key=True, server_default=text("uuidv7()"))`; in Python
   code that needs the id first, `uuid.uuid7()`; on Postgres 17 or older, where `uuidv7()` does
   not exist, the app makes the id: Prisma `@default(uuid(7))`, Python `default=uuid7`, and no
   database default); count (`integer`, `bigint` when it can pass two
   billion); instant (`timestamptz`; Prisma `DateTime @db.Timestamptz(3)`; SQLAlchemy
   `DateTime(timezone=True)`); blob read whole (`jsonb` with a `jsonb_typeof` CHECK); time range
   (`tstzrange`, `'[)'` bounds); location (`numeric(9,6)` lat and lng for display and rough
   nearby, PostGIS `geography` for radius and shapes); embedding (see Extensions). Rules: `text`,
   never `varchar(n)`, with a named length CHECK; never `float` or `double precision` for business
   values; status is `text` with a named CHECK, never a Postgres enum; money and decimals travel
   as decimal strings in JSON.
2. **Keys and constraints.** NOT NULL unless the field is really optional. Every constraint has a
   name, `<table>_<column>_<rule>`. Foreign keys are `ON DELETE RESTRICT`; `CASCADE` only for
   detail rows the parent owns (order lines); `SET NULL` only for an optional reference. Index
   every foreign key. A sign-in email is stored in lower case, with the named check
   `<table>_email_lower CHECK (email = lower(email))`, and is unique (with the organisation
   column in front where the table has one), so it is unique on `lower(email)`; no citext. `updated_at` comes from the shared
   `set_updated_at()` trigger. Every tenant table has the organisation column, and the one data
   layer scopes each query to the caller's organisation, with one refusal test per endpoint.
   Row-level security is not a default; a regulated client gets it as its own story.
3. **Indexes for lists.** The list index is `(organisation_id, <filter columns>, <sort column>
   DESC, id DESC) WHERE deleted_at IS NULL`. The search box is `ILIKE '%' || $term || '%'` with a
   pg_trgm GIN index, with the organisation column in front through btree_gin. Word search in long
   text is a generated `tsvector` column (`STORED`) with a GIN index, queried with
   `websearch_to_tsquery`. Add no index that no query uses; check a slow query with
   `EXPLAIN (ANALYZE, BUFFERS)`.
4. **List paging.** Keyset paging by default: `WHERE (sort, id) < ($lastSort, $lastId) ORDER BY
   sort DESC, id DESC LIMIT <n + 1>`, next and previous links, and an approximate total (a count
   capped at 1,000, shown as "1,000+"). Numbered pages only on small admin screens. Existing lists
   keep their paging.
5. **Dashboards and reports.** First a live query on indexed columns. When pg_stat_statements
   shows it over about 200 ms, use a materialized view (with a unique index, refreshed
   `CONCURRENTLY` by pg_cron or a job) or a summary table that app code updates in the same
   transaction. No pg_ivm.
6. **Change history.** App code writes the history row in the same transaction (in the starters,
   `HistoryService.record`); no audit triggers. Partition the history table by month only past
   about 50 to 100 million rows or when old months must be dropped.
7. **Job tables.** A jobs table read with `SELECT ... FOR UPDATE SKIP LOCKED`, or pg-boss in a
   Node app. pg_cron only for scheduled SQL. No separate queue server at the start.
8. **jsonb.** Real columns for anything that is filtered, joined, sorted or constrained. jsonb only
   for a blob read whole; a `jsonb_path_ops` GIN index when it is filtered by containment; a
   generated column for one hot key; a `CHECK (jsonb_typeof(...) = 'object')`. No hstore.
9. **Extensions.** A table: Need | Use | Best practice. Rows: similar text and typos (pg_trgm
   GIN, btree_gin for the organisation column in front); ranked word search (built-in
   `tsvector`); accents (unaccent through an `IMMUTABLE` wrapper function, so an index can use
   it); trees and graphs (adjacency list and a recursive CTE with `CYCLE` for org charts and
   permissions; ltree with a GiST index for read-heavy trees; a closure table when items move
   often); location (PostGIS `geography`, GiST index, `ST_DWithin`); bookings that must not
   overlap (`tstzrange` with `EXCLUDE USING gist` through btree_gist, or Postgres 18
   `WITHOUT OVERLAPS`); embeddings (pgvector in a separate table: organisation_id, source_type,
   source_id, model, model_version, content_hash, embedding `halfvec`; an exact scan with the
   organisation filter under about 100,000 vectors for each tenant, then HNSW with m 16 and
   ef_construction 64 on `halfvec` and `hnsw.iterative_scan = relaxed_order`; the operator class
   that matches the distance; re-embed by the model column; a separate vector database only well
   past 10 million vectors); large tables (partitioning only past about 50 to 100 million rows or
   for retention drops, RANGE by time or HASH by organisation, with pg_partman); scheduled SQL
   (pg_cron); time series (a partitioned table with a BRIN index); slow queries
   (pg_stat_statements, on from day one; auto_explain where the host offers it, with
   `log_min_duration` about 500 ms, `log_analyze` on, `log_timing` off and a sample rate about
   0.1). The allowed list: pgvector, ltree, pg_trgm, unaccent, fuzzystrmatch, citext, PostGIS,
   btree_gist, btree_gin, pg_partman, pg_cron, pg_stat_statements, pgcrypto. Every other
   extension (for example AGE, TimescaleDB, pgmq, pg_search) needs the owner's OK for that
   client and the constitution line under Shared names. Avoid pg_ivm. pg_uuidv7 is not needed:
   Postgres 18 has `uuidv7()`. Turn an extension on in its own migration
   (`CREATE EXTENSION IF NOT EXISTS <name>;`) in the first story that needs it. When a deploy
   stops because the app's user cannot turn an extension on: turn it on once as the host's admin
   user, run `prisma migrate resolve --rolled-back <migration>` (a Prisma app; Alembic needs no
   step), then deploy again.
10. **Speed without a cache.** No cache server at the start. Add one only for a slow page that
    pg_stat_statements measures and indexes cannot fix, for sessions or rate limits across
    instances, or for a hot aggregate read again and again.
11. **Prisma and SQLAlchemy.** A table: Thing | Prisma | SQLAlchemy and Alembic. Rows: uuidv7
    default; timestamptz; CHECK (raw SQL in the migration: `prisma migrate dev --create-only`,
    then edit the SQL | `CheckConstraint(..., name=...)` in the model, and `op.create_check_constraint`
    because autogenerate misses CHECK changes); partial index (`@@index([...], where: ...)` with the
    `partialIndexes` preview feature on | `Index(..., postgresql_where=...)`); trigram GIN (`@@index([...], type: Gin)` with
    `ops: raw("gin_trgm_ops")` | `postgresql_using="gin"`, `postgresql_ops`); generated tsvector
    (`Unsupported("tsvector")` plus raw SQL | `Computed(..., persisted=True)` with `TSVECTOR`);
    trigger, function, extension and exclusion constraint (raw SQL in both; `ExcludeConstraint` in
    SQLAlchemy); the drift check after a raw-SQL migration (`prisma migrate diff
    --from-migrations apps/api/prisma/migrations --to-schema apps/api/prisma/schema --script`
    must print an empty migration | `alembic check` must pass).

### Done-when details

1. Skill on new and existing repos (SKILL).
   - `app_baseline.ships` returns the two skill paths with the source text. The brief gets one
     paragraph next to the module and organisations paragraphs: `In an app with a database,
     follow the database skill (.codex/skills/database/SKILL.md) for each table, column, index,
     constraint, migration or extension that you add. Existing tables stay as they are. A review
     holds new schema that breaks the skill.` skill.md's constitution guide gets the extension
     OK rule (ask the owner, then write the line under Shared names), and its built-in money line
     becomes `... and money is stored as an exact decimal with its currency code; the helpers in
     @app/shared format them.` conventions/database.md: the example model uses the uuidv7 id,
     `@db.Timestamptz(3)`, `total Decimal @db.Decimal(19, 4)` with `totalCurrency String`, and a
     text status; the money line and the search line point to the skill; one line says the
     skill has the rules and this page has the Prisma how-to. conventions/python.md: the same in
     its Database section (`server_default=text("uuidv7()")`, `Numeric(19, 4)` with a
     `*_currency` column, no `*_in_cents`).
   - Test `tests/test_database_skill.py::test_1_new_and_existing_repos_get_the_database_skill`
     (platform mark): (a) a new client from `forge init` has both skill files, byte for byte the
     source, with each of the 11 section headings, the allowed list and the id line for Postgres
     17 or older; (b) adopted case: the
     adopted client with `apps/api/prisma/schema/shop.prisma` holding `totalInCents Int` and a
     `compose.test.yml` on `postgres:16-alpine`, after `forge sync`, has both skill files, and its
     `apps/` tree and `compose.test.yml` are byte for byte the same as before.
   - Update `tests/test_built_in_defaults_guide.py` (the money line) and
     `tests/test_python_guide.py` (`_in_cents` becomes `_currency`).
2. Postgres 18 and the three extensions (PG18).
   - Both `compose.test.yml` files: the `database` service uses the latest `postgres:18.x-alpine`
     tag at build time, pinned to that minor version; `command: ["postgres", "-c",
     "shared_preload_libraries=pg_stat_statements"]`; and `tmpfs: /var/lib/postgresql`, because the
     Postgres 18 image keeps its data under `/var/lib/postgresql/18/docker`, not `.../data`.
   - New migrations `starter/apps/api/prisma/migrations/20261026000000_extensions/migration.sql`
     and `starter-python/apps/api/migrations/versions/0006_extensions.py` (down revision
     `0005_history`): `CREATE EXTENSION IF NOT EXISTS` for pg_stat_statements, pg_trgm and
     btree_gin. The Alembic downgrade drops them.
   - Live cases: `starter/apps/api/test/database.e2e-spec.ts` (new) `the database runs Postgres 18
     with the day-one extensions` and `starter-python/apps/api/tests/test_database.py` (new)
     `test_the_database_runs_postgres_18_with_the_day_one_extensions`, each through the existing
     `psql` helper: `SHOW server_version_num` is at least 180000, `pg_extension` lists the three,
     and `SELECT count(*) FROM pg_stat_statements` succeeds.
   - Test `tests/test_database_starters.py::test_2_starters_run_postgres_18_with_three_extensions`
     (platform mark), parameters `react` and `python`: `forge init --starter <kind>` copies the
     compose file and the migration byte for byte; under `LIVE`, the live run shows the case
     above. The existing-repo side of this item is test_1 (b).
3. Time-ordered ids and the last-changed trigger (IDS for TypeScript, IDSPY for Python), and the
   starter tables' columns (COLUMNS for TypeScript, COLUMNSPY for Python).
   - IDS: every Prisma id becomes `@default(dbgenerated("uuidv7()"))` (Account included), and
     migration
     `starter/apps/api/prisma/migrations/20261026000100_ids_and_updated_at/migration.sql` sets
     each id default, creates `set_updated_at()` and the triggers. `auth.service.ts` stops calling `randomUUID()` for the
     account id: it reads `SELECT uuidv7()::text AS id` in the sign-up transaction, because the
     account references itself. Prisma's `@updatedAt` stays; the trigger sets the same column.
   - IDSPY: each model id gets `server_default=text("uuidv7()")`; each service that sets
     `id=uuid4()` uses the standard library's `uuid7()` (Python 3.14); revision
     `0007_ids_and_updated_at.py` (down revision `0006_extensions`) sets the defaults and creates
     the function and triggers. The models' `onupdate=func.now()` stays.
   - COLUMNS (TypeScript), migration
     `starter/apps/api/prisma/migrations/20261026000200_columns/migration.sql`, all in one
     transaction (a new app's tables are empty at set-up, but the `USING` clauses keep any rows):
     every `DateTime` becomes `@db.Timestamptz(3)`, changed with `USING "<column>" AT TIME ZONE
     'UTC'`; the `ProjectStatus` and `MembershipRole` enums go, and `status` and `role` become
     `String` (`text`) with their defaults and the named checks `Project_status_allowed` and
     `Membership_role_allowed` (`CHECK (... IN (...))`), then `DROP TYPE`; `Project.name` becomes
     `text` with `Project_name_length CHECK (char_length("name") BETWEEN 1 AND 120)`, and every
     other `varchar` becomes `text`; `Account.email` and `Invite.email` keep their unique
     keys (`@unique` and `@@unique([organisationId, email])`) and get the named checks
     `Account_email_lower` and `Invite_email_lower` (`CHECK ("email" = lower("email"))`), so each
     is unique on `lower(email)`. The shared zod schemas already lower-case emails, and the
     `findUnique({ where: { email } })` and `organisationId_email` upsert calls keep working with
     no change. The status and role lists stay the same, so the HTTP contract does not change;
     only code that imports the Prisma enum types changes to the shared string types.
   - COLUMNSPY (Python), revision `0008_columns.py` (down revision `0007_ids_and_updated_at`):
     the `project_status` and `membership_role` native enums become `Text` with the named checks
     `project_status_allowed` and `membership_role_allowed` (`CheckConstraint` in the models),
     then `DROP TYPE`; every `String(n)` becomes `Text`, with `project_name_length` (1 to 120) on
     `project.name`; `account.email` and the invite's `email` keep their unique
     constraints and get the named checks `account_email_lower` and `invite_email_lower`
     (`CheckConstraint("email = lower(email)", name=...)` in the models), so each is unique on
     `lower(email)`. The Pydantic schemas already lower-case emails, and the invite's
     `on_conflict_do_update(index_elements=["organisation_id", "email"])` keeps working. The Python times are
     already timestamptz. The Python `ProjectStatus` and `Role` types stay, so the API does not
     change.
   - Live cases (in the files from item 2): `the starter tables follow the database skill` and
     `test_the_starter_tables_follow_the_database_skill`: through `psql`, no column of the app's
     tables (all but `_prisma_migrations` and `alembic_version`) has the type `character
     varying`, `USER-DEFINED` or `timestamp without time zone`; an `UPDATE` that sets a project's
     status to `paused` fails and names `Project_status_allowed` (or `project_status_allowed`);
     and after one sign-up through the API, a `psql` `UPDATE` that sets the account's email to
     capital letters fails and names the lower-case email check.
   - Live cases (in the files from item 2): `a new row gets a time-ordered id and an update sets
     its last-changed time` and `test_a_new_row_gets_a_time_ordered_id_and_an_update_sets_its_last_changed_time`:
     after sign-up and one project through the API, `SELECT count(*)` of rows in each starter
     table with `uuid_extract_version(id) <> 7` is 0, and a `psql` `UPDATE` of the project's name
     that does not set the updated-at column moves it forward.
   - Test `tests/test_database_starters.py::test_3_new_rows_get_time_ordered_ids_and_updated_times`
     (platform mark), parameters `react` and `python`: init copies the migration byte for byte,
     the schema or model files have no `@default(uuid())` and no `uuid4()`, and under `LIVE` the
     live run shows the case. The `prisma migrate diff` drift check from item 5 also runs on the
     plain starter here and prints an empty migration.
   - Test `tests/test_database_starters.py::test_3_starter_tables_follow_the_skill` (platform
     mark), parameters `react` and `python`: init copies the columns migration byte for byte, the
     schema or model files have no `enum`, `VarChar`, `String(` or `native_enum`, and under `LIVE`
     the live run shows the columns case and the drift check (`prisma migrate diff ... --script`
     empty; `alembic check` passes) runs after the columns migration. The existing-repo side of
     item 3 is test_1 (b): an adopted app's schema and migrations stay byte for byte the same.
4. Money (MONEY; the stored columns are KINDS's, item 5).
   - `formatMoney(amount, currency)`: refuses with a `RangeError` an amount that is not a decimal
     string (`/^-?\d+(\.\d+)?$/`) or a currency that is not three capital letters. It formats the
     string itself (never `Number(amount)`) with `Intl.NumberFormat('en-US')` and the currency's
     own fraction digits, from `Intl.NumberFormat('en-US', { style: 'currency', currency })
     .resolvedOptions().maximumFractionDigits`, as `<code> <number>` with a plain space. The
     ponytail comment about two decimals goes. Both starters' `format.ts` stay byte-identical.
   - `starter/apps/web/src/lib/format.test.ts`: `formatMoney('1234.5600', 'USD')` is
     `USD 1,234.56`; `formatMoney('-0.0500', 'USD')` is `USD -0.05`; `formatMoney('1234', 'JPY')`
     is `JPY 1,234`; `formatMoney('12345678901234.5650', 'USD')` is `USD 12,345,678,901,234.57`
     (no float loss); `('1.5', 'usd')` and `('1,5', 'USD')` throw. `starter/README.md`: money is
     stored as `numeric(19,4)` with a currency code column.
   - Test `tests/test_database_money.py::test_4_money_is_an_exact_decimal_with_its_currency`
     (platform mark), parameters `react` and `python`: init copies `format.ts` and (TypeScript)
     `format.test.ts` byte for byte; under `LIVE`, the live run shows the passing format helper
     cases. Adopted case: the adopted client's own `libs/shared/src/format.ts` (a cents helper)
     is the same after `forge sync`.
5. The field-kind table (KINDS).
   - kinds.toml holds the values above. `feature.py` changes only where the new values need it:
     the `{...}` placeholders, `index`, the `currency_*` column, the `[table]` lines, and the
     NOT NULL rule. The money kind's other keys follow MONEY's helper: `zod` and `pydantic` take
     the amount as a decimal string and the currency is not input: the API writes
     `DEFAULT_CURRENCY` on create and keeps the stored code on edit; `input` stays FORGE-FEATURE-1's
     one amount input with the currency code in front (the row's code on edit,
     `DEFAULT_CURRENCY` on create), so the design does not change; `cell` and `csv` call
     `formatMoney(row.<name>, row.<name>Currency)`; `sample` and `bad` change to match. The
     number kind's `zod`, `pydantic`, `cell` and `sample` take a decimal string that may be
     negative.
   - Test `tests/test_database_kinds.py::test_5_feature_columns_come_from_the_kind_table`
     (platform mark), parameters `typescript` and `python`: in a new starter app,
     `forge task feature customers --one customer --field name:text`, then `forge task feature
     invoices --one invoice --field title:text --field notes?:long-text --field total:money
     --field dueDate:date --field paid:yes-no --field state:status(draft|sent|void) --field
     customer:link(customers)`. The new migration has, filled in, each field's `sql` with NOT NULL
     (and none on `notes`), each `check`, the `totalCurrency` (or `total_currency`) column and its
     check, the search index on `title`, the filter indexes on `paid`, `state` and `customerId`,
     the link's `index`, `list_index` and `updated_at_trigger`. For each kind, the synced
     `.codex/skills/database/SKILL.md` has a table row that names the kind and contains its
     `sql`, `prisma` and `sqlalchemy` values. Under `LIVE`, the copy's migration applies on
     Postgres 18, the feature's generated API tests pass, and the drift check (`prisma migrate
     diff ... --script` prints an empty migration; `alembic check` passes). Adopted case: in the
     adopted client the command refuses and writes nothing, and its synced skill has the same
     rows.
6. The review rule (REVIEW).
   - review.md, in the client-app rules after `Module tables`: `In an app with a database, report a
     table that this change adds, or a column, constraint, index or trigger on such a table, that
     breaks the database skill (.codex/skills/database/SKILL.md) as a P1 finding titled
     Database: <the table or column>. Report a Postgres extension that this change turns on and
     that is not on the skill's allowed list the same way, unless the app's constitution has a
     line "Postgres extension <name>:" with the owner's OK. A change to a table that the default
     branch already has is not a finding.` The reviewer already gets the
     constitution and can open the skill in the checkout. `score.normalise` adds the `Database: `
     floor (Shared names). No review.py change.
   - Test `tests/test_database_review.py::test_6_reviews_hold_schema_that_breaks_the_skill`,
     parameters `new-client` and `adopted-v1.2.2`, on the same fixtures and fakes as
     `tests/test_module_tables_review.py::test_3`: `forge work` gives a brief with SKILL's
     paragraph; a review that returns `Database: Invoice.total` scored `Gain 2, Work 3, Harm 1`
     leaves close blocked with `Gain 4, Work 2, Harm 1 (floor: database)`; the review prompt has
     the rule; after a fix commit and a clean review, close passes.

### New and existing repos

- **New repos** (`forge init`, `--starter`, `--starter python`): the skill for both agents, the
  brief paragraph, the convention pages and the review rule. With a starter: Postgres 18, the
  three extensions, uuidv7 ids, the `set_updated_at()` trigger, starter tables with text status
  and names, lower-case unique sign-in emails and timestamptz times, the new money helper, and
  the feature step's values.
- **Existing repos** (on upgrade to this release, after `forge sync`): the skill, the brief
  paragraph, the convention pages and the review rule. No app file, compose file, schema,
  migration or money helper changes. The review holds only schema that a change adds. Tested on
  the adopted fixture (items 1, 4, 5, 6).

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
| SKILL | The database skill and its texts | The skill page, its shipping to both hosts, the brief paragraph, the coordinator lines, and the database and Python convention pages. | 1 | `src/forge/templates/skills/database/SKILL.md` (new), `src/forge/app_baseline.py`, `src/forge/templates/brief.md`, `src/forge/templates/skill.md`, `src/forge/templates/conventions/database.md`, `src/forge/templates/conventions/python.md`, synced copies under `.claude/skills/` and `.codex/skills/` | `tests/test_database_skill.py` (`test_1`, new); `tests/test_built_in_defaults_guide.py`, `tests/test_python_guide.py` (money lines) | | no | |
| PG18 | Postgres 18 and day-one extensions | Both starters on Postgres 18 with pg_stat_statements preloaded, and one migration each that turns on the three extensions. | 2 | `starter/compose.test.yml`, `starter-python/compose.test.yml`, `starter/apps/api/prisma/migrations/20261026000000_extensions/` (new), `starter-python/apps/api/migrations/versions/0006_extensions.py` (new), `starter/apps/api/test/database.e2e-spec.ts` (new), `starter-python/apps/api/tests/test_database.py` (new), `.github/workflows/starter-smoke.yml` (the two `tests/test_database_*.py` selections) | `tests/test_database_starters.py` (`test_2`, new); the two live cases of item 2 | | no | |
| IDS | Time-ordered ids in the TypeScript starter | uuidv7 ids and the `set_updated_at()` trigger in the TypeScript starter. | 3 | `starter/apps/api/prisma/schema/*.prisma`, `starter/apps/api/prisma/migrations/20261026000100_ids_and_updated_at/` (new), `starter/libs/auth/src/auth.service.ts`, `starter/apps/api/test/database.e2e-spec.ts` | `tests/test_database_starters.py` (`test_3_new_rows...`, `react`); the TypeScript ids case of item 3 | PG18 | no | |
| IDSPY | Time-ordered ids in the Python starter | uuidv7 ids and the `set_updated_at()` trigger in the Python starter. | 3 | `starter-python/apps/api/app/*/models.py`, `starter-python/apps/api/app/*/service.py` (id lines only), `starter-python/apps/api/migrations/versions/0007_ids_and_updated_at.py` (new), `starter-python/apps/api/tests/test_database.py` | `tests/test_database_starters.py` (`test_3_new_rows...`, `python`); the Python ids case of item 3 | PG18, IDS | no | |
| COLUMNS | TypeScript starter tables follow the skill | Text status and role with named checks, text names, the lower-case unique emails and timestamptz times in the TypeScript starter. | 3 | `starter/apps/api/prisma/schema/*.prisma`, `starter/apps/api/prisma/migrations/20261026000200_columns/` (new), the files in `starter/libs/*/src/` that import a Prisma enum type, `starter/apps/api/test/database.e2e-spec.ts` | `tests/test_database_starters.py` (`test_3_starter_tables...`, `react`); the TypeScript columns case of item 3 | IDS | no | |
| COLUMNSPY | Python starter tables follow the skill | Text status and role with named checks, text names and the lower-case unique emails in the Python starter. | 3 | `starter-python/apps/api/app/*/models.py`, `starter-python/apps/api/migrations/versions/0008_columns.py` (new), `starter-python/apps/api/tests/test_database.py` | `tests/test_database_starters.py` (`test_3_starter_tables...`, `python`); the Python columns case of item 3 | IDSPY, COLUMNS | no | |
| MONEY | Exact money with its currency | The new `formatMoney` and `DEFAULT_CURRENCY` in both starters, its unit cases and the README line. | 4 | `starter/libs/shared/src/format.ts`, `starter-python/libs/shared/src/format.ts`, `starter/libs/shared/src/index.ts`, `starter-python/libs/shared/src/index.ts`, `starter-python/apps/api/app/core/config.py`, `starter/apps/web/src/lib/format.test.ts`, `starter/README.md` | `tests/test_database_money.py` (`test_4`, new); the format unit cases | | no | |
| REVIEW | Review holds schema that breaks the skill | The review rule and the `Database:` score floor. | 6 | `src/forge/templates/review.md`, `src/forge/score.py` | `tests/test_database_review.py` (`test_6`, new) | SKILL | no | |
| KINDS | The field-kind table's database values | The final database values and new keys in kinds.toml, the money and number keys that follow the new helper, and the small `feature.py` changes they need. | 4, 5 | `src/forge/templates/feature/kinds.toml`, `src/forge/feature.py` (the value rendering only) | `tests/test_database_kinds.py` (`test_5`, new); FORGE-FEATURE-1's `tests/test_feature_command.py` where it names a placeholder value | FORGE-FEATURE-1/PY, SKILL, COLUMNS, COLUMNSPY, MONEY | no | |

New moving parts: the pg_stat_statements, pg_trgm and btree_gin extensions in both starters (item 2); the `set_updated_at()` trigger function in both starters' migrations (item 3). No new package: `uuidv7()` is built into Postgres 18 and `uuid7()` into Python 3.14.

## Notes

- **Order.** SKILL, PG18 and MONEY start at once; they share no file. IDS after PG18 (its
  migration comes after the extensions one and needs Postgres 18); IDSPY after PG18 and IDS (the
  shared live test file and the same function name). COLUMNS after IDS (the same schema files
  and the next migration); COLUMNSPY after IDSPY and COLUMNS. REVIEW after SKILL (its test checks
  SKILL's brief paragraph). KINDS last: it needs FORGE-FEATURE-1's command and kinds.toml, the
  skill's table, the starters' new tables, and the new money helper. All parts ship in one
  release.
- **Order with FORGE-FEATURE-1.** That story's command copies the starter's projects module, so
  IDS, IDSPY, COLUMNS and COLUMNSPY must merge before FORGE-FEATURE-1's COMMAND part. That part
  lists them under After. Its SOURCE and SOURCEPY parts also change the projects files; whichever
  merges later brings main in first.
- **Not in this story.** Projects paging (next and previous links) belongs to FORGE-FEATURE-1's
  SOURCE part.
- **The other story.** FORGE-FEATURE-1's COMMAND part creates kinds.toml with placeholder database
  values; that story's plan says this story sets them. Its `{enum}` placeholder and its own
  Postgres enum for status go: status is text with a CHECK. Its test_3 reads the values from the
  table, so it keeps passing.
- **Part sizes.** Each part is planned under 400 hand-written lines; the skill page is the
  largest at about 220. IDS and IDSPY touch many files with one-line id edits.
- **Owner decisions (25 Oct 2026, settled).** No cache server at the start; the rules reach code
  through the feature step's field-kind table, the shipped skill and the review; Postgres 18 and
  `uuidv7()` ids in both starters; money as `numeric(19,4)` with a currency code column; tenants
  scoped in one data layer with a refusal test for each endpoint, and row-level security only as
  its own story; keyset paging by default; extensions only from the four hosts' list, others with
  the owner's OK for that client; pg_stat_statements, pg_trgm and btree_gin on from day one;
  existing apps get the rules for new tables only, with no forced Postgres, id or money
  migration. Later the same day the owner added: the starters' own tables move to the rules in
  both starters (text status with a named check, text names, sign-in email unique on
  `lower(email)`, timestamptz times), and existing client apps are not touched. The column, constraint, index, jsonb, history and dashboard rules in the skill are
  the owner's research decisions of the same day.
- **Planner choices the owner did not make.** (1) The skill ships beside app-baseline from
  `app_baseline.ships`, with its source under `src/forge/templates/skills/`. (2) The extension OK
  is a line in the constitution, which the review already reads. (3) Each money field has its own
  currency column. (4) The email field kind is a contact field and is not unique; the unique
  lower-case rule is for sign-in emails. (5) The project name keeps its 120-character limit as a
  named check; token and password hashes become text with no check, because the app writes
  them. (6) The invite's per-organisation email unique also moves to lower case. (7) The review holds schema only; paging and the other query
  rules are the skill's guidance. (8) A `Database:` finding gets the same score floor as a
  `Module tables:` finding, so a low score cannot let it through.
- No client repo is named anywhere in this story's code, tests, texts or commits.

### Cold read round 1

1. Services lose their email selectors. Disposition: cut. The sign-in and invite emails keep
   their plain unique keys and get a named lower-case check, which makes them unique on
   `lower(email)` with no service change (both starters already lower-case emails on input).
2. Prisma's nearest index contradicts the empty drift check. Disposition: cut. The TypeScript
   starter turns on Prisma's `partialIndexes` preview, so the schema states each index in full
   and the drift check can be empty.
3. The uuidv7 id has no path on Postgres 17 or older. Disposition: cut. The skill's id row says
   that on Postgres 17 or older the app makes the uuidv7 id (Prisma `uuid(7)`, Python `uuid7`);
   test_1 checks the line.
4. The skill and review reach past new tables. Disposition: cut. The skill and the review rule
   now cover only the tables a change adds (with their columns, constraints, indexes and
   triggers) and the extensions it turns on.
5. CI never selects the live database checks. Disposition: cut. PG18 adds
   `tests/test_database_*.py` to both starter-smoke jobs, split by the `python` parameter id.
6. The money entry changes with no design. Disposition: cut. The currency is not entered: the
   form keeps FORGE-FEATURE-1's one amount input with the code in front, and the API fills the
   currency column from `DEFAULT_CURRENCY`. Design stays none.
7. Indexes sort on creation time, but lists sort on last change. Disposition: cut. The list and
   filter indexes use `{updated}`.
8. Redeploy does not recover a failed Prisma migration. Disposition: cut. The trade-off and the
   skill add `prisma migrate resolve --rolled-back <migration>` before the new deploy.
