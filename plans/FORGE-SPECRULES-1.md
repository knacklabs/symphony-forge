# Client specs state each rule once

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- Spec authors write each rule once as a numbered line, and the validation, UAT and acceptance lines refer to it by its number instead of repeating it.
- When a decision changes a rule, Forge lists every spec line that refers to that rule before review, in the same change, so the copies cannot drift.
- A new client repo gets the rule-line template at init; an existing client repo gets the check and guide text on upgrade, and its old specs are flagged once with the lines that repeat a rule.

## Why

Client specs restate one rule in several places, so a decision that changes the rule updates one copy and the others drift, and the same rule keeps breaking (client issue 1145). Forge's shipped spec template has no rule IDs.

## Done when

1. **A spec that writes a rule once and refers to it by ID in its validation, UAT and acceptance lines passes read and confirm.**
2. **Changing a rule in a decision lists every spec line that refers to it before review.**
3. **An existing repo's old specs are flagged once on upgrade, listing each repeated line, and a new repo gets the template at init.**

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
