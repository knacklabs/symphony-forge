# src/forge is at its 8,000-line ceiling, so the next stories can't add their code without breaking Forge's rule that it shrinks over time

## What changes for you

<What the people who use this will notice, in plain English. No IDs, codes or jargon.>

## Why

src/forge is at its 8,000-line ceiling, so the next stories can't add their code without breaking Forge's rule that it shrinks over time

## Done when

1. src/forge has at least 400 fewer lines than on main, with no behaviour change: the full test suite passes and every Forge command's output is unchanged

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
| SRC-FORGE-IS-AT-ITS-8-000-LINE-CEILING-S | src/forge is at its 8,000-line ceiling, so the next stories can't add their code without breaking Forge's rule that it shrinks over time | src/forge is at its 8,000-line ceiling, so the next stories can't add their code without breaking Forge's rule that it shrinks over time | 1 | `docs/specs/forge-trim.md`, `docs/specs/forge-trim.read.md`, `plans/roadmap.json` | | none | no |

New moving parts: none

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none

## Notes
