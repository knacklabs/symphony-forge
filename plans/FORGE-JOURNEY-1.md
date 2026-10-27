# Agents teach the seven-step journey to new users

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- The seven-step journey is written once in the shipped guide, with one plain say-this sentence per step, and the README journey page matches it.
- After forge init, the agent explains the seven steps and asks for the first input.
- Each forge next starts with one line that names the current step out of seven, such as Step 3 of 7: canvas design, then the next step.
- When someone asks what they can do or seems unsure, the agent shows the plain phrases for the current step.
- When Forge refuses something, the agent explains the reason and the fix in plain words, and offers to file a Forge bug when the refusal looks like a Forge fault.
- New repos get all of this at init; existing repos get it on upgrade with forge sync.

## Why

New users learn the journey from the owner. The repo has no single journey yet: the README's From idea to production table has ten stages, the shipped guide's Prototype section describes a different route, and forge next has no journey step to show, because its stage names belong to each item, not to the whole journey.

## Done when

1. **In a new repo, the agent can list the seven steps with a say-this sentence each, and the first forge next names the current step out of seven; an existing repo gets the same after forge sync.**

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
