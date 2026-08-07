---
issue: FORGE-MODES-1
title: Developer-selectable workflow modes (Lite mode)
status: approved
saved: 2026-08-07T07:34:48+00:00
story: FORGE-MODES-1
decisions_reviewed:
  - 0001-determinism-contract
  - 0002-concurrency-one-task-per-branch
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
  - 0031-workflow-modes-lite
---

# FORGE-MODES-1 — Developer-selectable workflow modes (Lite mode)

## Problem

The lifecycle is terminal at ship: `pr_ready.py` archives the story, deletes
task-scoped `.factory` state, reduces `run.json` to project fields, and the
always-armed planning lock (0013) re-arms — so every product write after ship is
denied. A small, human-supervised fix (the common post-PR reviewer tweak) then
has only two doors with nothing between: a full re-intake (plan → grill →
decompose → stages → verify → three reviews → outcome → ship), or a `quickfix`
window that unlocks writes with no evidence at all. 0013's threat model is agent
drift, not human distrust, so the supervised small fix is exactly the low-risk
case the heavy loop was never aimed at. Decision **0031** authorizes a
proportionate lane; this story builds it.

## Scope / Non-goals

**In scope:** developer-selectable `lite` mode as a generalization of the
quickfix window — a human-initiated, ledgered, bounded write lane that uses
`terra@high` for the fix and closes only after one autoreview run with no
blocking findings; the `forge mode` / `forge fix` CLI; the `harness.yaml
modes.lite` pin; open-window banners; and the doc updates 0031 implies. An open
lite window authorizes product writes generally: `forge fix` (terra@high) is the
sanctioned, recorded path, but a supervising dev/Claude may also hand-edit — both
are captured by the file manifest and the mandatory close review (grill Q2).
Lite is most meaningful post-ship / with no active approved plan; opening it
mid-story is allowed but redundant (the story loop already authorizes writes).

**Non-goals:** no change to `pr_ready.py`'s ship checks (it already refuses to
ship with an open window); no post-merge / deploy phase (phase 9 stays out of
scope); no change to the `full` loop, the one-autoreview-run contract (0011), or
one-story-per-worktree (0002); `quickfix` keeps its current trust-and-trace
behavior unchanged.

## Acceptance Criteria

- **AC1** — `./forge mode lite --by "<name>" --reason "<why>"` opens a window
  recorded with `profile: lite` and `base_sha` = HEAD-at-open; while it is open,
  `pre_tool_use.py` authorizes a product write and records it. `./forge mode
  list` shows the open window; `./forge mode done` closes it (see AC3). There is
  no `mode full` (closing is returning to full).
- **AC2** — `./forge fix "<desc>"` refuses with no open lite window; with one
  open it runs a **write** delegation whose recorded row shows
  `model: gpt-5.6-terra, effort: high, write: true`, sourced from `harness.yaml
  modes.lite` (not the `implementation` pin). It does **not** auto-commit — the
  dev/Claude commits the fix.
- **AC3** — `./forge mode done` on a lite window: refuses if the product working
  tree is dirty ("commit the fix first"); measures the `base_sha→HEAD` diff and
  refuses if distinct product files exceed the budget; requires
  `.factory/reviews/{quality,performance,security}.json` present, stamped at
  HEAD, no blocking findings — and **these record post-ship**, because
  `record_review` accepts an open lite window in place of approved-plan +
  decomposition (grill Q8). On success it appends a ledger `done` row with the
  non-empty file manifest and archives the review artifacts into that record.
- **AC4** — `harness.yaml` carries a `modes.lite` block (`model`, `reasoning`,
  `gate`, `bound`); `check_dual_runtime.py` stays green.
- **AC5** — session-start and `./forge next` name an open lite window and its
  "one review required to close" state.
- **AC6** — `docs/decisions/0013`, `WORKFLOW.md`, and
  `docs/memory/factory-entry-contract.md` describe the third exit; the `/forge`
  skill maps "use lite mode" → `./forge mode lite`; decision 0003 gains a
  one-line "see 0031 (lite mode)" cross-reference so it no longer reads as
  absolute.

## Technical Approach

Reuse-first: lite mode is **not** new authorization machinery — it is the
existing quickfix window plus a `profile` field, a `base_sha`, a model profile,
and a profile-specific close gate. One mechanism, two profiles.

- **Window (`forge_cli/quickfix.py`).** `cmd_start` records `profile`
  (`quickfix`|`lite`) and, for lite, `base_sha` = current HEAD. A new `cmd_mode`
  dispatches `mode lite|list|done`; `mode lite` is `cmd_start` with
  `profile=lite` and required `--by`/`--reason`. The **closer is one command**:
  extend `cmd_done` to dispatch the gate by `profile` (quickfix = close as
  today; lite = the AC3 gate), exposed as `forge mode done` (and `quickfix done`
  stays for the quickfix profile). `pre_tool_use.py`'s existing open-window
  authorization (guard L281-313) covers lite for free — no authorization change;
  banners (`session_start.py`, `phase.py`) name the profile.

- **Fix path — a thin new `forge_cli/fix.py`**, not a `delegate --lite` flag,
  because `cmd_delegate` is hard-coupled to a decomposition task + active stage,
  which lite lacks (recommendation held through the grill). `forge fix "<desc>"`
  requires an open lite window, composes a minimal brief (description + active
  decisions + scope lessons + implementer contract, reusing `compose_brief`'s
  section helpers), reads model/effort from a new `mode_run_config(base,"lite")`
  over `harness.yaml modes.lite`, and launches the companion `--write` reusing
  `companion_script`, `append_delegation`, `_acquire_delegation_lock`,
  `_wait_and_reap` verbatim (inheriting the `normalize-ps-derived-identity` fix
  and the `launch-` id prefix that keeps the ledger out of secret scanners).
  Lite-fix rows reuse the **window id as `task`** so they satisfy
  `delegation.json` (extend the schema if needed). It does **not** commit;
  authorship of the commit stays human. It carries **none of the 0018 stage-done
  gates** (there is no stage) — lite's gates are the budget + close review.

- **Close gate (`forge_cli/quickfix.py cmd_done`, lite path).** Refuse on a
  dirty product working tree. Measure the committed `base_sha→HEAD` diff, count
  distinct product paths (`product_path()` classification), refuse if over
  `bound`. Require the three review artifacts stamped at HEAD with no blocking
  findings, reusing an extracted `pr_ready.py` review-load + blocker helper. To
  make review recording work post-ship, add a `lite_window_ok` path to
  `factory_lib.gate` that **only `record_review_from_json.py` passes** — the
  shared gate stays strict for verify/tests. On success, append the ledger
  `done` row with the manifest and fold the review artifacts into it (evidence
  lifetime, 0025).

- **Pins (`harness.yaml`).** Add `modes.lite: {model: gpt-5.6-terra, reasoning:
  high, gate: "...", bound: 5}`, landed by PR like every pin.

## Decisions

**No new decisions beyond 0031** (accepted, `confirmed_by: vrknetha`). 0031
governs every choice here and, explicitly:
- **extends 0003** (Terra explores, Sol implements) to permit a `terra@high`
  *write* inside the bounded lite lane — recorded, not accidental; task 4 adds a
  cross-reference from 0003 so it no longer reads as absolute;
- **adds a third exit** to 0013's always-armed planning lock (approved plan |
  quickfix | lite window).

Plan-level shape choices (not cross-cutting decisions, all held through the
grill): `forge fix` as a sibling command; the close-gate bar as "no blockers"
(fixed by 0031); a supervised hand-edit is allowed under a lite window (the pin
governs delegated fixes only); the review recorder's `lite_window_ok`
relaxation scoped to review recording alone.

## Surface Impact

| Surface | Class | Note |
|---|---|---|
| Runtime behavior | Changed | Planning lock gains a third authorized state (open lite window); `mode`/`fix` flows; review recording accepts a lite window. |
| API | N-A | No external/network API in the harness. |
| Data / schema | Changed | Window record gains `profile` + `base_sha`; `harness.yaml` gains `modes.lite`; delegation ledger gains lite-fix rows keyed by window id — `factory/schemas/delegation.json` must accept that shape. |
| CLI / ops | Changed | New `./forge mode {lite\|list\|done}` and `./forge fix "<desc>"`; `quickfix` verbs unchanged. |
| UI | N-A | No UI surface. |
| Docs | Changed | 0013, WORKFLOW.md, factory-entry-contract.md, 0003 cross-ref, `/forge` skill. |
| Tests | Changed | New gate tests in `factory/tests/test_gates.py`. |

## Task Decomposition

Capability-driven, sequential (0007 — each task is a stage), each tracing to
criteria:

1. **The lite window** — `quickfix.py` (`profile`, `base_sha`, `cmd_mode`,
   profile-dispatching `cmd_done`), `forge.py` wiring, session-start/`phase.py`
   banners, tests. → AC1, AC5.
   *write_scope:* `factory/scripts/forge_cli/quickfix.py`,
   `factory/scripts/forge.py`, `factory/scripts/session_start.py`,
   `factory/scripts/forge_cli/phase.py`, `factory/tests/test_gates.py`.
2. **The lite fix path** — `forge_cli/fix.py`, `mode_run_config`, `forge.py`
   wiring, `harness.yaml modes.lite`, delegation-schema acceptance, tests.
   → AC2, AC4.
   *write_scope:* `factory/scripts/forge_cli/fix.py`,
   `factory/scripts/forge_cli/delegate.py` (extract `mode_run_config` / shared
   launch helpers), `factory/scripts/forge.py`, `harness.yaml`,
   `factory/schemas/delegation.json`, `factory/tests/test_gates.py`.
3. **The lite close gate** — dirty-tree refusal, `base_sha→HEAD` budget
   measurement, shared review-check helper, the `lite_window_ok` review-recorder
   relaxation, on-close evidence archival, tests. → AC3.
   *write_scope:* `factory/scripts/forge_cli/quickfix.py`,
   `factory/scripts/pr_ready.py`, `factory/scripts/factory_lib.py`,
   `factory/scripts/record_review_from_json.py`, `factory/tests/test_gates.py`.
4. **Docs + contract** — 0013, WORKFLOW.md, factory-entry-contract, 0003
   cross-ref, `/forge` skill. → AC6.
   *write_scope:* `docs/decisions/0013-always-armed-planning-lock.md`,
   `docs/decisions/0003-model-tiers-terra-explore-sol-implement.md`,
   `WORKFLOW.md`, `docs/memory/factory-entry-contract.md`, the `/forge` skill.

## Risks

- **Lite is a genuine loosening** (unified/anytime + one review). Mitigation is
  0031's design: the file budget, the ledger + file manifest, and the required
  review; recurring findings still escalate to a refactor, never a fourth patch
  (0005). Tripwire: if review flags a "lite-bypass" class, escalate per
  WORKFLOW.md Recurring Findings.
- **`forge fix` carries none of the 0018 stage-done gates** (no stage). The
  substitute is the budget (files) + the mandatory close review; the model pin
  governs delegated fixes but a supervised hand-edit can bypass it (accepted,
  grill Q2). Both are captured by the manifest.
- **Gate relaxation must stay scoped.** `lite_window_ok` is passed only by
  `record_review`; verify/tests keep the strict `gate()`. A test asserts a lite
  window does **not** unlock verify/test recording.
- **New sanctioned terra write path.** `terra` is read-only today via
  `/codex:rescue`; lite fix is the only place it writes, raw `codex exec` stays
  hook-blocked, and delegate's reaping honors `normalize-ps-derived-identity`.
- **Delegation ledger collision (watch x2).** Lite-fix rows land in
  `.factory/delegations.jsonl`; the `launch-` prefix keeps secret scanners
  quiet. Tripwire per 0005 if it recurs.
- **Based off unshipped FORGE-LOCK-1.** Rebase onto main once FORGE-LOCK-1
  merges; the `plans/debt/FORGE-LOCK-1` artifact on this branch is reconciled at
  merge (`roadmap heal` handles roadmap status).

## Verify Plan

1. **Deterministic** — `python3 factory/scripts/verify.py` (structural,
   typecheck, tests) and `python3 factory/scripts/check_dual_runtime.py` green.
2. **Gate tests** (`factory/tests/test_gates.py`): a `profile: lite` window
   authorizes a write and records `base_sha` (AC1); `forge fix` refuses with no
   window and records `gpt-5.6-terra/high/write` with one open (AC2); `mode
   done` refuses on a dirty tree, refuses over-budget on the committed diff,
   refuses without fresh no-blocker reviews, and passes with them — recording a
   review **succeeds under an open lite window with no approved plan** and a
   lite window does **not** unlock verify/test recording (AC3); `modes.lite`
   parses and `check_dual_runtime` stays green (AC4).
3. **Live smoke (post-PR scenario)** — on a shipped-state branch (no approved
   plan): `forge mode lite` → `forge fix "<tiny change>"` → commit → run
   autoreview over `base_sha→HEAD` → `forge mode done`, confirming the planning
   lock never forced plan mode, the review recorded despite no approved plan,
   and the ledger manifest + archived reviews exist end to end.
