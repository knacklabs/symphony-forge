# Task plan — plan-mode-gate (story plan-mode-and-grill-provenance)

## Objective
Make `plan save`, `plan approve`, `task plan save` and `task approve` refuse
any plan file whose body digest was not recorded by a plan-mode write, so a
plan authored from normal mode can no longer be saved or approved.

## State left by prior work
Task 1 shipped `factory/scripts/post_tool_use.py`: for `Write`/`Edit`/
`MultiEdit` with `permission_mode == "plan"` it records
`<scope>/plan-mode/<uuid>.json` = `{generated_by, path (absolute), sha256
(raw), sha256_body (plan_digest_without_assumptions), at, session_id}`,
scope = `evidence_path(root, story, "plan-mode")` (root-level when no
story). `plans.cmd_save()` (plans.py:123) resolves `source` at :145 and
calls `_require_matching_plan_grill` at :170; `cmd_approve()` (:255)
re-checks the grill at :284. `tasks.cmd_plan_save()` (tasks.py:47) reads
`source` at :50–58 and copies it; `tasks.cmd_approve()` (:65) stamps the
task grill. `plan_digest_without_assumptions` (factory_lib.py:1329) is the
body digest both the grill and the marker use.

## Steps (Codex, via delegate)
1. `factory_lib.py`: `require_plan_mode_marker(root, story, source: Path,
   *, what: str) -> dict`: compute `plan_digest_without_assumptions(source)`;
   scan `evidence_path(root, story, "plan-mode")` (and, when `story` is
   None, the root scope) for a record whose `sha256_body` equals it; return
   the record or `fail(f"{what} was not authored in plan mode: no plan-mode
   marker matches {source} — enter plan mode, write the plan there, and
   save that file verbatim")`. Malformed marker files are skipped (the hook
   is fail-open; the gate is not).
2. Call sites: `plans.cmd_save()` right after `source` is resolved and
   before `_require_matching_plan_grill`; `plans.cmd_approve()` before the
   grill check, against the awaiting active plan file; `tasks.cmd_plan_save()`
   after reading `source`; `tasks.cmd_approve()` against the saved task plan.
   Quickfix/degraded paths are untouched (they have no plans).
3. Story-scope rule: markers are searched in the active story's scope first,
   then the root scope (a plan written before `intake` — e.g. a storyless
   spec session — still counts). No time window; digest only.
4. Tests (`factory/tests/test_gates.py`, reuse `repo`, `intake`,
   `save_plan`, `record_grill`, `post_hook`, `seed_task_grill_frontier`,
   `record_task_grill`):
   - `test_plan_save_refuses_plan_without_plan_mode_marker` — full happy
     fixture minus marker → refused with the message above.
   - `test_plan_save_and_approve_accept_plan_with_plan_mode_marker` — a
     `post_hook` plan-mode Write for the same file, then save → awaiting,
     approve → approved, save → approved.
   - `test_task_plan_save_and_approve_require_plan_mode_marker` — refusal
     without, success with.
   - `test_plan_mode_marker_matches_body_not_assumptions` — append an
     `## Implementation Assumptions` block after the marker; save still
     passes (body digest unchanged).
   Existing fixtures that call `save_plan` gain a helper `mark_plan(repo,
   path)` that writes the marker through the real hook (no fixture writes a
   marker file by hand).

## Write scope
`factory/scripts/factory_lib.py`, `factory/scripts/forge_cli/plans.py`,
`factory/scripts/forge_cli/tasks.py`, `factory/tests/test_gates.py`.

## Proof (required_tests)
`uvx --with pytest --with psutil python3 -m pytest {path}::{id} -q -o
junit_family=legacy --junitxml={report}` on `factory/tests/test_gates.py`
for the four ids above.

## Verify commands
`python3 factory/scripts/check_dual_runtime.py` (verify.py is the
story-level phase; it writes an event and is not a task proof).

## Reviewer focus
The check is digest-only (no timestamps); it reads markers through
`evidence_path`, never a hand-built path; the refusal message tells the
author exactly what to do; fixtures create markers only via the real hook;
no gate weakens when the story scope is empty but the root scope matches.

## Task grill (1 round, 2 questions; frontier empty)
- Lookup order: active story scope, then root scope; digest-only.
- Every existing fixture marks its plan through the real hook; no env
  bypass of any kind.

## Risk
Every existing gate test that saves a plan must now mark it first — the
helper keeps that to one line per fixture; if the count is large the worker
reports it as a finding rather than loosening the gate.
