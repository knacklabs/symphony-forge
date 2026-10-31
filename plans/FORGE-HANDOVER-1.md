# Hand over client work to another machine

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- A person can give a client project to another FDE. The decisions and lessons from the agent's handoff notes are saved in the repo, so they survive a laptop change.
- The guide gets a short Hand over section: push everything, reassign each item, continue on the new machine.
- Any ready item can be merged from any machine, not only from the machine that started it.

## Why

Handoff notes are kept in a folder that is never committed, so they stay on the old laptop. A ready item's merge record is kept in the same local folder, and forge merge also needs a local checkout of the item. A second machine therefore cannot merge the item, and the status line says the person who started it must merge it from their own machine.

## Done when

1. **A ready item started on laptop A can be merged with forge merge from laptop B, with no local checkout on B and no record copied by hand.**
2. **The decisions and lessons part of the handoff notes is in a committed file in the repo, and a new clone can read it.**
3. **The guide has a Hand over section that names the three steps, and the coordinator skill file (src/forge/templates/skill.md) says the same thing.**

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
