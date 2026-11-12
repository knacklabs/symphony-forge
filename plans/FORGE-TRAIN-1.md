# Merge several ready items in one train

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- When several items are ready at once, Forge merges them together in one pass instead of one after another.
- The combined check runs once. If it fails, Forge finds the item that broke it, sends only that item back for more work with the failure, and runs the train again with the rest.
- Items with a real merge conflict between them wait and merge one at a time.
- Each item keeps its own record and outcome. The merge = "agent" setting still decides who merges.

## Why

Each merge moves the main branch, so every other waiting item with clashing files must merge main again and rerun the full pull request check, 45 to 60 minutes each. A team reported about 11 merges in a day, most of the wait in these reruns, and one item went through this cycle about ten times.

## Done when

1. **With three to five ready items, one combined check runs for the group instead of a full check for each item.**
2. **A failing combined check sends only the item that broke it back for more work, and the other items run again as a new train.**
3. **Items with a real merge conflict merge one at a time, outside the train.**
4. **It works with merge = "agent" and with checks run in CI, in both new and existing client repos.**

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
it may change. Before writing each Scope, search the code for the files the task needs. The plan
check refuses two tasks whose Scope paths have the same prefix up to the first wildcard, unless
one waits for the other through After, directly or through another task; it names both tasks.
Paths with a segment named `tests`, `test`, `__tests__` or `spec` do not cause Scope overlaps
and can be shared without an After link. Explicit After links still apply.
When tasks need the same production file, put it in the first task's Scope with the shared names and stubs;
tasks that need them wait for that task through After and then own only their files. Keep a file
that a script can make at build time out of the repo and out of every Scope; when the repo keeps such
a file on purpose, give its change to one part that the others wait for. Tests: the
tests it adds or changes. After: the tasks it waits for. When two tasks share a function, field,
file format or command, the first task pins it: it commits the shared names and stubs plus one
test that crosses both sides, and the tasks that use it list it under After. Split tasks so each
owns its files; shared lines (command table, guide list, registry) go to one task or a small last
wiring task; After only when a task needs another task's code. The
Developer column is optional: the lead fills or changes a GitHub username here, below For the
builders, without another approval. Leave it blank for an unassigned part. Forge next uses
the caller's GitHub login; another developer may start it with a warning. Existing tables
without Developer still work. The moving-parts line stays last: "none", or each new dependency, service, datastore,
queue, background job or abstraction layer, with the Done-when item that needs it. -->

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|

New moving parts: none

## Notes
