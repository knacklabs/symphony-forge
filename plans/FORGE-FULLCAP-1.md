# Waiting parts start and merge on their own once the part before them is done

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- After a part merges, its stacked parts that already have a clean review also merge, and each part that can now start gets one line.
- The coordinator cannot end its turn while Forge lists a part that can start and none is running. A part that waits on a person does not count.
- After every merge, the coordinator starts each listed part in the background before it replies, on Claude and on Codex.
- Forge lists a part as able to start only when starting it would succeed.
- New client repos get all of this at init. Existing client repos get it on upgrade.

## Why

After a part merges, nothing starts the parts that waited for it unless the coordinator reads the next-step list and starts them by hand. The merge output for a stacked part names a close step, not a merge, and nothing calls the merge again. Forge already has a run that merges stacked parts base-first (forge land --all, in the land module), but nothing calls it after a merge. A stacked part still needs its own close step to move onto the default branch and wait for checks, so merging it inside the base merge is a longer run, not one quick step. The turn stop check is a gate on every turn end, so it needs a loop guard and a cost check against the speed rules.

## Done when

1. **After a base part merges, its clean stacked part merges, or its line says it can now start, with no extra step from a person.**
2. **A test shows that a part listed as able to start is one that task start accepts, including the case where the base lacks the default branch's merge.**
3. **A test shows the stop check holds a turn while a startable part is idle, and lets it end when only waits on a person remain.**
4. **Tests cover one new client repo and one existing repo adopted on an earlier release.**

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
