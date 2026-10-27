# Build only what was asked

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- Every story plan names where each screen, field, endpoint, tool and setting came from: a client note, a brief answer, a decision record, or a screen marked Build now at sign-off.
- Cold reads and reviews report an addition with no source as not asked for, and that blocks. The canvas may show the full product; code is checked against the signed Build now scope.
- A worker that thinks of a useful extra writes one line in the repo's idea list and builds nothing for it.
- New client repos get the rule at init, and existing client repos get it with forge sync.

## Why

Plans and builds add screens, fields, endpoints, tools and settings that nobody asked for. Today the cold read and the review flag only work that no Done-when item needs, so an extra that a Done-when line can be stretched to cover gets through.

## Done when

1. **Every story plan names a source for each screen, field, endpoint, tool and setting it adds.**
2. **A plan or build with an unsourced addition gets a blocking note saying it was not asked for.**
3. **A worker's useful extra becomes one idea-list line, not code.**
4. **New and existing client repos each get the rule, with a test for each side.**

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
