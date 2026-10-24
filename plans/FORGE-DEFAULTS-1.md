# New client apps start with the constitution's built-in defaults

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- New client apps get the constitution's built-in defaults from the first commit: organisation-scoped data, admin and member roles, email invites, shared date, time and money helpers, a CSV export for each table, change history for admin actions with soft delete as a shared rule, and one error report for UI and API crashes.
- Existing apps keep their code. On upgrade they get the guide and the rules text only.
- It builds after the React defaults and zod starter parts merge.

## Why

The constitution's defaults promise these things, but the starter builds none of them. Each new app's agent therefore decides and builds its own version. Today the starter scopes data to one account, not an organisation; it has no roles, invites, CSV export, money helper, or web error report; and date text comes from a local formatting function in the projects page, not a shared helper.

## Done when

1. **A new client app's organisation data is scoped so one organisation's records are never returned to another.**
2. **Admins can invite people by email, and members cannot change roles or invite people.**
3. **Date, time and money display come only from shared helpers, and a lint rule fails hand-written formatting in API and web.**
4. **Each table has a CSV export from one shared code path, and admin actions write change history.**
5. **A UI crash and an API crash each write one error report to the logs.**
6. **The starter's tests pass, and an existing app's code is unchanged after upgrade.**

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
