# Client apps can deploy several services from one repo

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- Each client repo keeps a services list that the deploy platform reads. Each service has a name, a Dockerfile path, a role or start command, a port, a health path, and one exposure: public at the main address, public at its own subdomain, or internal only.
- New apps from the starters list one public service. An existing app that Forge adopts gets a list the agent writes from its Dockerfiles.
- The deploy guide names the list and the subdomain that the deploy skill already asks for.

## Why

The deploy guide and both starters assume one root Dockerfile, container port 3000 and GET /health. An app with several Dockerfiles, such as an API, a web app and a worker, cannot be described to the platform, and the planned jobs story (one image run with APP_ROLE set to api, worker or all) has nowhere to say which service runs which role.

## Done when

1. **A new starter repo's services list has one public service on port 3000 with GET /health, and the deploy guide names the list.**
2. **An existing repo with two Dockerfiles, adopted by Forge, gets a list with both services, one of them internal only, and the agent confirms it with the owner.**
3. **The deploy skill reads the subdomain for each public service from the list, not from the root Dockerfile.**

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
