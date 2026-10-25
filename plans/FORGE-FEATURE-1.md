# Build a client feature from the starter in one step

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- The agent runs a new feature command from the plan, so the FDE never types it or makes technical choices.
- Each new feature comes with a table that keeps deleted items and their change history, a checked API, list, detail and form screens with filters kept in the web address, CSV export, and admin and member access.
- Each new feature takes the fields the plan names, of these kinds: text, long text, number, money, date, yes or no, email, a status list, and one link to an item of another feature.
- In an app that is not a starter, the command says it needs a starter app and changes nothing.

## Why

FDEs must ship client features without technical choices, but each new feature is built by hand in both starters. The starter's projects feature already has soft delete, change history, validation, CSV export and URL filters, so the command can copy and rename it.

## Done when

1. **An FDE names a new feature and its fields in a plan, and the first worker step builds it in both the TypeScript and the Python starters.**
2. **The generated feature's API and UI tests pass in both starters.**
3. **The generated feature has soft delete, change history, CSV export and role-based access, like the existing projects feature.**
4. **Outside a starter app the command refuses and says it needs a starter app.**

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
