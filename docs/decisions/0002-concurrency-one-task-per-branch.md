---
status: superseded
confirmed_by: "Ravi"
date: 2026-07-14
stories: []
superseded_by: 0047-task-level-worktree-and-pr
---

# Concurrency: one story per isolated worktree

## Context

`.factory/run.json` holds ONE active story, so a team working on parallel
stories needs a concurrency model. Each story also contains bounded task
stages, which must not race over the same checkout.

## Decision

One story per isolated Git worktree and branch. Intake names the branch
(`feat/<key>-<slug>`), the story's `.factory/` state is committed on that
branch through the loop, and `pr_ready.py` archives evidence to
`.factory/history/<issue>/` before merge. The roadmap dependency graph
determines the ready story frontier; each ready story may run in its own
worktree. Task stages inside one story execute sequentially in decomposition
order with no parallel file edits. Roadmap status flips merge normally and
`.gstack` JSONL stores union-merge via the jsonl-append driver.

## Consequences

- Evidence is reviewable in the PR alongside the code it attests to.
- main only accumulates archived history, never in-flight story state.
- Two branches merged in sequence may conflict on `.factory/run.json`;
  resolution is trivial (the later story's state wins — both are archived).
- `forge roadmap parallel` prints the exact worktree setup commands for the
  currently dependency-ready stories.
