---
issue: FORGE-BOARD-5
title: knacklabs-upgrade-project skill (machinery upgrade + guided re-authoring)
status: approved
saved: 2026-08-08T18:33:13+00:00
story: FORGE-BOARD-5
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
  - 0030-harness-source-is-product-in-its-own-repo
  - 0031-workflow-modes-lite
  - 0032-jit-task-planning
---

# Plan — FORGE-BOARD-5: Safe pending-story repair + backfill provenance honesty

> Story FORGE-BOARD-5, epic `traceable-board`, spec `docs/specs/traceable-board.md`.
> Worktree `/Users/dev/Workdir/symphony-forge-UPG5`, branch off main.
> The deterministic primitives the upgrade skill (FORGE-BOARD-6) needs; split out
> after a Codex plan review found two blockers in a skill-only approach.

## Problem

A Codex review of the upgrade-skill plan surfaced two determinism/honesty
blockers that a skill (agent guidance) cannot fix:

1. **No safe way to re-author a legacy card.** The audit finds incomplete
   `pending` stories, but nothing can fill an existing card's blank fields
   safely: `roadmap add` can't touch an existing key, and the only general route
   — `roadmap import` — OVERWRITES every non-lifecycle field even on a `done`
   card (`roadmap.py:456`). Race: a card is `pending` at audit → another worktree
   ships it → a guided import rewrites its acceptance criteria while keeping
   `status: done`, silently passing new intent off as history. That violates
   determinism (`traceable-board.md`) and mark-don't-fabricate (`project-record.md`).
2. **The backfill can falsify provenance.** `forge project backfill` on a
   ZERO-match GitHub search auto-sets `predates_outcome_contract: true`
   (`project.py:189`), which then exempts the story's missing outcome + pr-link
   from `check_board_complete`. But zero-match also happens when a real PR exists
   with a non-key title/branch (exactly the FORGE-DELEG-1→#24 class) — so a
   linkable story is silently marked as predating the contract.

## Scope / Non-goals

**In scope:** (1) a deterministic `forge roadmap fill` that repairs an existing
`pending` card by filling ONLY blank fields, refusing active/done cards, and
recording the change; (2) the backfill honesty fix — zero-match no longer
auto-marks `predates`; it reports *unresolved provenance* (the audit stays red)
and `predates` becomes a human-confirmed action.

**Non-goals:** NOT the `knacklabs-upgrade-project` skill (FORGE-BOARD-6, which
drives these + `forge upgrade` with robust routing). NOT the D-0014 PR-body
matcher (separate enhancement). NOT changing `forge upgrade`/`doctor`.

## Acceptance Criteria

1. `forge roadmap fill <key> --story/--ac/--skill/--epic/--spec/--depends-on ...`
   sets ONLY fields that are currently blank/absent on the card, and REFUSES if
   the card's `status` is not `pending` (never touches active/done) — so it can
   never overwrite a shipped story's history. It records the change (an event).
2. `forge roadmap fill` refuses to overwrite a field that is already non-blank
   (blank-only; re-running is a safe no-op / reports what's still blank).
3. `forge project backfill` on a ZERO GitHub match no longer sets
   `predates_outcome_contract`; it reports the story as unresolved provenance and
   leaves `check_board_complete` failing for it until a human resolves it
   (`forge pr-link` if the PR is found, or a human-confirmed predates path).
4. A story whose PR is uniquely recoverable still links (unchanged); the
   FORGE-BOARD-4 dogfood result stays valid (its 10 stories all matched; none
   relied on zero-match→predates).

## Technical Approach

### `forge roadmap fill` — the safe repair primitive (new)

`cmd_fill` in `factory/scripts/forge_cli/roadmap.py`, registered in `forge.py`.
Loads the item by key; **refuses if `status != "pending"`** (the history guard);
for each provided field, sets it ONLY if currently blank (`_blank`) — a non-blank
field is left untouched (or refused with a clear message). Reuses the existing
field validators (`ITEM_SKILLS`, `check_item`, `resolve_spec_reference` for
`--spec`) and `missing_story_contract_fields` to report what remains blank.
Appends a `roadmap-filled` event (`events.append_event`). This is the
deterministic enforcement the skill drives: the agent proposes values, the human
confirms, `fill` applies them safely.

### Backfill honesty — zero-match → unresolved, not predates

In `factory/scripts/forge_cli/project.py:backfill_project`, the ZERO-match branch
stops setting `predates_outcome_contract`. Instead it records the story as
unresolved (report + skip; the audit's `board_problems` already flags its missing
pr-link, so it stays red). `predates` is set only by a human-confirmed path —
either a new `--predates` confirmation flag / a small `forge project mark-predates
<key> --reason` (records who/why), or documented as a manual roadmap action.
Existing behaviour for unique matches (link) and 2+ ambiguous (report+skip) is
unchanged.

## Decisions

No new decision. All 28 active reviewed (frontmatter). Load-bearing: **project-record**
(the fill command's pending-only + blank-only guards are what MAKE re-authoring
honest; the backfill fix stops silent provenance fabrication), **0001**
(determinism — the repair is a deterministic gate, not agent discipline),
**0011**/**0025**. No contradiction with an active decision. (Codex's finding
that a skill-only path violates determinism is what motivated adding this command;
the earlier plan's "no new command" non-goal is deliberately reversed.)

## Surface Impact

- `factory/scripts/forge_cli/roadmap.py` — NEW `cmd_fill` + the pending-only,
  blank-only guards.
- `factory/scripts/forge_cli/project.py` — backfill zero-match → unresolved; the
  human-confirmed predates path.
- `factory/scripts/forge.py` — register `forge roadmap fill` (+ mark-predates if
  a command).
- `factory/tests/test_gates.py` — fill (blank-only, refuse active/done, race,
  no-op re-run) + backfill (zero-match no longer predates; unique still links).

## Task Decomposition

1. **FORGE-BOARD-5.1 — `forge roadmap fill` (safe pending repair)** (no deps) —
   the command + pending-only/blank-only guards + event; tests incl. refuse
   active/done and a status-change race.
2. **FORGE-BOARD-5.2 — backfill provenance honesty** (dep: 5.1 only for shared
   test scaffolding) — zero-match → unresolved (not predates); human-confirmed
   predates path; tests that a zero-match story stays red and a unique match still
   links.

## Risks

- **The pending-only guard is the whole safety story.** A bug that let `fill`
  touch a done card would reintroduce the fabrication Codex flagged — reviewer_focus
  + a test that active AND done cards are refused, and that a card flipping to
  done mid-flight is refused on write.
- **Backfill fix must not re-red the harness board.** The FORGE-BOARD-4 dogfood
  linked all 10 via unique matches (no zero-match→predates was used), so removing
  auto-predates leaves `check_board_complete` green on main — verify against the
  live board before/after.
- **`--kind feature`; net-additive** (a new command + a guard change + tests).

## Verify Plan

- **Gate tests** (`factory/tests/test_gates.py`): `fill` sets a blank field on a
  pending card, refuses a non-blank field, refuses an active card, refuses a done
  card, and a re-run is a no-op; `backfill` zero-match leaves the story unlinked
  and NOT predates (board stays red), unique match still links, ambiguous still
  reports.
- **Determinism:** `check_dual_runtime.py` + `verify.py` green.
- **Live smoke:** on a fixture, `forge roadmap fill` completes a pending card and
  the audit gap clears; on a done card it refuses; `forge project backfill`
  against a zero-match fixture reports unresolved and the audit stays red.
