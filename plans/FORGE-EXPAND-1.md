# Client migrations keep the previous release working

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- A rollback of a client app's code keeps its data working. A migration may add tables and columns, but a drop, rename or type change waits until the live release no longer uses that column or table.
- The database guide states expand then contract: add first, remove two releases later.
- Close reads the SQL and Python migration files of each new migration in both starters, and refuses a drop, rename or type change unless the story's Contract line says the live release no longer uses it.

## Why

A Mainline rollback reverts code only and leaves the database at the new migration, so old code that still reads a removed or renamed column fails. The rule is prose only today, and close reads no migration file, so nothing stops a destructive migration.

## Done when

1. **Close refuses a new migration that drops, renames or changes the type of a column or table, and names the Contract line as the way past it, in a new client repo and in a repo adopted on an earlier release.**
2. **With a Contract line that says the live release no longer uses the column or table, the same migration passes close.**
3. **The database guide and the coordinator and worker guide state expand then contract in the same change.**

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
