# Client app designs stop looking machine-made

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- Every client app gets one fixed baseline list: a collapsible sidebar with an icon rail, a top bar with search, one page title shown once, one spacing scale, one type scale, one main button per view, clear labels and error text, empty, loading and error states, a select or a search box chosen by how long the list is, phone-width layout, plain wording and realistic sample data.
- Before a design canvas is shown, and again at close, the design checker from impeccable and a few small Forge checks run.
- Each design canvas is also checked as screenshots at desktop and phone width before it is shown.
- Each client app gets its own look, chosen from five facts in the client's notes and written into a DESIGN.md file, with fixed rules for contrast, text size, focus and states.
- App screens use the quieter app mode of impeccable.
- A new client repo gets all of this when it starts. An existing client repo gets it when it upgrades to the new release, and its existing apps are checked only on the files a change touches.

## Why

Client app designs and canvases look generic and machine-made. The app baseline covers screens, states and the app shell, but it has no spacing scale, no type scale, no per-app design file, and no screenshot check at desktop and phone width. Its visual check is one review pass at the end.

## Done when

1. **A new client app starts with the shared baseline list, its own DESIGN.md, and the design checker and screenshots at desktop and phone width before any canvas is shown.**
2. **Close stops a design that fails the design checker or the small Forge checks.**
3. **An existing client app is checked only on the files a change touches.**
4. **Forge's own tests show each rule working on a new client repo and on an existing client repo.**

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
