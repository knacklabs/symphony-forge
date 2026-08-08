---
status: accepted
confirmed_by: "vrknetha"
date: 2026-08-08
stories: [FORGE-BOARD-2]
---

# Jit Task Planning

## Context

Decision 0007 records a decomposition as one stage per leaf task in fixed
execution order, and `record_decomposition` writes every task's full contract
upfront. But a later task's contract depends on what the earlier tasks actually
built — which an upfront contract cannot know. The agent implements task N from a
contract written before tasks 1..N-1 existed, fills the unknowns by ASSUMING, and
the assumption ships as incorrect code. This is the first and worst gap in the
`traceable-board` spec.

The mechanics already permit the fix: the recorder requires per task only `id`,
`title`, `objective`, `acceptance_criteria`, and ordered `dependencies` —
`write_scope`, `required_tests`, and `verify_commands` are optional at record
time and re-read by id at delegate / `stage done`. Decision 0023 already makes a
mid-stage contract re-record ledgered rather than baseline-resetting. What is
missing is a gate that forces each task's detail to be authored — and grilled —
against real prior state before that task is implemented.

## Decision

Record only the task **list** at decomposition (id, order, dependencies, one-line
objective, acceptance). Author each task's detailed contract (`write_scope`,
`required_tests`, `verify_commands`) **just-in-time**, against the actual repo
state left by the prior tasks, and **grill it before delegating** that task. The
per-task JIT grill is a deterministic gate: `forge delegate <task>` refuses a
write launch without a fresh, digest-bound, passing per-task grill
(`.factory/grills/tasks/<id>.json`, bound to `task_digest`), exactly as
`plan save` refuses an ungrilled plan.

This **amends 0007** — the task list and execution order stay fixed at
decomposition; only the per-task contract DETAIL becomes JIT — and **extends
0023** — pre/mid-stage contract authoring is now the normal path, not just an
escape hatch. Done-stage contract immutability (0023) is preserved unchanged.

## Consequences

- Two grill points are kept deliberately: the story plan-grill validates the
  decomposition (are these the right tasks? does the shape cover the story?); the
  per-task JIT grill validates each task's details against real prior state.
- The authoring/re-record happens BEFORE `stage start`, so the digest stamped at
  start already matches the grilled+delegated contract — no change to the stage
  engine's digest logic or the active-stage re-record path.
- A fifth grill gate (`task`) joins {signoff, spec, epics, plan}; per-task grills
  are retained under `.factory/grills/tasks/` and archived per story at pr_ready.
- The split rule still bounds a story to ~5 tasks, so JIT adds a handful of quick
  task-grills, not dozens.
- FORGE-BOARD-2 itself bootstraps this and is therefore decomposed the current
  upfront way; the new gate governs future stories.
