# Guides and starters agree

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- The paging, currency, UI library and environment name in the guides match what the starters actually use.
- Prettier is removed from the starters, and the guides stop saying it runs.
- The default setup notes name only the parts that are built, and each names the story that builds it.
- Client apps get rules for background jobs and schedules, outgoing web calls, and uploads, with the upload settings left for Mainline to supply later.
- Both starter READMEs get a when something breaks section.
- Starter containers run the app as a non-root user.
- Dependabot security alerts are on, with no update pull requests.

## Why

The shipped guides and starters contradict each other, promise parts that are not built yet, and lack rules for jobs, outgoing calls and uploads.

## Done when

1. **A new client app's guides and starter code agree on paging, currency, the UI library pin and environment names.**
2. **A new client app's starter containers run as a non-root user, and both starter READMEs have a when something breaks section.**
3. **A new client app has no Prettier claim, and its setup notes name only built parts.**
4. **A new client app gets rules for background jobs, schedules, outgoing web calls and uploads.**
5. **An existing client app gets the same changes on upgrade, and each change has a test for a new app and for an existing app.**
6. **Dependabot security alerts are on with no update pull requests.**

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
