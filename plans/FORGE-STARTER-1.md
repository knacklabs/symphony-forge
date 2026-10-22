# Starter app for new client React apps

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- A new client React app starts from a runnable Nx workspace with React (Vite, React Router) and NestJS on Postgres, with sign-in, one example entity carried end to end, tests and CI, and an app shell built from shadcn blocks.
- The stack page changes from npm workspaces to Nx for new apps.
- A close check refuses a second UI library and hand-made copies of shadcn components, and review reports a custom UI piece as P1 unless the change says why shadcn cannot do it.
- An existing client app keeps its own stack and code on upgrade; the new check and review rule apply to its later changes, and an app that already has a second UI library is not blocked for it.

## Why

Each new client app starts with no code, so sign-in, the app shell and the test and CI setup are rebuilt by hand, and the stack page still says npm workspaces while the skill already says Nx.

## Done when

1. **A new client React app runs locally after setup, and its tests and CI pass on the first commit.**
2. **The app has sign-in, one example entity from the database to the screen, and a shell with a collapsible sidebar, a top bar with Cmd+K search, auth pages, settings and a 404 page.**
3. **The stack page names Nx for new apps, and the stack default in the skill matches it.**
4. **A close check on a client app fails when it adds a second UI library or a hand-made copy of a shadcn component.**
5. **Review reports a custom UI piece as P1 unless the change says why shadcn cannot do it.**
6. **A new repo and an existing client repo adopted on an earlier release each get a test for these rules.**

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
