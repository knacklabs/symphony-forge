# Clients choose which added-work review notes hold their work

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- A client sets a minimum score in forge.toml. An added-work review note below it is recorded as a known limit and does not block.
- A client lists kinds of note that always block, such as legal must-haves and safety steps, whatever their score.
- Each review note shows its Gain, Work and Harm scores next to its reason, so the owner can see why it held or passed.

## Why

Review holds work by a fixed bar that clients cannot change, so a small extra check for a rare case can block a change the owner would ship. The bar already scores notes on Gain, Work and Harm and records notes below it as follow-ups, and close already prints the scores. The new part is the client setting and the always-block list. The owner's formula counts how often a case happens, which review does not measure today, and its cost scale is 1 to 3 where Work is 1 to 5; the plan must decide how Gain and Work map onto it.

## Done when

1. **A minimum score in forge.toml makes an added-work note below it a known limit instead of a blocker.**
2. **A list of always-block kinds in forge.toml blocks a note of that kind at any score.**
3. **Each review note shows its scores beside its reason.**
4. **A new client repo and an existing client repo upgraded to this release both get the setting, with today's bar as the default until they set it.**

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
