# Forge supports only its newest release

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- Repos pinned to the release just before the newest one can upgrade directly; repos pinned to any older release are refused with one line telling them to upgrade through each release in order.
- Repos on an older pin get one line on every command except upgrade telling them to upgrade, and the shared lanes and the /forge pane read only the current data format.
- Forge's own tests check each rule on a new repo, plus one test of the upgrade from the release before and one test of the refusal on an older pin for the whole suite. The earlier-adopted test cases and old-release fixtures are removed (470 of 832 test files), and the review rule in AGENTS.md and the standards are rewritten to match.
- forge migrate for a copied-in old Forge stays one more release with a notice that it will be removed, then it is deleted.

## Why

Forge keeps working for repos pinned to many older releases, so each rule is tested against old repos too and that test load grows with every release.

## Done when

1. **Older pins are refused with the upgrade-in-order line, and the test suite keeps only new-repo cases plus one upgrade test and one refusal test in all.**
2. **The release that makes the cut ships only after the one client repo in daily use is on v1.2.40, the last release that upgrades from any older one.**

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
