# Close shows what a changed screen looks like

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- When a client UI change closes, Forge opens each changed screen at desktop and phone width, in light and dark, and in its empty, loading and error states.
- Close reports overflow, cut text, low contrast and layout jumps, each with its screen, width, theme and state.
- A model reads the saved screenshots only before a demo or sign-off, never at close.

## Why

Close checks only read code, so a screen that overflows at phone width, cuts text, fails contrast in dark mode or breaks in its error state can close and reach the client unseen. The design canvas screenshots already merged on 6 Nov 2026 cover only design canvases at two widths, not built screens in their states.

## Done when

1. **A UI change that closes lists its rendered problems per screen, width, theme and state, or says none were found.**
2. **Overflow, cut text, low contrast and layout jumps are each named with the screen and state where they occur.**
3. **A new client repo gets the check on its first UI change, and an existing client repo gets it on its next UI change after upgrading.**
4. **Close makes no model call; a model reads the screenshots only for a demo or sign-off.**

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
