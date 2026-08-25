---
issue: plan-mode-and-grill-provenance
title: Plan mode and grill provenance are enforced, not advisory
status: approved
saved: 2026-08-24T10:04:04+00:00
story: plan-mode-and-grill-provenance
decisions_reviewed:
  - 0001-determinism-contract
  - 0003-model-tiers-terra-explore-sol-implement
  - 0005-recurring-findings-escalation
  - 0006-lessons-ledger
  - 0007-stage-commit-loop
  - 0008-loop-health-audit
  - 0009-frozen-gate-integrity
  - 0010-client-signoff
  - 0011-orchestrator-runs-autoreview
  - 0012-project-level-memory
  - 0013-always-armed-planning-lock
  - 0014-specs-before-signoff
  - 0015-plan-contradiction-gate
  - 0016-machinery-dir-rename
  - 0017-repo-as-system-of-record
  - 0018-delegation-gates
  - 0021-derived-ordering
  - 0022-conflict-free-ledgers
  - 0023-stage-delta-by-ref
  - 0025-evidence-lifetime-contract
  - 0026-bundled-example-validated-by-production-validators
  - 0027-responsive-proof-without-a-browser
  - 0028-path-boundary-invariant
  - 0029-plan-approval-in-plan-mode
  - 0030-harness-source-is-product-in-its-own-repo
  - 0031-workflow-modes-lite
  - 0032-jit-task-planning
  - 0033-gate-a-declares-all-work-records
  - 0034-vendored-docs-are-client-safe
  - 0035-commit-belt-keeps-ledger-fresh
  - 0036-client-gates-arm-on-roadmap
  - 0037-strict-role-split
  - 0038-portable-fail-closed-hooks
  - 0040-windows-user-scope-first-elevation-deferred
  - 0041-sandboxed-workers-default
  - 0042-psutil-cross-platform-process-model
  - 0044-accountable-engineering-loop
  - 0045-conflict-free-story-state
  - 0046-scoped-layout-activation-ordering
  - 0047-task-level-worktree-and-pr
---

# Plan — plan-mode-and-grill-provenance: Plan mode and grill provenance are enforced, not advisory

## Problem

`forge next` prints "MANDATORY: enter plan mode" and decision 0044 says every
grill delivers its rounds through AskUserQuestion — but no recorder checks
either. Today (cadence, `decisions-reconciled`) a session authored a story
plan and a task plan as files from normal mode and recorded grills with one
self-reported round; `plan save`, `task plan save` and
`record_grill_from_json.py` accepted all of it. The accountable-engineering
spec even permits zero rounds for a zero-gap grill, which lets a session
declare no gaps and skip interrogation. Decision 0029 already established
that hooks do **not** fire on `ExitPlanMode` (#21282), so the enforcement
signal must come from somewhere the hook can see.

## Scope / Non-goals

**In scope:** (1) a `post_tool_use` hook script and wiring; (2) plan-mode
provenance markers for story and task plans, checked by `plan save`,
`plan approve`, `task plan save`, `task approve`; (3) an AskUserQuestion
round ledger, with the grill recorder matching `rounds[]` to it and
enforcing per-gate floors + a `frontier_empty` attestation; (4) the task
frontier order changed to author-task-plan → grill → approve; (5) `forge
next` text; (6) gate tests; (7) spec/decision updates (accountable-
engineering-loop zero-rounds clause; plan-approval "plan mode is
presentation only" clause); (8) vendoring via the existing wholesale copy.

**Non-goals:** Codex-side provenance (the Codex planner hands its draft to
Claude — requirements grill R3); quickfix/degraded windows (exempt, R4);
non-Claude sessions (refused, R7); any change to how humans approve
(`plan approve --by`, 0029 stands).

## Acceptance Criteria

From the roadmap item, amended by the requirements grill (R1–R7) and the
exploration finding on 0029:
1. A hook records a story-scoped plan-mode marker (timestamp, sha256 of the
   plan file) for every `Write`/`Edit` made with `permission_mode: "plan"`
   to a plan file; `plan save --from` and `task plan save --from` refuse a
   file whose exact digest has no marker in the active story; `plan
   approve` and `task approve` re-check it.
2. The hook logs every `AskUserQuestion` (questions, options, chosen
   answers) one record per file under the active story; the grill recorder
   for spec, requirements, plan and task gates requires each
   `rounds[].question` to match a logged record, enforces floors
   spec 2 / requirements 1 / plan 2 / task 1, and requires
   `frontier_empty: true` on the final round.
3. The task frontier is author-task-plan → grill → approve → stage start →
   delegate; `record_grill_from_json.py --gate task` refuses when no task
   plan is saved; `forge next` prints the enforced order for planning and
   implementing.
4. Gate tests: a plan authored outside plan mode is refused; a grill with
   an unlogged round, below the floor, or without `frontier_empty` is
   refused; the happy path passes; the new script and hook entries are
   vendored and integrity-checked by the existing mechanisms.

## Technical Approach

**Signal.** Claude Code delivers `permission_mode` on every tool event
(`pre_tool_use.py:187` already reads it). In plan mode the only writable
file is the plan (`~/.claude/plans/<name>.md`), so a `Write`/`Edit` with
`permission_mode == "plan"` is proof the content was authored in plan
mode. `ExitPlanMode` itself is not hookable (0029) and is not needed.

1. **`factory/scripts/post_tool_use.py`** (new; registered in `forge.py`'s
   hook dispatcher next to `pre_tool_use`). Reads stdin JSON; fail-open on
   unparseable input (0038: a logging hook must never block). Two branches:
   - `tool_name in {Write, Edit, MultiEdit}` and `permission_mode == "plan"`
     → read the file at `tool_input.file_path` after the write, record
     `.factory/stories/<key>/plan-mode/<uuid>.json` =
     `{path, sha256, at, session_id, generated_by: "claude-code:plan-mode"}`.
     Active story from `run_state_path`; no active story → no record.
   - `tool_name == "AskUserQuestion"` → record
     `.factory/stories/<key>/grill-rounds/<uuid>.json` =
     `{questions: [{question, options, chosen}], at, session_id}` from
     `tool_input.questions` and `tool_response` (answers). No free-text
     notes are stored.
   Both validated by new schemas `factory/schemas/plan-mode-marker.json`
   and `factory/schemas/grill-round.json` via `validate_payload`.
2. **Wiring.** `.claude/settings.json` gains `PostToolUse` with matcher
   `Write|Edit|MultiEdit|AskUserQuestion` → `forge hook post_tool_use`.
   `.codex/hooks.json` unchanged (Codex has neither plan mode nor
   AskUserQuestion; R3). Both files are already in `COPY_CLAUDE`/
   `COPY_CODEX`; `factory/` is copied wholesale; `VENDOR_MANIFEST.json` is
   regenerated by init/upgrade — no new vendoring code.
3. **Plan-mode check.** New helper `require_plan_mode_marker(base, story,
   source_path)` in `factory_lib.py`: sha256 of the exact file bytes must
   equal a marker's `sha256` in the active story. Called in
   `plans.cmd_save()` after source existence (before
   `_require_matching_plan_grill`), in `plans.cmd_approve()`, in
   `tasks.cmd_plan_save()` after reading `source`, and in
   `tasks.cmd_approve()`. The plan-mode file is saved verbatim (R5); the
   existing `plan_digest_without_assumptions` stays for grill/approval
   binding — the marker binds the raw file.
4. **Round provenance.** In `record_grill_from_json.py`, after base schema
   validation (line ~200), for gates spec/requirements/plan/task: load the
   story's `grill-rounds/*`; each `rounds[].question` must equal a logged
   question (exact string) and `chosen` must equal the logged answer;
   count ≥ floor (`GATE_ROUND_FLOORS = {spec: 2, requirements: 1, plan: 2,
   task: 1}`); the last round carries `frontier_empty: true`. Spec and
   epics gates that run before any story exists (pre-sign-off) read
   `.factory/grill-rounds/` at repo root instead — same schema. The task
   branch additionally refuses when `task-plans/<id>.md` is absent.
5. **Frontier order.** `task_frontier_state()` (`factory_lib.py:~1603`)
   routes `author-task-plan` before `grill`; `tasks.cmd_plan_save()` stops
   requiring a grill (`require_ready_task(..., require_grill=False)` or
   equivalent); `stage start` still requires both. `phase.py` planning
   route prints "1. plan mode (hook records your plan) 2. grill via
   AskUserQuestion until frontier_empty 3. plan save --from
   <plan-mode file> 4. human: plan approve"; implementing route prints
   the new task order.
6. **Docs.** `docs/specs/accountable-engineering-loop.md`: replace "a
   zero-gap grill may validly have zero rounds" with the floors +
   attestation rule; `docs/specs/plan-approval.md`: plan mode remains the
   presentation *and* the authorship proof via `permission_mode`; both
   re-confirmed with recorded grills. Decision `0048-plan-mode-and-grill-
   provenance` records the mechanism and the per-gate floors.
7. **Tests** (`factory/tests/test_gates.py`, reusing `repo`, `intake`,
   `save_plan`, `record_grill`, `task_grill_payload`,
   `seed_task_grill_frontier`, `record_skeleton_then_frontier`, `hook()`):
   `post_tool_use` records a marker for a plan-mode Write and nothing for
   a normal-mode Write; `plan save` refuses without marker, passes with;
   `task plan save` likewise; grill recorder refuses unlogged round /
   below floor / missing `frontier_empty`, passes the happy path; task
   grill refuses without a saved task plan; frontier order test updated
   (existing inverse-order tests at ~15112 flipped, not deleted);
   `check_vendor_integrity` covers the new script.
8. **Live verification** (orchestrator, not Codex): after task 1 lands, in
   this session trigger one AskUserQuestion and one plan-mode Write and
   confirm both records appear — the only way to verify Claude Code's
   PostToolUse payload for these tools (docs do not state it).

Rejected simpler shapes: (a) marker on `ExitPlanMode` — not hookable
(0029). (b) time-window instead of digest — lets post-exit edits through
(R1). (c) extend `pre_tool_use.py` instead of a new script — PreToolUse
fires before the file exists for `Edit`, so the digest would be wrong; the
post hook reads the written file. (d) require rounds only on task grills —
the failure observed was on story plans (R2).

## Decisions

- `docs/decisions/0048-plan-mode-and-grill-provenance.md` (new):
  `permission_mode == "plan"` writes are the authorship proof; exact-digest
  match; AskUserQuestion ledger is the only sanctioned round source; floors
  spec 2 / requirements 1 / plan 2 / task 1 + `frontier_empty`; task plan
  precedes task grill; Codex planner hands back to Claude; quickfix/degraded
  exempt; non-Claude sessions refused. Supersedes the zero-rounds clause of
  0044 and the "not the enforcement signal" clause of 0029 (0029's human
  approval mechanism stands).

## Surface Impact

| Surface | Class | Note |
|---|---|---|
| Runtime behaviour | Changed | new PostToolUse hook; recorders refuse without provenance |
| API | N-A | no network surface |
| Data / schema | Changed | two new schemas; two new per-story record dirs |
| CLI / ops | Changed | `plan save`/`task plan save`/`approve` refusals; `forge next` text; task frontier order |
| UI | Read-only | board reads task state derivation unchanged in shape |
| Docs | Changed | two specs amended + re-confirmed; decision 0048; WORKFLOW.md task-loop paragraph |
| Tests | Changed | gate tests for every refusal and the happy path; inverse-order tests flipped |

## Task Decomposition

1. **post-tool-use-ledgers** — script, dispatcher entry, two schemas,
   settings wiring, unit tests for both record kinds; no recorder changes
   yet. Serves AC 1 (marker), AC 2 (ledger). Write scope: `factory/scripts/
   post_tool_use.py`, `factory/scripts/forge.py`, `factory/schemas/
   plan-mode-marker.json`, `factory/schemas/grill-round.json`,
   `.claude/settings.json`, `factory/tests/test_gates.py`.
2. **plan-mode-gate** — `require_plan_mode_marker` + calls in plans.py and
   tasks.py; tests for refusal/pass. Serves AC 1, AC 4.
3. **round-provenance-gate** — grill recorder checks (ledger match, floors,
   `frontier_empty`, task plan present); frontier order flip in
   `task_frontier_state`/`tasks.cmd_plan_save`; `phase.py` text; tests
   flipped and added. Serves AC 2, AC 3, AC 4.
4. **docs-and-decision** — decision 0048; amend + re-confirm the two
   specs; WORKFLOW.md paragraph; `check_dual_runtime` green. Serves AC 4
   (docs) and closes the contradiction Codex found.
Sequential (2 and 3 both touch `factory_lib.py` and the gate suite).

## Grill resolutions (plan gate, 7 questions, 2 rounds; frontier empty)

- The marker check excludes the `## Implementation Assumptions` block the
  way `plan_digest_without_assumptions` does; `forge plan assume` is the
  only post-approval edit path.
- Pre-sign-off spec/epics grills log rounds under root-level
  `.factory/grill-rounds/`; same schema and hook, story key absent.
- Migration: a task grill recorded before its task plan stays valid if the
  task plan is saved before `stage start` (grill timestamp < task-plan
  timestamp); tested as a one-time tolerance.
- Four sequential tasks kept.
- If the live check shows AskUserQuestion answers are not delivered to the
  hook, the ledger stores questions + options only and the grill record
  carries `chosen`; recorded as an implementation assumption.
- Decision 0048 supersedes clause-level: 0044's zero-rounds sentence and
  0029's "not the enforcement signal" sentence; both records otherwise
  stand.
- Re-recording a grill after tree drift may reuse the same rounds when the
  interrogated text is byte-identical; a changed text requires new rounds.

## Risks

- Claude Code may not deliver `tool_response` for AskUserQuestion on
  PostToolUse → fall back to PreToolUse for questions/options and require
  only question-text match (chosen stays in the recorder payload). Decided
  at live verification after task 1; noted in the task-1 contract.
- `permission_mode` value string for plan mode assumed `"plan"` (matches
  Claude Code's documented modes) — task 1's live check confirms.
- Flipping the task order breaks in-flight stories that recorded a grill
  before a task plan → migration rule: existing grills stay valid if a task
  plan is saved before `stage start` (one-time tolerance, tested).
- Story-less spec grills (pre-sign-off) need a root-level rounds dir → same
  schema, same hook, story key absent.

## Verify Plan

- `python3 factory/scripts/verify.py` green (runs the gate suite).
- Live: one AskUserQuestion and one plan-mode Write in this session produce
  records under `.factory/stories/plan-mode-and-grill-provenance/`.
- `plan save --from ~/.claude/plans/<file>` for this very story succeeds
  only because this file was written in plan mode — the story proves its
  own gate.
- `check_dual_runtime.py`, `check_vendor_integrity.py` green; `forge
  upgrade --target <example>` carries `post_tool_use.py` and the settings
  entry.

