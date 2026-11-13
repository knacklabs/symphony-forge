# /forge opens a small live pane of what is running on this laptop

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- Typing /forge always opens one small live pane, in the Claude desktop app and in the terminal, at any width.
- The pane lists the builds, tests and reviews running now on this laptop, with round and time, names the repo on rows from other repos, and puts one line at the top when anything needs the person.
- The skill named forge in every client repo gets a new name, so /forge is free for the pane.
- The events that start agent turns and the line above the prompt are removed for now; the board copy, stage chains and next-command button are deleted.

## Why

/forge never opens in any Forge repo today. Its start step asks Claude Code for the command name /forge, the repo's skill with that name blocks it, and the pane stays on Loading. Behind that, the mod reads the full board every 10 seconds, which takes 16 seconds and 14 MB in a busy repo.

## Done when

1. **Typing /forge opens the pane within 300 ms in any repo, on the first try, and never shows Loading after its first content; one small command answers its reads; where no pane can be drawn, the same lines print as text.**

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
