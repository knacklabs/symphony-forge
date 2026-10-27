# Client apps offer MCP resources and prompts too

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- Each client app built from the starters offers read-only resources for every feature: one item at an address such as app://projects/{id}, a field guide that lists each field with its kind and allowed values, and lists of allowed values such as statuses, with change notices.
- At setup the agent asks which tasks people will repeat, and writes one prompt per answer in the feature's tools file; with no answer there are no prompts.
- No elicitation is added, and sampling is never used.
- The guide, the worker brief and the feature command carry these rules; new repos get them at init and existing repos get the guide text on upgrade, with no app files, like the MCP tools story.

## Why

An agent using a Forge client app through MCP can only call tools. It cannot read a record at a stable address, look up a field's allowed values without trial and error, or reuse a repeated workflow without a fresh request. The data already exists in the feature command's kinds table and schemas, so resources can be generated from the same schemas as the tools. This depends on the MCP tools story landing first.

## Done when

1. **A new client app built from the starter serves, for each feature, one resource per record address, a field guide, and allowed-value lists, each with change notices.**
2. **Prompts exist only for the tasks the owner names at setup; with no answer, the app has none.**
3. **The generated app contains no elicitation and no sampling.**
4. **The guide, the worker brief and the feature command state these rules; an existing repo gets the text on upgrade with no app files, with a test for a new repo and an adopted repo.**

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
