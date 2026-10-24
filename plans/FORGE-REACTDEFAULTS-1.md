# Four frontend defaults for new client React apps

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- A new client React app starts with React Compiler on, and its review flags hand-written memoization in its own code.
- A new client React app follows a composition rule that its review checks: layout through children, shared-state parts as compound components, logic without markup in custom hooks, and no boolean props that switch a component between modes.
- Filters, tabs, sort order and the page number of a list live in the web address, so a shared link or a page refresh shows the same view.
- Each route in a new client app has its own error page, so a crash on one screen shows that screen's error page and the other screens keep working. React Router stays.
- An existing client app gets these rules for new code only; its current code is not changed or flagged.

## Why

The starter sets no frontend defaults beyond its layout. Its projects page writes memoization by hand, only that page keeps its list in the web address, no rule says how components are composed, and no route has an error page, so one crash on a screen can blank the whole app.

## Done when

1. **A new client React app starts with React Compiler turned on, and its review flags a change that adds useMemo, useCallback or React.memo to the app's own code, but not the shadcn/ui copies.**
2. **Its review flags a component that breaks the composition rule.**
3. **Reloading or sharing a link to a filtered, sorted or paged list shows the same view.**
4. **A crash on one route shows that route's error page, and the other routes still work.**
5. **An existing client app's current code is not flagged; only new code is checked.**

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
