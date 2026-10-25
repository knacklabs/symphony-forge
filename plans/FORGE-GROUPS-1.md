# Split any test runner's CI tests into parallel groups

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- A client with a slow test suite on any runner, such as vitest, can set the number of parallel test groups in forge.toml, and the test command gets each group's number filled in.
- A repo that already gets the six automatic pytest groups keeps six after upgrade, and a new repo starts with one group.
- Each group runs only its own share of the related tests and never counts another group's pass as its own, even when the groups run one after another on one self-hosted runner.
- A test listed to always run passes in the group that owns it and does not fail the other groups.

## Why

A client's 2,300-test vitest suite went past the CI job's fixed 30-minute limit on a 2-core runner. Only pytest repos are split automatically today, so other test runners have no way to share the load. Four groups would take about 8 to 10 minutes.

## Done when

1. **A forge.toml groups setting splits a pull request's test job into that many parallel jobs for any test runner.**
2. **The test command receives the group number and the group count, so a vitest command can use its own shard flag.**
3. **A pytest repo upgraded without a groups setting still runs six groups, and a new repo runs one.**
4. **Groups run on one machine never report another group's pass as their own.**
5. **Always-run tests pass in their owning group only and do not fail the others.**

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
