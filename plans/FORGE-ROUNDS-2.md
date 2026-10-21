# Owner decides before open findings drop at the round limit

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- At the round limit, an open finding that is not P0 stops the item and asks the owner to choose one more round, split, or accept as follow-ups. Nothing moves to follow-ups without the owner's answer.
- An open P0 never stops the item at the limit. The worker keeps fixing it until the review or read is clean.
- forge work refuses an item that has an unanswered stop and shows the same question that close shows.
- The guide, the worker brief and the release notes state the new rule. New repos get it at init; existing repos get it on upgrade and sync.

## Why

Today a cold read moves every open note that is not P0 into follow-ups at round two without asking the owner. A code review at the limit stops for any blocking finding and for a P0 too, although the owner wants a P0 kept in the worker's hands. forge work does not check for a waiting stop, so a worker round can run on an item the owner has not answered. With no owner stop on a P0, nothing in the rule caps a P0 the worker cannot fix.

## Done when

1. **At the limit, a read or review with an open non-P0 finding stops and asks; with an open P0 it does not stop, and the worker fixes it.**
2. **forge work refuses while a stop waits, showing the same question close gives.**
3. **The guide, the worker brief and the release notes state the rule, and init, upgrade and sync each deliver it.**

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
