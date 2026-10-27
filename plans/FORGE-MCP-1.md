# Client apps ship an MCP server so agents can use their features

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- Every new client app, from either starter or from forge init, starts with an MCP server, a standard way for AI agents to call an app's features as tools.
- Each feature that the feature command builds adds its own agent tools, such as list, get, create, edit, delete and restore, and each tool checks the same permission as the app's own screens.
- Agents, including Gantry Cloud agents through Mainline, sign in with the app's sign-in or a Mainline key. Calls are rate limited.

## Why

Agents cannot use a client app's features today. Each feature is only reachable through the app's screens and API, so an agent would have to be hand-wired for every app.

## Done when

1. **A new TypeScript or Python starter app lists an MCP service in services.toml, and that service starts and returns its tool list.**
2. **A feature built by the feature command gets its tools, and each tool refuses a call from a person or key that lacks the feature's permission.**
3. **A tool call with no valid sign-in or Mainline key is refused, and calls over the rate limit are refused.**
4. **Tests run the MCP service and each tool, and an existing app gets the command and guide text on upgrade but no new service file.**

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
