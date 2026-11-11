# Stop committing generated API types in Python apps

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- New Python client repos start with the API contract file and its generated TypeScript types not committed; they are made at build, type check and test time.
- New TypeScript client repos get the same rule for any generated file; the TypeScript starter commits none today, so nothing changes there.
- Existing Python client repos keep their committed files after upgrade and sync; Forge changes no app file, and the guide gives the agent the steps to move the app over in one small change.

## Why

Bug 1529. Committed generated Python API files make every API part list the same two files in its scope, so parts that could run side by side wait for each other.

## Done when

1. **The Python starter and its guidance no longer commit the API contract file or its generated types, and the test and type check create them first.**
2. **The TypeScript starter and its guidance are checked and give the same rule for any generated file it has.**
3. **An existing Python client repo upgraded and synced keeps its committed files, with no app file changed by Forge.**
4. **The guide gives the agent steps to move an existing Python app to the new layout in one small change.**

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
