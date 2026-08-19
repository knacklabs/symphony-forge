# FORGE-ACC-3 · Task 11 — roadmap-gate-task-markers

## Context

Decision 0047 ships each leaf task as its own PR. CI's `pr-ticket-check`
(`check_pr_ticket.py`, run by `roadmap-gate.yml`) requires every completed work
record in a PR to be declared, but it only knows about **story** completions
(`.factory/history/<KEY>/`, `.factory/stories/<KEY>/shipped.json`) and
**quickfix windows** — it has no notion of a per-task `pr-ready.json` marker. So
a task PR (whose only completed work record is its validated marker) would fail
the gate. This task teaches the gate to recognize a validated task marker as the
completed work record `<KEY>/<TASKID>`.

## Design (grilled — all three questions confirmed)

- **Marker validation** is lightweight and dependency-free: an added path
  `.factory/stories/<KEY>/tasks/<TASKID>/pr-ready.json` whose JSON has
  `task_id == <TASKID>`, `branch`, `base_main_sha`, `commit`, `sealed_at`.
- **Declaration**: a `Ticket: <KEY>/<TASKID>` PR-body line **or** inference from
  a canonical `feat/<KEY>-<TASKID>` branch that adds that marker (mirrors story
  handling).
- **Additive**: task markers join `completed_stories` + `completed_windows`; a
  PR must declare every record it completes; story/quickfix logic is untouched.

## Changes (write_scope only — 3 files)

1. **`factory/scripts/check_pr_ticket.py`** — add `completed_task_markers(root,
   added)` returning `<KEY>/<TASKID>` for each added, field-valid marker; wire it
   into `main()` additively; extend `branch_ticket` so a `feat/<KEY>-<TASKID>`
   branch that adds the matching marker yields `<KEY>/<TASKID>` (the story-branch
   `feat/<KEY>-<slug>` inference stays).
2. **`.github/workflows/roadmap-gate.yml`** — change only if it must pass the head
   branch or must not filter the marker path; otherwise leave unchanged.
3. **`factory/tests/test_gates.py`** — the two required tests below.

## Non-goals / guardrails

- No schema/factory_lib import in the CI check — validate marker fields by
  presence.
- Story done-flip (`history`/`shipped.json`) and quickfix-window handling stay
  **unchanged** (a required test asserts this).
- Touch only the 3 write_scope files.

## Reuse (already on the branch)

`added_paths`, `branch_ticket`, `completed_windows`, `completed_stories`, the
`Ticket:` regex and the "every record must be declared" loop in
`check_pr_ticket.main`; the marker path/field contract from `task_marker_path`
and `cmd_task_pr_ready` (tasks 8/9).

## Verification

- `test_pr_ticket_accepts_a_validated_task_marker_as_work_record` — a PR that
  adds a valid `.factory/stories/<KEY>/tasks/<TASKID>/pr-ready.json` and declares
  it (via `Ticket:` or a `feat/<KEY>-<TASKID>` head branch) passes; an
  undeclared or field-invalid marker fails.
- `test_pr_ticket_story_and_quickfix_handling_unchanged` — a story-completion PR
  and a quickfix-window PR behave exactly as before.
- `python3 factory/scripts/check_dual_runtime.py` clean.
