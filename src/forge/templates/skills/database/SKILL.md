---
name: database
description: "Database rules for Forge client apps on Postgres. Use before adding or changing a table, column, index, constraint, migration, extension, list query, report or job table, in Prisma or SQLAlchemy."
---

# Database

These rules apply to the tables a change adds, with their columns, constraints, indexes and triggers, and the extensions it turns on.
A change to an existing table follows that table's own style. Never migrate existing tables to these rules unless a story asks.
Where the app's constitution differs, it wins, including an existing rule to store money in cents.

## Columns by kind of data

| Kind of data | Postgres | Prisma | SQLAlchemy | Rule |
|---|---|---|---|---|
| text | `text` | `String` | `Text` | `CONSTRAINT "{table}_{column}_length" CHECK (char_length("{column}") BETWEEN 1 AND 200)` |
| long-text | `text` | `String` | `Text` | `CONSTRAINT "{table}_{column}_length" CHECK (char_length("{column}") <= 10000)` |
| number | `numeric(19,4)` | `Decimal @db.Decimal(19, 4)` | `Numeric(19, 4)` | No sign check; a plan adds a check for a field when the client needs one. |
| money | `numeric(19,4)`; currency `text` | `Decimal @db.Decimal(19, 4)`; currency `String` | `Numeric(19, 4)`; currency `Text` | `CONSTRAINT "{table}_{currency}_code" CHECK ("{currency}" ~ '^[A-Z]{3}$')` |
| date | `date` | `DateTime @db.Date` | `Date` | A calendar date, with no time zone. |
| yes-no | `boolean DEFAULT false` | `Boolean @default(false)` | `Boolean, server_default=false()` | Always NOT NULL, even when the field is marked optional. |
| email | `text` | `String` | `Text` | `CONSTRAINT "{table}_{column}_format" CHECK (char_length("{column}") <= 254 AND "{column}" ~ '^[^@[:space:]]+@[^@[:space:]]+$')` |
| status | `text DEFAULT '{first}'` | `String @default("{first}")` | `Text, server_default="{first}"` | `CONSTRAINT "{table}_{column}_allowed" CHECK ("{column}" IN ({options}))` |
| link | `uuid` | `String @db.Uuid` | `Uuid` | Follow the module-link rule below; index it. |
| id | `uuid DEFAULT uuidv7()` | `String @id @default(dbgenerated("uuidv7()")) @db.Uuid` | `mapped_column(Uuid, primary_key=True, server_default=text("uuidv7()"))` | Python code that needs the id first uses `uuid.uuid7()`. |
| count | `integer` | `Int` | `Integer` | Use `bigint` / `BigInt` / `BigInteger` when it can pass two billion. |
| instant | `timestamptz` | `DateTime @db.Timestamptz(3)` | `DateTime(timezone=True)` | Store UTC; local time belongs at the edge. |
| blob read whole | `jsonb` | `Json @db.JsonB` | `JSONB` | Named `CHECK (jsonb_typeof("{column}") = 'object')`. |
| time range | `tstzrange` | `Unsupported("tstzrange")` | `TSTZRANGE` | Use `'[)'` bounds. |
| location | `numeric(9,6)` latitude and longitude | `Decimal @db.Decimal(9, 6)` | `Numeric(9, 6)` | Display and rough nearby only; use PostGIS `geography` for radius and shapes. |
| embedding | `halfvec` | `Unsupported("halfvec")` | pgvector `HALFVEC` | See Extensions; do not add a package unless the story names it. |

On Postgres 17 or older, where `uuidv7()` does not exist, the app makes the uuidv7 id: Prisma `@default(uuid(7))`, Python `default=uuid7`, and no database default. Use a UUIDv7 implementation the app already has; a new dependency needs a story.
Use `text`, never `varchar(n)`, with a named length CHECK. Never use `float` or `double precision` for business values.
Status is `text` with a named CHECK, never a Postgres enum. Money and decimals travel as decimal strings in JSON.
Each money field has its own currency column (`totalCurrency` / `total_currency`). Fill it from the app's default currency (INR unless the owner chooses another at setup); show the code in front of the one amount input, with no currency picker. Format with the shared money helper.
The email kind is a contact field and is not unique; sign-in emails follow Keys and constraints.

## Keys and constraints

| Concern | Rule |
|---|---|
| Module schemas | Each module has its own Postgres schema; core tables live in the `core` schema. |
| Module links | A link between two business modules stores the id with an index and no foreign key. Links within a module and links to core tables keep their foreign key. |

Use NOT NULL unless the field is really optional. Every constraint has a name: `<table>_<column>_<rule>`.
Where a link has a foreign key, use `ON DELETE RESTRICT`. Use `CASCADE` only for detail rows the parent owns, such as order lines; `SET NULL` only for an optional reference. Index every foreign key.
Store a sign-in email in lower case, with `<table>_email_lower CHECK (email = lower(email))`, and a unique key (organisation column first when the table has one). This makes it unique on `lower(email)`; do not use citext.
The shared `set_updated_at()` BEFORE UPDATE trigger sets the last-changed time, including raw SQL updates. Use `updatedAtUtc` in Prisma and `updated_at_utc` in Python.
Every tenant table has the organisation column. One data layer scopes each query to the caller's organisation, with one refusal test per endpoint. Row-level security is not a default; a regulated client gets it as its own story.

## Migrations

Expand, then contract. Add a new table or column before code uses it. Keep the old table or column for two releases, and remove it only when no live release uses it. Mainline rollback restores the previous release's code and keeps the database, so every migration must work with that code still running.

Close checks only migrations added by the change. It skips this check in a prototype repo with no live release. A new migration that drops or renames a table or column, or changes a column's type, needs a comment that explains why the live release no longer reads it: `-- Contract: the live release no longer reads "Project"."legacyName".` in Prisma SQL or `# Contract: the live release no longer reads project.legacy_name.` in Alembic Python. Close allows the migration when this line is present; review reads the explanation.

## Indexes for lists

Use `(organisation_id, <filter columns>, <sort column> DESC, id DESC) WHERE deleted_at IS NULL`.
The default list sort is last change, newest first. In the statements below, `{org}`, `{updated}` and `{deleted}` mean the organisation, last-changed and soft-delete columns in the app's naming style. `{table}`, `{column}`, `{currency}`, `{first}` and `{options}` come from the field-kind table.

| Use | SQL |
|---|---|
| Every table's list | `CREATE INDEX "idx_{table}_list" ON "{table}" ("{org}", "{updated}" DESC, "id" DESC) WHERE "{deleted}" IS NULL;` |
| yes-no, status or link filter | `CREATE INDEX "idx_{table}_{column}" ON "{table}" ("{org}", "{column}", "{updated}" DESC, "id" DESC) WHERE "{deleted}" IS NULL;` |
| text or email search | `CREATE INDEX "idx_{table}_{column}_search" ON "{table}" USING gin ("{org}", "{column}" gin_trgm_ops) WHERE "{deleted}" IS NULL;` |
| Every link, filter or not | `CREATE INDEX "idx_{table}_{column}_fk" ON "{table}" ("{column}");` |
| Last-changed trigger | `CREATE TRIGGER "{table}_set_updated_at" BEFORE UPDATE ON "{table}" FOR EACH ROW EXECUTE FUNCTION set_updated_at();` |

The search box uses `ILIKE '%' || $term || '%'`, with a pg_trgm GIN index and the organisation column in front through btree_gin. Bind the term as a parameter.
Word search in long text uses a generated `tsvector` column (`STORED`), a GIN index and `websearch_to_tsquery`.
Other field kinds have no automatic filter or search index. Add no index that no query uses. Check a slow query with `EXPLAIN (ANALYZE, BUFFERS)`.

## List paging

Use keyset paging by default: `WHERE (sort, id) < ($lastSort, $lastId) ORDER BY sort DESC, id DESC LIMIT <n + 1>`.
Show next and previous links and an approximate total: cap the count at 10,000 and show "More than 10,000" above the cap. Reverse the comparison and order for the previous page, then reverse the returned rows.
Use numbered pages only on small admin screens. Existing lists keep their paging.

## Dashboards and reports

Start with a live query on indexed columns. When pg_stat_statements shows it over about 200 ms, use a materialized view with a unique index, refreshed `CONCURRENTLY` by pg_cron or a job, or a summary table that app code updates in the same transaction. No pg_ivm.

## Change history

App code writes the history row in the same transaction (in the starters, `HistoryService.record`); no audit triggers.
Partition history by month only past about 50 to 100 million rows or when old months must be dropped.

## Job tables

When a story first adds background jobs or schedules, add a worker entry in `services.toml`
and a jobs table read with `SELECT ... FOR UPDATE SKIP LOCKED`. Keep the attempt count and
last error on the job row. A schedule only inserts job rows; the worker does the work through
the owning module's public service. Make each job safe to run again after a worker stops.
The first job is clean-up of old sessions, reset tokens and invites.
Add these only with the story that needs jobs, not to the starters. No separate queue server.

## jsonb

Use real columns for anything filtered, joined, sorted or constrained. Use jsonb for a blob read whole, with `CHECK (jsonb_typeof(...) = 'object')`.
When an existing blob must be filtered by containment, use a `jsonb_path_ops` GIN index; for one hot key, use a generated column. No hstore.

## Extensions

| Need | Use | Best practice |
|---|---|---|
| Similar text and typos | pg_trgm GIN | btree_gin puts the organisation column in front. |
| Ranked word search | Built-in `tsvector` | Generated STORED column, GIN and `websearch_to_tsquery`. |
| Accents | unaccent | An `IMMUTABLE` wrapper function lets an index use it. |
| Trees and graphs | Adjacency list and recursive CTE with `CYCLE` | Start here for org charts and permissions; ltree with GiST for read-heavy trees; a closure table when items move often. |
| Location | PostGIS `geography` | GiST index and `ST_DWithin`. |
| Bookings that must not overlap | `tstzrange` | `EXCLUDE USING gist` through btree_gist, or Postgres 18 `WITHOUT OVERLAPS`. |
| Embeddings | pgvector in a separate table | Store organisation_id, source_type, source_id, model, model_version, content_hash and embedding `halfvec`. Exact scan with the organisation filter under about 100,000 vectors per tenant; then HNSW with m 16, ef_construction 64 and `hnsw.iterative_scan = relaxed_order`. Match the operator class to the distance; re-embed by the model column. A separate vector database only well past 10 million vectors. |
| Large tables | Partitioning with pg_partman | Only past about 50 to 100 million rows or for retention drops; RANGE by time or HASH by organisation. |
| Scheduled SQL | pg_cron | SQL schedules only. |
| Time series | Partitioned table | BRIN index. |
| Slow queries | pg_stat_statements, on from day one | auto_explain where the host offers it: `log_min_duration` about 500 ms, `log_analyze` on, `log_timing` off, sample rate about 0.1. |

Allowed list (AWS RDS, Google Cloud SQL, Azure and Neon): pgvector, ltree, pg_trgm, unaccent, fuzzystrmatch, citext, PostGIS, btree_gist, btree_gin, pg_partman, pg_cron, pg_stat_statements, pgcrypto.
Every other extension (for example AGE, TimescaleDB, pgmq or pg_search) needs the owner's OK for this client. Ask first, then write this line under Architecture choices in `docs/product/CONSTITUTION.md`:

`- Postgres extension <name>: the owner allows it on <date> (<why>)`

Avoid pg_ivm. pg_uuidv7 is not needed: Postgres 18 has `uuidv7()`.
Turn an extension on in its own migration in the first story that needs it: `CREATE EXTENSION IF NOT EXISTS <name>;`. New starters have pg_stat_statements, pg_trgm and btree_gin on from day one; existing apps keep their extensions.
If a deploy stops because the app's user cannot turn an extension on, turn it on once as the host's admin user. In a Prisma app run `prisma migrate resolve --rolled-back <migration>` (the starter's extension migration is `20261026000000_extensions`); Alembic needs no step. Then deploy again. Do not hide the database error.

## Speed without a cache

No cache server at the start. Add one only for a slow page that pg_stat_statements measures and indexes cannot fix, for sessions or rate limits across instances, or for a hot aggregate read again and again. The story must name the new moving part.

## Prisma and SQLAlchemy

| Thing | Prisma | SQLAlchemy and Alembic |
|---|---|---|
| uuidv7 default | `@default(dbgenerated("uuidv7()")) @db.Uuid` | `server_default=text("uuidv7()")` with `Uuid` |
| timestamptz | `DateTime @db.Timestamptz(3)` | `DateTime(timezone=True)` |
| CHECK | Raw SQL: `prisma migrate dev --create-only`, then edit the SQL | `CheckConstraint(..., name=...)` in the model and `op.create_check_constraint`; autogenerate misses CHECK changes. |
| Partial index | `@@index([...], where: ...)` with the `partialIndexes` preview feature on | `Index(..., postgresql_where=...)` |
| Trigram GIN | `@@index([...], type: Gin)` with `ops: raw("gin_trgm_ops")` | `postgresql_using="gin"`, `postgresql_ops` |
| Generated tsvector | `Unsupported("tsvector")` plus raw SQL | `Computed(..., persisted=True)` with `TSVECTOR` |
| Trigger, function, extension, exclusion constraint | Raw SQL in the migration | Raw SQL; `ExcludeConstraint` for an exclusion constraint. |
| Drift check after raw SQL | After the shadow database setup below, `prisma migrate diff --from-migrations apps/api/prisma/migrations --to-schema apps/api/prisma/schema --script` must print an empty migration | `alembic check` must pass. |

Before running the Prisma drift check against a migrations directory:

1. Create a separate, empty development database, for example `CREATE DATABASE app_shadow;`, using a database admin if needed. Give the migration user ownership of this database.
2. Set `SHADOW_DATABASE_URL` in the command's environment to that database's connection URL. Keep credentials out of git.
3. In `prisma.config.ts`, import `env` from `prisma/config` and add `shadowDatabaseUrl: env("SHADOW_DATABASE_URL")` to the existing `datasource` object, beside its `url`. Keep the existing schema and migrations paths.
4. Run the drift check from the app root with both `DATABASE_URL` and `SHADOW_DATABASE_URL` set.

The shadow database must be disposable and different from every database holding app data. Prisma resets it while replaying migrations; never point `shadowDatabaseUrl` at the development or production app database. This setup is for development checks, not production deployment. See [Prisma's shadow database setup](https://www.prisma.io/docs/orm/v7/prisma-migrate/understanding-prisma-migrate/shadow-database).

State each Prisma index in full, including partial WHERE, type and ops. CHECK constraints and triggers live only in migration SQL: Prisma neither states nor compares them. Never edit a merged migration.
