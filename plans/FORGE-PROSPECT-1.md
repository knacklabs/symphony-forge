# Research the prospect before a prototype and propose features from what is found

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- Before a prototype is built, the Sales person gives the company name, its website and any notes, and the agent writes one page of sourced research about the company in the client repo.
- The agent proposes one prototype, with each feature linked to the finding it comes from, plus two other possible prototypes. The Sales person says yes, picks another or changes it in plain words.
- When little is public, the agent says what it could not find, asks up to five questions, and marks ideas taken from similar companies as coming from similar companies.

## Why

A prototype built from a generic list for the industry does not show what this company actually needs, so the demo can miss the buyer's own problems.

## Done when

1. **One sourced research page is written in the client repo, from one bounded web research pass with a fixed stop limit.**
2. **The Sales person sees one proposed prototype with a finding and a link for each feature, plus two other options.**
3. **The Sales person can say yes, pick another prototype or change it before any build starts.**
4. **Guide and skill text ship to new and existing client repos, with no new screen.**

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
it may change. Before writing each Scope, search the code for the files the task needs. The plan
check refuses two tasks whose Scope paths have the same prefix up to the first wildcard, unless
one waits for the other through After, directly or through another task; it names both tasks.
Paths with a segment named `tests`, `test`, `__tests__` or `spec` do not cause Scope overlaps
and can be shared without an After link. Explicit After links still apply.
When tasks need the same production file, put it in the first task's Scope with the shared names and stubs;
tasks that need them wait for that task through After and then own only their files. Tests: the
tests it adds or changes. After: the tasks it waits for. When two tasks share a function, field,
file format or command, the first task pins it: it commits the shared names and stubs plus one
test that crosses both sides, and the tasks that use it list it under After. Split tasks so each
owns its files; shared lines (command table, guide list, registry) go to one task or a small last
wiring task; After only when a task needs another task's code. The
Developer column is optional: the lead fills or changes a GitHub username here, below For the
builders, without another approval. Leave it blank for an unassigned part. Forge next uses
the caller's GitHub login; another developer may start it with a warning. Existing tables
without Developer still work. The moving-parts line stays last: "none", or each new dependency, service, datastore,
queue, background job or abstraction layer, with the Done-when item that needs it. -->

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|

New moving parts: none

## Notes
