# Task plan — round-provenance-gate (story plan-mode-and-grill-provenance)

## Objective
Make grills provable: every recorded round must match the AskUserQuestion
ledger, meet the per-gate floor, and end with a frontier-empty attestation;
a task grill needs its task plan saved first; the frontier and `forge next`
state the enforced order.

## State left by prior work
Task 1 records `<scope>/grill-rounds/<uuid>.json` =
`{generated_by, questions: [{question, options, chosen}], at, session_id}`
via the PostToolUse hook (live-proven: chosen answers ARE delivered). Task 2
enforces plan-mode markers via `plan_body_digest` (frontmatter and
assumptions excluded), story-then-root scope. The grill recorder
(`record_grill_from_json.py`) validates rounds structurally for the task
gate only (`_validate_task_grill`, rounds optional elsewhere; zero rounds
legal); freshness lives in `require_grill`/`require_task_grill`
(`factory_lib.py:1212/1276`); the frontier routes `grill` before
`author-task-plan` (`task_frontier_state`, `factory_lib.py:~1603`;
`tasks.cmd_plan_save` calls `require_ready_task` which demands the grill);
`phase.py` prints the old order.

## Steps (Codex, via delegate)
1. **Ledger match (all four gates: spec, requirements, plan, task).** In
   `record_grill_from_json.py`, after base schema validation: load
   grill-round records from the story scope and the root scope (both, same
   rule as markers). Each `rounds[].question` must exactly equal a logged
   question and its `chosen` must equal the logged chosen (when the log has
   a non-null chosen). Unmatched round → refusal naming the question.
2. **Floors + attestation.** `GATE_ROUND_FLOORS = {"spec": 2,
   "requirements": 1, "plan": 2, "task": 1}`; `len(rounds)` ≥ floor; the
   final round carries `"frontier_empty": true` (schema: optional boolean
   on a round entry; the hook does not record it — the griller attests it
   in the payload, but the round itself must still match the ledger).
   Zero-rounds grills are refused for these gates; the epics and signoff
   gates are untouched this task.
3. **Byte-identical re-record reuse.** When a grill for the same gate and
   story already exists with `input_sha256` equal to the new payload's, the
   rounds ledger-match may reuse ledger records regardless of age (no
   freshness window on rounds); nothing else changes about digest freshness.
4. **Task plan before task grill.** The task-gate branch refuses when
   `task-plans/<id>.md` is absent, with the one-time tolerance: an existing
   recorded grill stays valid if the task plan is saved before
   `stage start` (tolerance keyed on grill `recorded_at` < task-plan mtime;
   tested). `task_frontier_state` routes `author-task-plan` before `grill`;
   `tasks.cmd_plan_save` drops its grill requirement (keeps
   `require_ready_task(..., require_grill=False)` semantics);
   `stage start` still requires both.
5. **`forge next` text.** Planning route prints: plan mode (hook records
   the plan) → grill via AskUserQuestion until frontier_empty → plan save
   --from the plan-mode file → human plan approve. Implementing route
   prints: author task plan in plan mode → task grill → human task approve
   → stage start → delegate.
6. **Tests** (six required):
   - `test_grill_refuses_round_not_in_ledger`
   - `test_grill_refuses_below_gate_floor`
   - `test_grill_refuses_missing_frontier_empty`
   - `test_grill_accepts_ledger_matched_rounds_happy_path` (plan gate,
     2 logged rounds via the real hook, final one attested frontier_empty)
   - `test_task_grill_requires_saved_task_plan_with_tolerance`
   - `test_frontier_orders_task_plan_before_grill` (flip the existing
     inverse-order tests at ~15112; do not delete them)
   Fixture helper: extend `post_hook` usage to log AskUserQuestion payloads
   (questions with options and chosen) exactly as the live hook does.
   Existing suite fixtures that record grills gain logged rounds through
   the same helper — no hand-written ledger files, no env bypass.

## Write scope
`factory/scripts/record_grill_from_json.py`,
`factory/scripts/factory_lib.py`, `factory/scripts/forge_cli/tasks.py`,
`factory/scripts/forge_cli/phase.py`, `factory/schemas/grill.json`,
`factory/tests/test_gates.py`.

## Proof (required_tests)
`uvx --with pytest --with psutil python3 -m pytest {path}::{id} -q -o
junit_family=legacy --junitxml={report}` on `factory/tests/test_gates.py`
for the six ids above.

## Verify commands
`python3 factory/scripts/check_dual_runtime.py`.

## Reviewer focus
Rounds are matched against ledger records read via `evidence_path`
(story-then-root), never hand-built paths; the floors are a named constant;
`frontier_empty` is required on the final round only; the tolerance is
keyed on timestamps and covered by a test; every fixture logs rounds
through the real hook; the epics/signoff gates are explicitly unchanged;
no weakening of digest freshness.

## Task grill (1 round, 2 questions; frontier empty)
- Recorded via AskUserQuestion in this session (the ledger match will
  apply to this story's own later grills once this task lands).
- Chosen equality is exact when the ledger entry has a non-null chosen;
  null-chosen entries match on question text alone.
- Epics and signoff gates stay un-floored this story; extend later if
  they prove gameable.

## Risk
This story's OWN grills recorded before this task (requirements, plan,
tasks 1–2) predate the enforcement and stay valid — enforcement applies at
record time, not retroactively. Task 4's grills (spec re-confirms) will be
the first recorded under the full rule; the orchestrator must deliver those
rounds via AskUserQuestion or be refused by its own gate.
