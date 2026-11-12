# Builds and tests run on separate cloud machines when the laptop is full

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- A repo names one provider for these machines in its settings file, and each developer uses their own account with that provider.
- Each developer signs in once inside a kept machine to Claude Code, Codex and GitHub. Forge never sees or carries a model login.
- The feature is off by default, and the agent turns it on per repo. Runs on these machines show their minutes in the machine view, and a stop command ends one.

## Why

Every build round and test run waits for one of the laptop's few places, so an idea reaches a ready pull request slowly.

## Done when

1. **With the feature on, a build round or test run that would wait for the laptop starts on a machine at once.**
2. **When a provider fails, the run goes back to the laptop's line with one line saying why.**
3. **Turning the feature off deletes the kept machines, and the model review stays on the laptop.**

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
