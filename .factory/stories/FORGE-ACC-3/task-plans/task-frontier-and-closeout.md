# FORGE-ACC-3 · Task 10 — task-frontier-and-closeout

## Context

Decision 0047's per-task shipping needs the frontier to be **marker-aware**:
`forge next` must not offer task N+1 until task N's marker is on `main`, and the
story done-flip must require every task marker on main. Today
`task_frontier_state` is purely stage-driven (earliest task whose stage != done)
and `pr_ready` has no task-marker requirement; `completed_stories` also reads
only the legacy `.factory/history/<KEY>/` path, missing CFS-1's
`shipped.json`. **Critical constraint (task-8 deadlock lesson):** all new
behavior applies ONLY to task-level runs — a story-level run like ACC-3 (run
pointer has no `base_main_sha`) MUST keep its exact current frontier and
closeout.

## Design (grilled — all three questions confirmed)

- **Mode switch**: `is_task_level = bool(run-pointer base_main_sha)`. Story-level
  runs keep the current stage-driven frontier and the task-6 closeout unchanged.
- **await-merge fetch is lazy** — `task_marker_on_main` (fetch + cat-file) runs
  only when evaluating a task-level task that is stage-done and awaiting its
  marker; story-level `forge next` never fetches.
- **`completed_stories`** reads `.factory/stories/<KEY>/shipped.json` **and** the
  legacy `.factory/history/<KEY>/` path (additive).

## Changes (write_scope only — 4 files)

1. **`factory/scripts/factory_lib.py`** — add an `is_task_level` gate;
   `task_frontier_state` (task-level only) selects the earliest task whose marker
   is absent from main and adds an `await-merge` state after a task's stage is
   done until `task_marker_on_main(root, key, id)` is true (reuse task 9's
   helper, called lazily). Fix `completed_stories` to also read
   `.factory/stories/<KEY>/shipped.json`.
2. **`factory/scripts/forge_cli/phase.py`** — route exactly one per-task frontier
   state including `await-merge`; `task_rows` uses the SAME predicates so the
   board can't disagree; story-level routing unchanged.
3. **`factory/scripts/pr_ready.py`** — for task-level runs, require every
   decomposition task marker present on the closeout main base before
   verify+review+outcome+done-flip (an evidence-only story-closeout PR carries
   the flip); story-level closeout unchanged (task-6 chain).
4. **`factory/tests/test_gates.py`** — the three required tests below.

## Non-goals / guardrails

- Story-level behavior stays **byte-identical** — a required test asserts the
  frontier is unchanged when no task markers exist.
- Reuse `task_marker_on_main` / `task_marker_path` (task 9); no new marker logic.
- No fetch on the story-level or common path.
- Touch only the 4 write_scope files.

## Reuse (already on the branch)

`task_marker_on_main`, `task_marker_path` (task 9), `git_control_dir`,
`run_state_path`, `story_dir`, the existing `task_frontier_state` / `task_rows`
predicate structure, the task-6 `require_closeout_order` chain in `pr_ready.py`.

## Verification

- `test_task_frontier_awaits_marker_on_main_between_tasks` — a task-level run
  with task N stage done but its marker absent from a stub `origin/main` →
  frontier is `await-merge` for N, never N+1; once the marker is on main, N+1
  becomes the frontier.
- `test_story_closeout_requires_all_task_markers_and_completed_stories_reads_shipped`
  — task-level `pr_ready` refuses until all task markers are on main;
  `completed_stories` counts a story with `.factory/stories/<KEY>/shipped.json`.
- `test_story_level_frontier_unchanged_without_task_markers` — a story-level run
  (no `base_main_sha`) yields the identical stage-driven frontier and never
  fetches.
- `python3 factory/scripts/check_dual_runtime.py` clean.
