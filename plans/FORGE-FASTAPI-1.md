# FastAPI starter for Python backends

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- A new client app whose backend is Python starts from a runnable FastAPI app with the TypeScript starter's fixed rules: one app split into modules, each module owning its tables, other modules using it only through its public service, uv, SQLAlchemy with Alembic on Postgres, and tests end to end first (pytest HTTP tests on a real database, Playwright for the React UI).
- An import-linter contract fails the tests when one module imports another module's internals, as Nx's module-boundary lint does in the TypeScript starter.
- forge init picks this starter only when the owner asks for a Python backend, and the constitution lists the fixed rules without asking about them.
- An existing client app keeps its stack, Dockerfile and test command on upgrade or sync.

## Why

A Python backend has no starter today, so each Python client app starts from nothing and its module, database and test rules depend on the agent that builds it.

## Done when

1. **A new client app that asks for a Python backend gets a FastAPI app from forge init whose test command runs API tests on Postgres, browser tests and the module-boundary check, and all of them pass.**
2. **An existing client app's stack, Dockerfile and test command are unchanged after upgrade.**

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
