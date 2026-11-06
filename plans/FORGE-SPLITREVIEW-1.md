# After a conflict, close reviews only the conflict fix, and plans keep task files apart

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- After a task brings in main and fixes a conflict, close reviews only the lines that resolved the conflict, keeps the earlier clean review, and still runs all tests in full. A merge with no conflict still needs no new review, as it does today.
- The planner searches the code for each task's Scope before writing it, and the plan check refuses two tasks whose Scopes can touch the same file unless one waits for the other through After. Shared names go to the first task or to a small last wiring task.
- New client repos get both at init. Existing client repos get both on upgrade, and a story already in flight gets the refusal at its next plan check, with a plain next step.

## Why

Close reuses an earlier review only when the whole branch diff is unchanged, so a task that fixes a conflict after another task merged gets a full new review, which takes time. Task start checks file overlap only against started tasks, and with stacking on by default an overlapping task is usually stacked, not refused, so plans with shared files reach building and cause the conflicts. The worker brief also allows edits outside Scope, so some conflicts come from files no Scope check can see. Forge already needs Git 2.38 or newer for git merge-tree, which also has git show --remerge-diff, so the review step adds no new Git minimum.

## Done when

1. **A task that merges main with a conflict is reviewed only on its conflict fix, and its tests still run in full.**
2. **A plan with two tasks whose Scopes can touch the same file, and no After link between them, is refused before approval, and the refusal names both tasks.**
3. **Stories already in flight get that refusal at their next plan check with a plain next step; new and existing client repos both get both changes.**

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
