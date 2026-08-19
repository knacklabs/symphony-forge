# FORGE-ACC-3 · Task 8 — task-worktree-start

## Context

Decision 0047 supersedes 0002: each leaf task should ship in its **own worktree
and PR off `main`, sequentially**. This task builds the entry point —
`forge task start <id>` — plus the `require_task_worktree` gate that binds every
downstream action to the right worktree. Today `forge task` has only
plan-save/approve; worktrees are merely *printed* by `roadmap cmd_parallel`, and
the untracked run pointer (`git_control_dir/run.json`) carries `issue_key` but no
task identity. **Bootstrap:** ACC-3 itself ships story-level and does not run
`forge task start`; this builds it for the *next* story.

## Design (grilled — all three questions confirmed the recommended option)

- **Predecessor-marker gate** via `git cat-file -e origin/main:<marker>` on the
  fetched main tree (no branch-name / merge inference).
- **Hydrate** the new worktree by **copying** the approved plan, decomposition,
  task grill, and task-plan from the current planning worktree (uniform for the
  first and later tasks).
- **`require_task_worktree`** refuses unless the current branch == the run
  pointer's branch **AND** its `task_id` == the frontier task.

## Changes (write_scope only — 6 files)

1. **`factory/scripts/factory_lib.py`** — `task_marker_path(key, task_id)` =
   `.factory/stories/<KEY>/tasks/<TASKID>/pr-ready.json` (shared; task 9 writes
   it) and `require_task_worktree(root)` (branch + run-pointer `task_id` match).
2. **`factory/scripts/forge_cli/tasks.py`** — `cmd_task_start(<id>)`:
   `git fetch origin main` → resolve `base_main_sha`; for a non-first task,
   `git cat-file -e origin/main:task_marker_path(pred)` or refuse; `git worktree
   add ../<repo>-<KEY>-<TASKID> -b feat/<KEY>-<TASKID> <base_main_sha>`; copy the
   approved plan / decomposition / task grill / task-plan in and init the new
   worktree's protected run/decomposition/stages authority; write the untracked
   run pointer with `issue_key`, `task_id`, `branch`, `base_main_sha`. Refuse if
   the branch or worktree already exists; never touch `origin`.
3. **`factory/scripts/forge.py`** — register `forge task start <id>`.
4. **`factory/scripts/forge_cli/stages.py`** — `stage start` calls
   `require_task_worktree`.
5. **`factory/scripts/forge_cli/delegate.py`** — write `delegate` calls
   `require_task_worktree`.
6. **`factory/tests/test_gates.py`** — the two required tests below.

## Non-goals / guardrails

- The predecessor is the decomposition task immediately before `<id>` in
  recorded order; the first task skips the gate (bootstrap).
- Run-pointer additions stay backward-compatible — story-level runs omit
  `task_id`/`branch`, and `require_task_worktree` is a no-op when they're absent.
- `forge task pr-ready` (the marker writer) and frontier routing are tasks 9/10 —
  out of scope; only the marker *path* is defined here.
- Touch only the 6 write_scope files.

## Reuse (already on the branch)

`git_control_dir` / `run_state_path` (the untracked run pointer),
`story_dir` / `evidence_path`, `protected_decomposition_state_path`
(`factory_lib.py`); the `git worktree add -b feat/<KEY>-<slug> <sha>` pattern
from `roadmap.cmd_parallel`; the `forge task` subparser wiring in `forge.py`.

## Verification

- `test_task_start_creates_worktree_off_main_and_gates_on_predecessor_marker` —
  with the predecessor marker absent from a stub `origin/main`, `forge task start`
  refuses; with it present, it creates `feat/<KEY>-<TASKID>` off the fetched SHA,
  hydrates the inputs, and writes a run pointer carrying `task_id`/`branch`/
  `base_main_sha`; the first task starts with no marker gate.
- `test_stage_start_and_delegate_refuse_from_wrong_task_worktree` — a run pointer
  naming one task/branch while on a different branch → `stage start` and write
  `delegate` both refuse via `require_task_worktree`; they pass in the matching
  worktree.
- `python3 factory/scripts/check_dual_runtime.py` clean.
