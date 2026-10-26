# Client apps deploy to dev and preview on their own, and production waits for a person's Promote

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- An engineer asks the agent once to set up deploys. The agent signs in to Mainline in the browser, connects the repo, writes the service settings after the engineer confirms them, and sets the subdomain and the variables from the example env file.
- Every merge to main deploys dev automatically, and every pull request gets a preview link. No agent runs a deploy after setup.
- Production changes only when a person presses Promote.
- The board and each pull request show the preview link, dev health and the release now in production.
- A failed dev deploy opens a fix that carries the failed step's log.

## Why

Each deploy is a manual agent run that waits for a specific request, the address is written by hand, and neither the board nor the pull request shows whether dev or production is healthy. A failed deploy has no fix path.

## Done when

1. **A new client repo completes the setup once, and its first dev deploy reports healthy before any other deploy runs.**
2. **A merge to main updates dev, and a pull request shows a preview link without any agent command.**
3. **An agent cannot deploy production, and production changes only after a person presses Promote.**
4. **The board and the pull request show the preview link, dev health and the production release.**
5. **A failed dev deploy opens a fix that includes the failed step's log.**
6. **An existing client repo on upgrade receives the new guidance and the setup prompt, with a test for that path next to the new-repo test.**

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
