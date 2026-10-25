# Client apps can split into services and frontends later without a rewrite

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- A new TypeScript client app splits its shared code into shared/util and shared/ui, and its core into core/server and core/web, and each module gets contracts, server and web libraries.
- The module boundary lint allows a module to reach another module only through its contracts, and module web libraries never import each other.
- A new Python client app keeps its API and web types generated from OpenAPI, with the same web library rule.
- An existing client app keeps its current layout on upgrade.

## Why

The starter's shared library mixes every module's schemas with general helpers, and each module's screens sit in the web app folder, so splitting services or frontends later means a rewrite. It must land before the feature command's parts, which then copy three libraries for each feature.

## Done when

1. **A new TypeScript client app builds with the split libraries, and its tests fail when a module imports another module's server or web files, or when one module web library imports another.**
2. **A new Python client app's web types still come from its OpenAPI schema, and its tests fail on the same web library import.**

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
