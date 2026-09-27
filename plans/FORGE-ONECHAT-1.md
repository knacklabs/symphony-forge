# The owner wants every Forge repo's stories approved from one main chat, but the approval hook only sees stories in the repo the chat started in

## What changes for you

<What the people who use this will notice, in plain English. No IDs, codes or jargon.>

## Why

The owner wants every Forge repo's stories approved from one main chat, but the approval hook only sees stories in the repo the chat started in

## Done when

1. docs/specs/one-chat-approval.md is confirmed by the owner and on the roadmap as FORGE-ONECHAT-1

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
| THE-OWNER-WANTS-EVERY-FORGE-REPO-S-STORI | The owner wants every Forge repo's stories approved from one main chat, but the approval hook only sees stories in the repo the chat started in | The owner wants every Forge repo's stories approved from one main chat, but the approval hook only sees stories in the repo the chat started in | 1 | `docs/specs/one-chat-approval.md`, `docs/specs/one-chat-approval.read.md`, `plans/roadmap.json` | | none | no |

New moving parts: none

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none

## Notes
