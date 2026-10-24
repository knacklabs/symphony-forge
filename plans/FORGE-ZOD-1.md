# One zod schema checks every client app input

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- New client apps check all input with zod: the projects list query moves from class-validator rules to a zod schema in the shared library, next to the body schemas.
- New client apps no longer include class-validator or class-transformer.
- The API documentation for the projects list is built from that same zod schema.
- The API and backend convention pages tell agents to write zod schemas for request input, not class-validator rules.
- Existing client apps keep their current validation; only new code follows the zod rule.

## Why

The starter checks input two ways: class-validator on the projects list query and zod on request bodies. The API convention page tells agents to write class-validator rules, so new code follows the older rule and the starter ships two validators.

## Done when

1. **A new client app's dependencies have no class-validator or class-transformer.**
2. **A bad projects list query gets the same validation error reply as a bad request body.**
3. **The projects list's documented query fields come from the zod schema in the shared library.**
4. **The API and backend convention pages name zod for request input.**
5. **An existing client app keeps its current validation after upgrading.**

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
