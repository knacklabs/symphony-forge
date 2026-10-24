# New client apps start from the client notes and a fixed modular stack

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- The agent reads the FDE's client notes and asks only the questions that change a screen, field or flow, one at a time. Other open points get a listed default. Anything the FDE cannot answer goes to an "ask the client" list in the recap, and the prototype does not wait.
- Every new app is a modular monolith on pnpm and Prisma. Modules call each other only through public services, never through another module's tables. The starter turns on Nx's module-boundary lint, so a cross-module import fails the tests, and reviews hold a direct query on another module's tables.
- The constitution fills in the 21 product defaults at the start and raises one only when the notes contradict it. The owner still approves it once after sign-off.
- Existing apps keep their package manager and structure. Reviews hold only new cross-module queries, and the constitution records the stack the app already uses.

## Why

The module rule exists only as prose in the shipped backend conventions, and the starter has no lint rule that enforces it. The starter ships an npm lockfile, not pnpm. The FDE also answers many product questions one by one before the prototype, and the constitution asks the defaulted ones again later.

## Done when

1. **A new client app's starter fails its tests when one module imports another module's tables.**
2. **A new client app's constitution arrives with the 21 defaults filled in, and the FDE sees a list of contradictions and gaps instead of a full question list.**
3. **An existing app keeps its package manager and folder layout after upgrading, and its reviews check only new cross-module queries.**

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
