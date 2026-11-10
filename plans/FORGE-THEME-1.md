# One shared design system and theme, set in Claude and checked at close

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- Forge keeps its design system (the shared parts and the theme names) once, in its code.
- For each client, the agent builds that client's Claude design system from Forge's code.
- Sales sets the client's theme (colours, fonts, corner size, spacing) in Claude, and the agent copies that theme into the prototype, so the prototype matches the approved design.
- Close reports when the app's theme differs from the approved design. The later step that picks the look in code goes away.
- A new client repo gets this when it starts. An existing client repo gets it when it upgrades to the new release and syncs.

## Why

The look is picked in code at a later step, so the prototype can drift from the design the client approved, and nothing reports the difference.

## Done when

1. **The shared parts and theme names live once in Forge's code, and each client's Claude design system is built from them.**
2. **Sales sets a client's theme in Claude, and the prototype shows that theme.**
3. **Close reports when the app's theme differs from the approved design.**
4. **The code step that picks the look is gone for new and upgraded client repos.**

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
tasks that need them wait for that task through After and then own only their files. Tests: the
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
