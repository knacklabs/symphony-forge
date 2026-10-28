# Client apps are ready for agents from day one

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- Every action in a client app goes through its service and permission check, whether it comes from a screen, an agent over MCP, or a later in-app agent.
- Every change records the person, and for an agent it also records the agent acting for that person.
- Every write takes a retry key, so a repeated request makes no second record.
- Reports come from summary tables built from the main tables, and typed results name their units.
- The rules sit in the conventions and the database skill, each with its cheapest check, and the FDE is not asked about them.

## Why

Much already ships, but change records name only the agent account, only MCP creates take a retry key, units are not stated, and the rules are spread across several guides. Three points conflict with shipped rules and need the owner's choice first: agents acting for a person, retry keys on every write, and reports always from summary tables.

## Done when

1. **A new client app and an existing client app each show every rule in the conventions and database skill, each rule with a named check, and the FDE is never asked about them.**

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
