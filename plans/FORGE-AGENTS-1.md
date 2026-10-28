# Client apps with agents get agent must-haves before they build

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- Client repos get an agents skill, like the database skill, with the owner's agent must-haves, each with its default and its LangGraph note.
- Builders load the skill before any agent, chat, voice or assistant work, and channel-only rules apply only when the app has that channel.
- Review checks agent work against the skill's must-haves.
- A new client repo gets the skill at init, and an existing client repo gets it on upgrade.

## Why

Builders choose agent design, memory, safety and cost rules by hand for each feature, so the choices differ from one feature to the next.

## Done when

1. **A new client repo has the agents skill after init, and an existing client repo has it after upgrade.**
2. **Agent, chat, voice and assistant work starts only after the skill is loaded, and each must-have shows its default and LangGraph note.**
3. **Review reports agent work that breaks a must-have as a must-fix finding.**

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
