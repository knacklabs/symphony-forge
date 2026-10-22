# Setup interview and app constitution for client repos

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- When Forge sets up a new app or adopts a live one, the agent interviews the person in plain words. It always asks the five questions with no safe default (what the app is for, who uses it, what it tracks with each thing's fields, the options of each choice list, and whether any data is private or regulated). For the other questions it shows safe defaults in one message that the person can change.
- The agent makes the architecture choices from the answers and Forge's stack, each in one plain line with its reason. It writes docs/product/CONSTITUTION.md plus one accepted decision record per choice, and the owner approves the constitution once.
- No story or fix starts in a new app until the constitution is approved. This conflicts with decision 0095 (docs/decisions/0095-prototype-before-stories.md), which lets prototype fixes run before customer sign-off, so the plan must settle that order.
- New client repos get the interview on init. Existing client repos get it on upgrade and sync, and are asked only what the code cannot answer.

## Why

A new or adopted app starts with its product facts and stack choices unrecorded, so later stories rest on guesses and the non-technical owner has no single place to confirm them. This is a guess from the idea and the research checklist at /Users/ravikiranvemula/Workdir/app-checklist-research.md, which lists 26 questions with defaults.

## Done when

1. **A new client repo, after the interview, has an approved docs/product/CONSTITUTION.md and one accepted decision record per architecture choice.**
2. **Forge refuses to start a story or fix in an app whose constitution is not approved, and the message names the next action.**
3. **A cold read or review that finds work against the constitution reports it as P1.**
4. **An existing client repo adopted on an earlier release gets the interview only for answers the code cannot give, on upgrade and sync.**

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
