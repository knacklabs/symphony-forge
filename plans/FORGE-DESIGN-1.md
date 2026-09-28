# Design work (screens and flows) runs on Codex like everything else, but the owner wants UI and UX built by Opus 5.5 with impeccable, Emil and the app baseline, falling back to Codex Sol high

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

<What the people who use this will notice, in plain English. No IDs, codes or jargon.>

## Why

Design work (screens and flows) runs on Codex like everything else, but the owner wants UI and UX built by Opus 5.5 with impeccable, Emil and the app baseline, falling back to Codex Sol high

## Done when

1. **User-facing story tasks and prototype fixes run on a Claude worker with the models in forge.toml's [models.design] (Opus 5.5, high), falling back to Codex with [models.design.codex] (Sol, high) only when Claude can't run; other work is unchanged** <Detail: evidence, edge cases or technical notes, if needed.>

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none

## For the builders

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
| SPEC | Design work (screens and flows) runs on Codex like everything else, but the owner wants UI and UX built by Opus 5.5 with impeccable, Emil and the app baseline, falling back to Codex Sol high | Design work (screens and flows) runs on Codex like everything else, but the owner wants UI and UX built by Opus 5.5 with impeccable, Emil and the app baseline, falling back to Codex Sol high | 1 | `docs/specs/prototype-signoff.md`, `docs/specs/prototype-signoff.read.md`, `plans/FORGE-PROTO-1.md`, `plans/FORGE-PROTO-1.read.md`, `plans/roadmap.json` | | none | no |

New moving parts: none

## Notes
