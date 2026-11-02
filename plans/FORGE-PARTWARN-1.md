# Warn instead of stop for story parts over 400 lines

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- A story part over 400 changed lines shows a warning when its task starts, and close no longer stops to ask the owner.
- The planner splits such a part before building, and the planning guide says so.
- AGENTS.md principle 4 (Four simplicity principles, Rules are stated, not policed) becomes three levels: Forge does the right thing by default where it can; it refuses only when a mistake costs a lot or is hard to undo; it states a rule only when a mistake is cheap and something later catches it.

## Why

A part over 400 lines stops close and asks the owner, and the stop cannot be cleared: open issue 960 shows that accept is refused and the allowance does not release it. Each stop costs a builder round.

## Done when

1. **A part over 400 changed lines closes without an owner question and shows a warning at task start, and a story approved before the change keeps working.**

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
