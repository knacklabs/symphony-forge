# Client apps reach sign-off through five guided steps and one list of open decisions

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- The client is led through five steps (brief, canvas design, clickable prototype, open decisions, sign-off), each ending with a short check-in, instead of a pile of questions at the end.
- The canvas in Play mode is the default clickable prototype; a coded working prototype is optional and needs a demo address only when built.
- One open-decisions list for the whole repo collects every item that needs the client, each scored on Gain, Work and Harm, with a pre-picked default and a due date.
- When a due date passes, the default applies, is recorded as decided by default, and the client is told.
- forge next and the board show a sign-off readiness line, such as Decisions 3 open (1 blocks).

## Why

Clients are asked many questions at the end of a project, so sign-off comes late and the client cannot see what they are approving (client issue 1145).

## Done when

1. **The five steps run in order, and each step ends with a short client check-in.**
2. **Forge asks for open decisions at the end of each step and at least weekly, and each item shows its default and due date.**
3. **A passed due date applies the default, records it as decided by default, and tells the client.**
4. **forge next and the board show a readiness line for brief, screens and decisions.**
5. **Sign-off is refused while the signed canvas is missing or a blocking decision is open, and the refusal names the next step.**
6. **A new client repo and an existing client repo that adopted an earlier release each get the path, with at least one existing-repo test case.**

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
