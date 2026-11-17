# Run work rounds on a second Linux machine

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- A coordinator can send Codex and Claude work rounds to a Linux machine listed in forge.toml, with a slot count for each host.
- The remote machine builds, tests, commits and pushes. Threads, locks, round records and handbacks stay in the coordinator's checkout, and the result comes back like a normal round end or handback.
- A remote round refuses to start, with a plain message, when its clone or branch is behind or has local changes, so two machines never write the same item.
- A remote round is counted only against that host's own slots. The Mac's load limit of 1.5 per core no longer holds it.

## Why

Every work round runs on the coordinator's Mac, and new rounds wait once load passes 1.5 per core, while CI machines sit idle. There is no supported way to run a round's worker on another host that has its own clone, signed-in Claude Code and Codex, and the round's branch.

## Done when

1. **The owner can list a Linux host with a slot count in forge.toml, and a round sent there runs on that host while its state stays in the coordinator's checkout.**
2. **The result of that round (round end or handback) appears on the board the same way a local round's result does.**
3. **A round sent to a host whose clone or branch is behind or dirty is refused before any work starts, with a plain reason.**
4. **While the Mac is at its load limit, a round sent to a listed remote host still starts when that host has a free slot.**

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
