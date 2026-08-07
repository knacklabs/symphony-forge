---
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

# FORGE-BOARD-1 — Enforcement gates: every PR ties to a complete on-board ticket

## Problem

The provenance chain (spec→story→plan→decomposition→stage→evidence→outcome)
stops one step short of the PR, and board-completeness checks are only advisory,
so PRs go untraceable (a PH-5 audit: 30 of 36 merged PRs invisible in-repo) and
the board can rot until agents can no longer reconstruct what shipped. The
confirmed `traceable-board` spec's first story makes the two invariants —
**completeness** and **PR-linkage** — deterministic hard gates.

## Scope / Non-goals

**In scope:** the three deterministic gates from the spec's Enforcement section —
Gate C (intake refuses off-board keys), Gate A (a PR required-check that every PR
resolves to one complete on-board ticket/window), Gate B (auto-link the story↔PR
on merge + a red-main completeness invariant).

**Non-goals:** JIT per-task planning (a separate story — it amends 0007 and is
not a prerequisite here); the board/UI; the `--ac`-on-`--no-spec` drop and
tracker-mirroring removal (the ad-hoc/simplification story); the upgrade and
sanitise skills. No change to `pr_ready.py`'s frozen gate surface (0009) — this
story ADDS gates (CI + intake), it does not alter the existing ship gate.

## Acceptance Criteria

- **AC1 (Gate A)** — a PR cannot merge unless it resolves to exactly one on-board
  story (or a ledgered mode/quickfix window) whose done-flip and
  `.factory/history/<key>/` archive travel inside the PR's diff. A required CI
  check fails otherwise.
- **AC2 (Gate B link)** — once a PR has a number, the story↔PR link is captured
  automatically on the PR branch (a `pull_request` workflow runs `forge
  pr-link`), so it merges as committed history — no CI writes to main — and
  survives a clone with no remote (it lives in committed `.factory/events.jsonl`).
- **AC3 (Gate B invariant)** — main CI fails if any `done` story lacks a
  `pr-linked` event, an outcome (or `predates_outcome_contract`), or a
  `.factory/history/<key>/` dir.
- **AC4 (Gate C)** — intake refuses a roadmap key that is not on the board,
  naming `roadmap add --no-spec`.
- **AC5 (determinism)** — every gate is a deterministic script or CI check with
  unit tests; an agent with no memory of the rules cannot weaken any invariant.

## Technical Approach

Reuse-first; three self-contained check scripts + thin CI workflows.

- **Gate C — `factory/scripts/intake.py`:** `activation_state` already returns
  `absent | blocked | activate | done`; intake refuses only `blocked` today. Add
  a refusal for `absent`, with an error naming `roadmap add --no-spec`. One
  branch; the existing on-roadmap paths are unaffected.
- **Gate A — `factory/scripts/check_pr_ticket.py` + `.github/workflows/
  pr-ticket-check.yml`:** the script takes the base..head diff, the head branch,
  and the PR body (env from the workflow) and asserts exactly one work record —
  branch `feat/<key>-*` or a `Ticket: <key|window-id>` line — resolves; for a
  story, the key is on `plans/roadmap.json` and the diff flips it to `done` with
  `.factory/history/<key>/` added; for a window, its ledger `done` record is in
  the diff. Non-zero exit → the required check fails → merge blocked. The
  workflow runs on `pull_request`; it validates on this very PR (self-test).
- **Gate B — auto-link on the PR branch (pre-merge) + red-main invariant
  (`factory/scripts/check_board_complete.py` + `.github/workflows/pr-link.yml`
  + `.github/workflows/board-invariant.yml`):** a `pull_request` workflow, once
  the PR number exists, runs `forge pr-link <key> <PR#>` and commits the
  `pr-linked` event to the PR BRANCH — guarded to no-op if already linked so the
  push does not re-trigger itself — so the link travels IN the merge and **no CI
  writes to main**. Separately, on `main`, `check_board_complete.py` reads
  `plans/roadmap.json` + `.factory/events.jsonl` and fails if any `done` story
  lacks a `pr-linked` event, an outcome (or `predates_outcome_contract`), or a
  `.factory/history/<key>/` dir. Window-PRs are exempt from the story invariant:
  their ticket is the window id and their ledger `done` record is their proof.
  Reuses `load_events`, `load_items`, `load_outcome`/history paths, and the
  existing `forge pr-link` command.

Legacy stories that predate this contract are exempted by the same
`predates_outcome_contract` marker the outcome gate already uses.

## Decisions

**No new decisions beyond the confirmed `traceable-board` spec.** The spec's
determinism clause and Enforcement section already authorize these as hard CI
gates and place linkage in CI (because `pr_ready` runs pre-PR). The choice to ADD
CI gates rather than touch `pr_ready` is required by 0009 (frozen gate surface).
If the plan grill judges "completeness + PR-linkage are blocking CI invariants"
to be a stance worth its own record, it becomes a decision before decomposition.

## Surface Impact

| Surface | Class | Note |
|---|---|---|
| Runtime behavior | Changed | intake refuses off-board keys; two new CI gates block merges / redden main. |
| API | N-A | No network API. |
| Data / schema | Read-only | Reuses `events.jsonl` (`pr-linked` events), `roadmap.json`, history dirs; no schema change. |
| CLI / ops | Changed | New `check_pr_ticket.py`, `check_board_complete.py`, two `.github/workflows/`. |
| UI | Unchanged by design | Board/UI rendering of the link is a later story; this story only guarantees the data. |
| Docs | Changed | WORKFLOW.md gating model gains the two CI gates + Gate C. |
| Tests | Changed | Unit tests for both check scripts + the intake refusal, in `factory/tests/`. |

## Task Decomposition

Capability-driven, sequential (0007), each tracing to criteria:

1. **Gate C — intake refuses off-board.** `intake.py` + a test.
   → AC4. *write_scope:* `factory/scripts/intake.py`, `factory/tests/test_gates.py`.
2. **Gate A — PR-ticket required-check.** `check_pr_ticket.py` +
   `pr-ticket-check.yml` + tests. → AC1, AC5.
   *write_scope:* `factory/scripts/check_pr_ticket.py`,
   `.github/workflows/pr-ticket-check.yml`, `factory/tests/test_gates.py`.
3. **Gate B — branch auto-link + red-main invariant.** `check_board_complete.py`
   + `pr-link.yml` (pull_request → `forge pr-link`, commits to the branch,
   loop-guarded) + `board-invariant.yml` (main invariant) + tests; WORKFLOW.md
   gating note. → AC2, AC3, AC5.
   *write_scope:* `factory/scripts/check_board_complete.py`,
   `.github/workflows/pr-link.yml`, `.github/workflows/board-invariant.yml`,
   `WORKFLOW.md`, `factory/tests/test_gates.py`.

## Risks

- **CI workflows can't run locally.** Mitigation: the deterministic core is the
  CHECK SCRIPTS (unit-tested against fixture diffs/roadmaps/events); the workflow
  YAML is thin wiring, and Gate A self-tests on this very PR.
- **Auto-link pushes to the PR branch from CI.** It needs `contents: write` on
  the head ref and a loop guard (no-op when the `pr-linked` event already exists)
  so the push does not re-trigger the workflow. The PR number comes from
  `${{ github.event.pull_request.number }}`; local degraded mode keeps manual
  `forge pr-link` (per the spec).
- **Legacy/`predates_outcome_contract` stories** must not fail the invariant.
  Mitigation: reuse the existing marker; a test asserts a predating story passes.
- **`.github/workflows/` is harness-owned but mixed** (client workflows coexist).
  Only add harness-named workflow files; do not touch client workflows (per
  vendoring boundary).

## Verify Plan

1. **Deterministic:** `python3 factory/scripts/verify.py` (structural, typecheck,
   tests) and `check_dual_runtime.py` green.
2. **Gate tests** (`factory/tests/test_gates.py`): intake refuses an off-board
   key and names the ad-hoc path (AC4); `check_pr_ticket.py` passes a
   well-formed story PR fixture and fails on missing ticket / missing done-flip /
   two records (AC1); `check_board_complete.py` passes a complete board and fails
   on a done story missing pr-link / outcome / history, and passes a
   `predates_outcome_contract` story (AC2/AC3); a determinism test asserts each
   check is a pure script (no network, deterministic on fixtures) (AC5).
3. **Self-test:** Gate A's workflow runs on this PR and passes (this PR resolves
   to FORGE-BOARD-1 with its done-flip + history in the diff).
