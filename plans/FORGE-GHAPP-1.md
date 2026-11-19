# Give each client its own GitHub app for Forge's GitHub work

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- During setup, each client creates its own Forge GitHub app inside its own GitHub organization, and the client keeps the app's keys.
- Close, merge, land and runner work act through that app, using its own identity and hourly request budget instead of the owner's personal sign-in.
- A later story sets up and checks GitHub's standard runner tool for the client, and Forge builds no runner manager of its own.

## Why

Forge's close, merge and land run on the owner's personal GitHub sign-in, and at one client that sign-in hit its 5,000 requests an hour several times a day on 18 and 19 November 2026.

## Done when

1. **forge doctor shows which identity close, merge and land use for a repo and how much of its hourly budget is left.**
2. **A new repo gets its app at init, and an existing repo gets it through one setup step after upgrading, with both paths written down in the plan.**
3. **The app's keys stay with the client, Forge never writes them into a tracked repo file, and the plan says where the laptop reads them from.**

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
