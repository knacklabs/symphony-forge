# Build and fix rounds raise their effort after a failure

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- Build, fix and lite start at low effort by default: Codex gpt-6.1-sol at low and Claude claude-sonnet-5-5 at low.
- A round after a verified failure (red tests, a blocking review finding or a failed check) runs at the top effort: Codex high, Claude xhigh.
- A repo's own model choices stay; only the effort changes from round to round, in codex, claude and split worker modes, by the tool that runs the round.
- Reviews, cold reads and sign-off keep their fixed effort; in Claude-only repos, cold reads and reviews default to claude-sonnet-5-5 at high instead of Opus.

## Why

Build and fix rounds run at one fixed effort, so a retry after a failure gets no more reasoning than the attempt that failed, while every first attempt pays for the higher effort.

## Done when

1. **A first build, fix or lite round runs at low effort, and a round after a failed test, blocking review finding or failed check runs at the top effort, in codex, claude and split modes.**
2. **A repo's own model choices stay, and only the effort changes from round to round.**
3. **Reviews, cold reads and sign-off keep their fixed effort.**
4. **In a Claude-only repo, cold reads and reviews run on claude-sonnet-5-5 at high effort, not Opus.**
5. **Each round's run record shows its effort and round number, so a week of cost and round counts can be compared.**

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
