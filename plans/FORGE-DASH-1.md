# Client apps get fast dashboards without hand-written queries

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

<What the people who use this will notice, in plain English. No IDs, codes or jargon.>

<!-- For user-facing parts: run impeccable init if PRODUCT.md is absent. Design the screens
in a Claude Design artifact; on a Codex-only host without artifact tools, use HTML artboards.
Save each screen and its images in docs/design/<KEY>/. Copy .forge/design/support.js beside
the HTML screens and run it for a 1440 by 900 PNG per screen. Commit the folder. Use its git tree
id (git rev-parse HEAD:docs/design/<KEY>) in the last line below. For small changes to existing
screens that add no screen and change no flow, use Design: none (<why>) instead.
Remove this comment and omit
the Design line for a backend-only story. Cold read follows the design; one plan approval binds
these exact files. A folder edit needs its new tree id and a new plan approval.
The rule starts with the next plan read and approval. Plans approved without a Design line
before this rule keep their existing approval. -->
Design: docs/design/<KEY>/ (<tree id>)

## Why

Client apps get fast dashboards without hand-written queries



## Done when

<!-- One bold plain sentence per result, which the owner approves: no code names, file paths or
test names. Its evidence, edge cases and proving tests go under the same number in Done-when
details. -->

1. **Something anyone can observe once this is done.**

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
