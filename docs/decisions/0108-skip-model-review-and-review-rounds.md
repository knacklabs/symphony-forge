---
status: proposed
confirmed_by: ""
date: 2026-11-07
stories: []
supersedes: ""
---

# Skip the model review and set review rounds

## Context

Decision 0092 says every task and Lite fix gets a model review. On 6 November 2026, the owner chose to let a named person skip that review for a task or fix. The owner also chose limits for cold reads and task reviews. This decision records those choices.

## Decision

A person can skip the model review at close when they give a name and reason. Close records both on the pull request. Close refuses the skip after any earlier review blocked the item. Tests, CI, design checks and merge still run. Agents use the skip only when a person asks.

`cold_read_rounds` sets the cold-read limit. `task_review_rounds` sets the task-review limit. Each accepts 1 or 2 and defaults to 2. Fixes keep one review round.

This decision replaces only 0092's rule that every item gets a model review. The other rules in 0092 remain in force.

## Consequences

A named skip can close an item without a model review. A change after that close needs another review unless a person asks for another skip. An item with an earlier review that blocked it cannot use the skip.
