# A person can skip the model review, and forge.toml sets the review rounds

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- A named person can close an item without the model review. Their name and reason show on the pull request. Tests, CI, the design checks and the merge step still run.
- Close refuses the skip when a review has already blocked the item. Agents use the skip only when a person asks for it.
- Two forge.toml settings set the rounds before Forge asks the person: one for a plan's cold read and one for a task's review, each one or two, both two by default. Fixes keep one review round. At the limit Forge still asks for one more round, split or accept.
- This replaces the rule that every item gets a model review (decision 0092); the owner chose this on 6 Nov 2026.
- New client repos get the skip and the settings at init. Existing client repos get them on upgrade.

## Why

Small changes such as version bumps, docs and generated files wait for a model review that adds little, and no close option skips it. The round limits are fixed in code, so a team cannot choose one round for its cold reads or its task reviews.

## Done when

1. **Close with a named person and a reason skips only the model review, and the name and reason show on the pull request.**
2. **Close refuses the skip after a blocking review, and tests, CI, the design checks and the merge step still run on a skipped item.**
3. **forge.toml sets one or two rounds for the cold read and for task reviews; at the limit Forge asks for one more round, split or accept; fixes keep one round.**
4. **skill.md and brief.md describe the skip and the settings, and tell agents to use the skip only when a person asks.**
5. **Tests cover a new client repo and an existing repo adopted on an earlier release.**

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
