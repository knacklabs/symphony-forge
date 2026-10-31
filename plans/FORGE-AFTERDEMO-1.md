# After a demo: waiting items show in the app, notes become changes, and releases get a backup before Promote

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- Each client app user sees records waiting for their action (an approval or an assignment) in an in-app notification list, with a count by default. Email comes later through SNS, not in this story.
- The FDE gives the agent demo notes or a call transcript. The agent splits it into separate changes and shows one list. After one FDE OK, each change goes through forge start.
- Each release that adds a database migration is marked, so Mainline takes a backup at Promote. Mainline does the backup and the restore itself; Forge only marks the release.
- Every database change keeps the previous release working (add first, remove a release later). This is the pending story FORGE-EXPAND-1, which this plan cites and does not rebuild.

## Why

After a demo, the FDE has no single way to turn notes into separate changes with one approval. A person waiting on an approval or an assignment does not see it in the app. A Mainline rollback reverts only the code, so a migration that removes something the previous release reads breaks it, and no release is marked for a backup before Promote.

## Done when

1. **A record waiting for someone's action shows in that person's in-app list with a count.**
2. **Demo notes or a transcript become separate changes shown as one list, and none starts until the FDE gives one OK.**
3. **A release with a migration is marked, and one test restore is run before launch.**
4. **Each part says what a new client repo and an existing client repo get on upgrade, and its tests cover both.**

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
