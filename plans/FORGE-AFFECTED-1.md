# Tests run once, and only for the parts a change touches

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- The pull request check of a client app runs lint, typecheck and tests only for the parts a change touches, compared with the merge base, and its log names them. Close does not run them again on the laptop; it waits for that one check.
- Forge picks the touched parts in this order: Nx affected projects where the workspace defines its targets; else each runner's own selection (Forge's related pytest picker, vitest changed, jest changed since, Playwright only-changed); a chained command is split and each step gets its own selection; only a step with no selection runs whole.
- A Python app without Nx gets its related pytest tests, plus ruff and mypy on the changed files.
- The full suite runs nightly and before sign-off, as it already does when tests run in CI.
- Forge's own repo works the same way first: its related tests run once in the pull request check, not in close as well, and the starter app smoke runs are chosen by the area a change touches.
- New client repos get it at init. Existing client repos get the CI file on sync; the agent asks before it changes forge.toml.

## Why

Client developers wait about 40 minutes at close. With the default setup close does not run tests on the laptop; it waits for the pull request check, and that check runs the starter's whole test script (lint, typecheck, API, hooks and Docker browser tests) for every change, because the script is one chained command that Forge cannot select from. The starters' Nx setup cannot select yet: only the two app projects define targets, and the Python starter has no Nx. In Forge's own repo the same related tests run in the builder, in close and in CI, and any template change starts every app smoke run.

## Done when

1. **A change to a client app runs lint, typecheck and tests only for the parts it touches, once, in the pull request check, and the log names those parts.**
2. **A Python app without Nx runs only its related pytest tests and checks the changed files.**
3. **The full suite runs nightly and before sign-off.**
4. **Forge's own repo runs a change's related tests once and picks app smoke runs by the changed area.**
5. **New client repos get it at init; existing client repos get the CI file on sync, and the agent asks before forge.toml changes.**

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
