# Client apps get an optional in-app assistant

<n> parts · Risks: ... · New moving parts: ...

## What changes for you

- New client apps from either starter can include an assistant page, where a signed-in person asks questions in plain words and the assistant works with that person's own permissions.
- Reads run at once and show as a table, chart, stat tiles or a detail card, all from the app's design system. The assistant never writes page markup.
- Every write shows a confirm card first, and nothing is saved until the person confirms it.
- The agent loop uses LangGraph's prebuilt tool-calling agent in both starters, with its interrupt for the confirm card and its Postgres checkpointer for the 30-day chats.
- Each change made through the assistant is logged as that person, marked as made through the assistant, using the agent-ready story's rule for agents that act for a person.
- Analytics come from the app's report services. Models, the key and the spend budget come from Mainline.
- Each person's chats are kept for 30 days, and no one else can read them.
- A new app that opts in gets the assistant. An existing app gets nothing on upgrade, and adding the assistant later is a separate choice.
- Building waits for the agent-ready story and follows the agents skill.

## Why

Client apps cannot answer a person's question about their own data in plain words, and each client that wants this would build its own assistant with its own model keys, chat storage and write checks.

## Done when

1. **A new app from either starter with the assistant on shows a page where a signed-in person's question gets an answer from the app's own tools.**
2. **A question that only reads gets its answer at once, with no confirm card.**
3. **A question that would change data shows a confirm card, and nothing changes until the person confirms.**
4. **A chat disappears after 30 days, and no other person's chats ever show.**
5. **The assistant's model, key and budget come from Mainline, and an app without the assistant has none of its code.**

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
