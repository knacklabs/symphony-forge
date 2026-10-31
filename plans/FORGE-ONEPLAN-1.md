# One prototype approval, then the agent builds every record type

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- The owner approves one prototype plan, which lists the record types, their fields, the architecture choices and who may do what with each record type. The design canvas, working-build, constitution and architecture-record approvals are no longer separate steps.
- After that one approval, the agent builds every record type with the feature command without more questions.
- The agent writes about 20 realistic demo records per record type, in the client's own words, with no real personal data. They are for the prototype and tests only.
- Each Done-when item becomes a demo step that opens on the client's business task. The agent runs the steps in a browser and saves a screenshot of each one, kept out of code review. The client ticks each step to sign off.

## Why

The owner's approval steps are spread across four separate gates, and the client's sign-off is not tied to the business tasks the prototype has to do. The plan must also change the constitution rule in FORGE-CONSTITUTION-1 and the sign-off spec in docs/specs/prototype-signoff.md, which currently require those separate approvals.

## Done when

1. **One prototype plan approval replaces the four separate approvals, and the agent then builds every listed record type without asking more questions.**
2. **Each record type has about 20 demo records in the client's words, with no real personal data.**
3. **Each Done-when item runs as a browser demo step with a saved screenshot, and the client ticks each step.**

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
