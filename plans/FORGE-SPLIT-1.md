# A few shared files, the command table, the sync file list and the guide's command table, make every new feature queue behind the others

## What changes for you

<What the people who use this will notice, in plain English. No IDs, codes or jargon.>

## Why

A few shared files, the command table, the sync file list and the guide's command table, make every new feature queue behind the others

## Done when

1. docs/specs/own-your-entry.md is confirmed by the owner and on the roadmap as FORGE-SPLIT-1

## Tasks

<!-- One row per task. Covers: the Done-when numbers it delivers, at most three. Scope: the paths
it may change. Tests: the tests it adds or changes. After: the tasks it waits for. When two tasks
share a function, field, file format or command, the first task pins it: it commits the shared
names and stubs plus one test that crosses both sides, and the tasks that use it list it under
After. Split tasks so each owns its files; shared lines (command table, guide list, registry) go
to one task or a small last wiring task; After only when a task needs another task's code. The
moving-parts line stays last: "none", or each new dependency, service, datastore,
queue, background job or abstraction layer, with the Done-when item that needs it. -->

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| A-FEW-SHARED-FILES-THE-COMMAND-TABLE-THE | A few shared files, the command table, the sync file list and the guide's command table, make every new feature queue behind the others | A few shared files, the command table, the sync file list and the guide's command table, make every new feature queue behind the others | 1 | `docs/specs/own-your-entry.md`, `docs/specs/own-your-entry.read.md`, `plans/roadmap.json` | | none | no |

New moving parts: none

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none

## Notes
