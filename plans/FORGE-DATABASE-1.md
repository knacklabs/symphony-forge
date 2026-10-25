# Database rules for every client app

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- New client repos get a database skill covering column types, keys, constraints, indexes that match each list's filters, sorting and search, keyset paging, dashboards and summary tables, change history, job tables, and when to use each extension.
- The skill covers only extensions that AWS RDS, Google Cloud SQL, Azure and Neon all offer, unless the owner allows one for a client.
- Both starters move from Postgres 17 to Postgres 18, with time-ordered ids, money as numeric(19,4) with a currency column (replacing whole cents), and pg_stat_statements, pg_trgm and btree_gin on from the first day.
- One field-kind table sets the column type, constraint and index for each kind of field, and the feature step reads it, so builders stop choosing them by hand.
- A review rule rejects any schema that breaks the skill.
- Existing apps get the skill and the rules for new tables only; their current tables stay as they are.

## Why

Column types, keys, indexes and extensions are chosen by hand for each feature, so choices can differ from one builder to the next. The starters run Postgres 17.6, use random uuid ids, and the database convention page stores money as whole cents and covers only Prisma, while the Python starter uses SQLAlchemy.

## Done when

1. **A new client repo gets the database skill, and its starter runs Postgres 18 with the three extensions on.**
2. **The feature step fills each column type, constraint and index from the field-kind table, with no manual choice.**
3. **A review fails any schema that breaks the skill.**
4. **An existing app's new tables follow the rules, and its old tables are unchanged.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

### Done-when details

<!-- Under each Done-when item's number: its evidence, edge cases and the tests that prove it.
Workers and reviewers get the entries of the items they cover. An item with nothing to add has
no entry. -->

1. <Evidence, edge cases and the tests that prove item 1.>

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

New moving parts: none

## Notes
