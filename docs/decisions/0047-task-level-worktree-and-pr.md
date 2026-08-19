---
status: accepted
confirmed_by: "Ravi Kiran Vemula"
date: 2026-08-19
stories: [FORGE-ACC-3]
supersedes: 0002-concurrency-one-task-per-branch
---

# Each leaf task ships in its own worktree and PR

## Context

Decision 0002's filename reads "concurrency-one-task-per-branch," but its
accepted body, `WORKFLOW.md`, and `roadmap.cmd_parallel()` enforce **one story
per worktree**: leaf tasks run sequentially inside a single story worktree and
ship as one story PR. The operator requires each leaf task to be independently
reviewable and shippable — its own worktree and its own PR to `main`. This also
closes a real gap: the story `done`-flip happens in `pr_ready` before the PR
merges ("done before merge"), and per-task work carries no PR-level review or CI
of its own. The dependent-task ordering (task N+1 builds on task N) makes this a
**sequential** model, not parallel.

## Decision

Supersede 0002. Each leaf task runs in its own git worktree and ships as its own
PR to `main`, **sequentially**: task N+1 branches only after task N's marker is
on `origin/main`.

- `forge task start <id>` creates `feat/<KEY>-<TASKID>` in a sibling worktree
  off the exact fetched `origin/main` SHA, requires task N−1's marker on main,
  hydrates the approved story plan / decomposition / task grill / task plan, and
  initializes that worktree's protected run/decomposition/stages authority. The
  untracked run pointer gains `issue_key`, `task_id`, `branch`, `base_main_sha`;
  a shared `require_task_worktree()` gate binds every downstream action to the
  right worktree.
- `forge task pr-ready <id>` is the per-task seal (shared predicates factored
  from `pr_ready.py`, not cloned): fresh grill + attributed task-plan approval,
  this task's stage `done` with a clean certified local-review stamp and a
  non-empty committed product delta, no open signal/window/blocking assumption,
  clean worktree. It writes `.factory/stories/<KEY>/tasks/<TASKID>/pr-ready.json`
  and opens/attaches the PR — it does NOT `mark_status()` or write story
  outcome/`shipped.json`.
- **Shipped truth is marker-on-main**, not CI success: a task advances only when
  its exact `pr-ready.json` marker appears on refreshed `origin/main`. No task
  DB, no roadmap task fields, no branch/Git-log inference.
- Roadmap `done` stays story-level: `pr_ready.py` (story closeout) requires every
  decomposition task marker present on the closeout branch's main base, then runs
  the once-per-story verify + functional (when `user_facing`) + one coherent
  three-lens autoreview + outcome, and flips `done`. A final evidence-only
  **story-closeout PR** off updated main carries that flip (never the last task
  PR — that would recreate "done before merge").
- `forge next` routes exactly one per-task frontier: author-contract → grill →
  author-task-plan → await-approval → start-worktree → stage-start → delegate →
  local-review → commit → stage-done → open-task-pr → await-merge, then task N+1.
- `check_pr_ticket.py` + `roadmap-gate.yml` treat a validated task marker as a
  completed work record (`<KEY>/<TASKID>`), preserving story/quickfix handling.

## Consequences

- Each task is a focused, independently reviewed PR with its own CI; the story
  ships as a chain of merged task PRs plus a closeout PR.
- Per task: focused tests/CI + certified local review. Once per story: verify,
  functional evidence, three-lens review, outcome — unchanged (decision 0011).
- Preserves 0032 (fixed ordered task list, JIT detail, no task N+1 until N
  merges), 0045 (`story_dir`/`evidence_path`; each worktree hydrates protected
  authority), and 0029 (real attributed human approval — no backdating).
- Over-building rejected: stacked-PR tooling, parallel worktrees for dependent
  tasks, a task tracker, a second top-level evidence tree, merge inference from
  branch names.
- Bootstrap: the infrastructure itself is built in the current story-worktree
  model (it cannot ship under a model that does not yet exist); thereafter every
  task uses task-level shipping. A retrofit of already-done tasks must re-run the
  real gates, never backdate stamps.
- Also fixes a CFS-1 mismatch: story completion writes
  `.factory/stories/<KEY>/shipped.json`, but `completed_stories` still recognizes
  only `.factory/history/<KEY>/`.
- Updates `WORKFLOW.md` (Concurrency, Stage Loop, Execution Order, PR Ready).
