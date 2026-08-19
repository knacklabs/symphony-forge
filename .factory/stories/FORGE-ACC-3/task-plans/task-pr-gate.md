# FORGE-ACC-3 · Task 9 — task-pr-gate

## Context

Decision 0047: each leaf task ships as its **own PR to `main`**, sealed by the
same rigor as a story. Task 8 built `forge task start` and defined the marker
path; nothing writes that marker yet, and `pr_ready.py` holds the seal checks
inline as a story-level script. This task adds `forge task pr-ready <id>` — the
per-task seal — by **factoring** the reusable predicates out of `pr_ready.py`
(not cloning them), writing the marker, and opening the PR. **Bootstrap:** ACC-3
ships story-level and does not run `forge task pr-ready`.

## Design (grilled — all three questions confirmed)

- **PR open via `gh pr create`** — gh 2.95.0 is installed and authenticated in
  this environment. The marker is written **first** (shipped truth), so it never
  depends on the PR call; if gh is unavailable/unauthenticated at run time, fail
  clearly (never silently skip). Tests stub a fake `gh` on PATH.
- **Factor the seal predicates into `factory_lib`** — `pr_ready.py` refactors to
  call the same predicates where they overlap (factored, not cloned).
- **Shipped truth = the marker on refreshed `origin/main`** — a shared
  `task_marker_on_main` helper reused by task 8's start gate and task 10's
  frontier; never CI-green or branch/git-log inference.

## Changes (write_scope only — 5 files)

1. **`factory/scripts/factory_lib.py`** — `require_task_sealed(root, task_id)`:
   fresh grill + attributed task-plan approval (reuse `require_ready_task`),
   this task's stage `done` with a clean certified local-review stamp (task-4
   stamp check) and a non-empty committed product delta, no open
   signal/window/blocking assumption, clean product worktree/index (reuse
   `product_tree_snapshot`). Plus `task_marker_on_main(root, key, id)` (git
   fetch + `cat-file -e origin/main:<marker>`).
2. **`factory/scripts/pr_ready.py`** — refactor to call the factored predicates
   where they overlap; the story closeout still adds its own verify/review/
   outcome chain (task 6).
3. **`factory/scripts/forge_cli/tasks.py`** — `cmd_task_pr_ready(<id>)`: run
   `require_task_sealed`; on pass write `task_marker_path(key, id)` (validated
   payload: `task_id, branch, base_main_sha, commit == HEAD, sealed_at`), then
   `gh pr create`. It MUST NOT `mark_status()`, write `outcome.json`/
   `shipped.json`, or flip the roadmap.
4. **`factory/scripts/forge.py`** — register `forge task pr-ready <id>`.
5. **`factory/tests/test_gates.py`** — the two required tests below.

## Non-goals / guardrails

- Factored, not cloned — no second copy of the seal logic.
- No `mark_status`/outcome/`shipped.json`/roadmap flip (task 10 owns closeout;
  task 6 owns story-level pr_ready ordering).
- Marker written before the PR call; gh failure never leaves a half-sealed task.
- Touch only the 5 write_scope files.

## Reuse (already on the branch)

`require_ready_task` + the task-4 stamp check, `product_tree_snapshot`,
`task_marker_path` (task 8), `open_signals`, `load_active` (window state),
blocking-assumption check (`forge_cli/assumptions`) — all already used by
`pr_ready.py`.

## Verification

- `test_task_pr_ready_refuses_unsealed_then_writes_marker_and_opens_pr` — a task
  missing approval/stamp/clean-tree/committed-delta → refuses; a fully sealed
  task → writes the marker (`commit == HEAD`) and invokes the stubbed `gh pr
  create` with the expected argv.
- `test_task_pr_ready_does_not_flip_roadmap_or_write_outcome` — after a
  successful seal, `roadmap.json` status is unchanged and no
  `outcome.json`/`shipped.json` is written.
- `python3 factory/scripts/check_dual_runtime.py` clean; the pr_ready suite green
  (refactor preserved story-level behaviour).
