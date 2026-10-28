# Email and member removal for client apps

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- Deployed apps send password reset and invite emails through an SMTP connection set in one setting.
- Deployed apps refuse to start until mail settings are present.
- A dev setup runs Postgres and a local mail catcher together.
- An Owner can remove a member, which ends their sessions, records it in history and cancels their pending invites.
- Sign-up in many-company apps verifies the email address.

## Why

Deployed apps send no mail, because the starter's mail provider only logs links outside development and test, so invites and password resets never reach people, and no route removes a member, because the members route only changes roles.

## Done when

1. **An Owner can remove a member, and that member's sessions end and their pending invites are cancelled.**
2. **Each removal appears in the history.**
3. **A deployed app with no SMTP setting refuses to start, with a clear message.**
4. **A new client app starts with a dev setup that runs Postgres and a local mail catcher.**

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
