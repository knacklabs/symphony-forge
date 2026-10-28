# Log every API request safely in client apps

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- Each client app writes one log line for every API request, with the method, route, status, duration and request id, and never the query string.
- Each client app has a log level setting that decides which log lines are written.
- Passwords, tokens, secrets, keys and authorization values are removed from log details in both the TypeScript and Python starters.
- Error alerts come from Mainline reading error log lines by their error id, so client apps need no error-tracking vendor.

## Why

Client apps in both starters already write some log lines, but not one line per API request, there is no log level setting, and secret values are not removed from log details, so request outcomes cannot be seen safely.

## Done when

1. **A new client app in either starter writes one log line per API request, and that line holds no query string.**
2. **Setting the log level to error hides the info lines in both starters.**
3. **A password, token or authorization value sent in a request never appears in any log line in either starter.**
4. **An existing client app gets the same request log line and value removal in both starters when it upgrades.**

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
