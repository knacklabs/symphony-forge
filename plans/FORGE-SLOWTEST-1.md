# Faster tests for repos with one combined test command

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- When a repo's test setting is one combined command, Forge proposes a faster quick-test setting that runs a type check and the changed unit tests, and the agent asks the owner, then sets it.
- On Windows laptops, heavy browser tests stay out of the worker's local test loop by default, while the pull request check and the nightly full run still run them.
- A failed nightly full run shows under Needs you on the board and in the next-step output, not only as one line.
- New and existing client repos get all three through the release, the sync and the guide.

## Why

Bug 1530. With one combined test script, Forge cannot pick related tests, so every worker test run and every pull request check runs the whole suite, taking 11 to 24 minutes on Windows laptops, and browser tests fail there for reasons unrelated to the change.

## Done when

1. **For a combined test script with no quick-test setting, forge doctor, init and adoption propose one, and the agent sets it after asking.**
2. **Heavy browser tests are skipped in the worker's local Windows test loop by default, and the pull request check and nightly full run still run them.**
3. **A failed nightly full run appears under Needs you on the board and in the next-step output.**

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
tasks that need them wait for that task through After and then own only their files. Tests: the
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
