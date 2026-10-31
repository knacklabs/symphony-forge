# Starter ships no screens

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- New client apps from forge init get the API, the rules, the skills and the guide, with no sign-in, Members, Projects, Change history, Join or web shell screens, in both the React and Python starters.
- Existing client repos keep their app code when they upgrade.
- Forge's review reports any new screen added to its templates, and the rule lives under the review rules.

## Why

Each client app is built in its own design, so the starter's screens are wrong for every new app and the client must remove or rebuild them before its own design can start.

## Done when

1. **A new app from forge init has no screen files in either starter, its API tests and starter smoke run still pass, and an existing client repo's app files are unchanged after upgrade.**

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
