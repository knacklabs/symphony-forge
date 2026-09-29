# Upgrading Forge in a client repo is blocked: the upgrade pull request can never pass Forge's check, close calls it clean with stale synced files, and the default branch refuses every command until the upgrade merges

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

<What the people who use this will notice, in plain English. No IDs, codes or jargon.>

## Why

Upgrading Forge in a client repo is blocked: the upgrade pull request can never pass Forge's check, close calls it clean with stale synced files, and the default branch refuses every command until the upgrade merges

## Done when

1. **A client repo upgrades Forge through one fix whose pull request passes Forge's check** <Detail: evidence, edge cases or technical notes, if needed.>

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
| SPEC | Upgrading Forge in a client repo is blocked: the upgrade pull request can never pass Forge's check, close calls it clean with stale synced files, and the default branch refuses every command until the upgrade merges | Upgrading Forge in a client repo is blocked: the upgrade pull request can never pass Forge's check, close calls it clean with stale synced files, and the default branch refuses every command until the upgrade merges | 1 |  | | none | no |

New moving parts: none

## Notes
