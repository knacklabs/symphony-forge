# Tests run once per change, in one place per repo, and CI is optional

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- Each repo picks one place for its change tests: its CI, or the laptop. A repo with no GitHub CI can ship, with an empty checks list; close's clean review and its laptop test result are then the merge gate. A repo with CI no longer runs the tests twice.
- Each change runs only its related tests plus lint and type checks, in that one place. The pull request's CI run does the same, not the full suite.
- The full suite runs nightly on main, in a scheduled GitHub workflow where the repo has CI, or on the laptop when it is quiet. A failed night opens a fix that names the failing tests.
- A release or a client sign-off waits for a green full run on the current main. Everyday merges never wait for it.
- New repos get CI with a GitHub remote, the laptop otherwise. Existing repos move to the new setting on upgrade, the upgrade message says so, and the settings file can switch back.

## Why

Every change runs its tests twice, on the laptop at close and again in the pull request's CI with the full suite, close refuses an empty checks list, and the merge waits for CI, so a repo without GitHub CI cannot ship.

## Done when

1. **A repo with no GitHub CI and an empty checks list closes and merges a change on its laptop tests alone.**
2. **A change's related tests, lint and type checks run once, in the chosen place only, and never the full suite.**
3. **A failed nightly run opens a fix naming the failing tests, and a release or client sign-off is refused until a full run on main is green.**

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
