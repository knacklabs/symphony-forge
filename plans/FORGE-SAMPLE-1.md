# Sample-data prototypes get a light sign-off

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- A prototype whose sign-off record declares sample data gets one small gap check at sign-off. It reads the brief, the client's answers, the artifact's screens, the app routes, the demo steps and the signer's record.
- That prototype skips the full test run and the whole-source review at sign-off, and needs only the signer's name.
- Review findings other than Harm 4 or higher, Gain 5 or P0 go to Known issues with no repair round, unless the owner asks for one.
- Open brief items show as a quiet checklist in forge next and on the board. They inform and never block, and not known yet is accepted, not a finding.
- An open personal-data answer blocks only before the first release that uses real data.
- Agents run review-only passes at milestones for other prototypes. There is no new brief command.
- Prototypes with real data or a back end keep today's sign-off rules. Existing repos need no migration.

## Why

Sign-off for a prototype that holds only sample data is heavier than the prototype needs. It runs the full test gate and a whole-source review, and it refuses while must-answer brief topics are open.

## Done when

1. **A sample-data prototype's sign-off runs only the small gap check and asks only for the signer's name.**
2. **Its other review findings land in Known issues with no repair round, unless the owner asks for one.**
3. **forge next and the board show open brief items as a checklist, and sign-off never refuses on them for such a prototype.**
4. **A prototype with real data or a back end, and every existing repo, sees no change.**

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
