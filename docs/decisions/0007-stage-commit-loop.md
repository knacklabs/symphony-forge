---
status: superseded
superseded_by: 0093-lean-forge-rebuild
confirmed_by: "Ravi"
date: 2026-07-21
stories: []
---

# Decomposition tasks execute as stages; local autoreview gates every commit

## Context

The recorded decomposition bounded the work but nothing tracked execution
through it: a task's whole diff could accumulate uncommitted (or worse, be
committed unreviewed) until the single end-of-task review. The Gantry goal
pipeline showed the tighter loop — implement one stage, autoreview the LOCAL
diff until clean, then commit — keeps defects out of history entirely.

## Decision

Recording a decomposition also creates `.factory/stages.json`, a mutable
per-task tracker (one stage per leaf task, list order = execution order).
The dev loop per stage: `forge delegate <id>` composes the brief and launches
the installed companion in the story worktree → orchestrator inspects the diff
→ assumption rows validated → smallest relevant checks → **local autoreview
(`--mode local`) until clean → commit** → `forge stage done`. `forge stage start`
strictly enforces decomposition
order and refuses task-level `--parallel`; independent stories may run in
parallel only in separate worktrees when their roadmap dependencies are done.
`pr_ready` refuses
while any stage is not done; the tracker is archived to history and cleaned
at ship like all task-scoped state.

This CLARIFIES decision 0001's review consolidation (D6), not weakens it:
per-stage local autoreviews are pre-commit hygiene and record nothing; the
single branch-wide autoreview at the review phase remains the only review
GATE and the sole producer of `.factory/reviews/*`.

## Consequences

- Defects are caught while still uncommitted — history stays clean, and the
  final branch review sees cross-stage issues instead of re-finding
  per-stage ones.
- Stage state is deterministic and visible (`forge next` shows n/m done),
  so an interrupted task resumes exactly where it stopped.
- Slightly more ceremony per story; single-stage stories pay one `stage start`
  / `stage done` pair.
