---
issue: FORGE-BOARD-3
title: Ad-hoc capture + simplification: one capture path, stories-only board mirror
status: approved
saved: 2026-08-08T12:58:42+00:00
story: FORGE-BOARD-3
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

# Plan — FORGE-BOARD-3: Ad-hoc capture + simplification

> Story FORGE-BOARD-3, epic `traceable-board`, spec `docs/specs/traceable-board.md`.
> Worktree `/Users/dev/Workdir/symphony-forge-BOARD-3`, branch off clean main.

## Problem

Three small residual rough edges in the traceable-board model, from the spec's
"Ad-hoc capture — one path" and "Remove, to keep it simple" sections:

1. **Ad-hoc capture demands acceptance criteria at capture time.** `roadmap add`
   requires `--ac` unconditionally (argparse `required=True`, `forge.py:184`), so
   a dev's "what about X" can't be jotted as spec-debt without inventing ACs —
   friction that pushes ad-hoc ideas back into chat. AC should arrive with the
   spec, not at capture.
2. **WORKFLOW.md says task state is mirrored into the tracker** (`:6-8`, `:281-283`),
   which is the exact source of the "are tasks tickets?" ambiguity the spec calls
   out. The board mirrors *stories*; tasks are a story's internal stages.
3. **Manual `forge pr-link` still reads as a routine step**, but Gate B's
   `pr-link.yml` now automates it on every PR. Manual linking should be a
   degraded-mode fallback (CI unavailable), not a discipline anyone relies on.

## Scope / Non-goals

**In scope:** make `--ac` optional on the `--no-spec` path (still required with
`--spec`); reword WORKFLOW.md's Source-of-Truth to mirror stories only; add a
degraded-mode note demoting manual `pr-link` to a CI-unavailable fallback.

**Non-goals:** NOT removing the `pr-link` command, its Gate B automation, or any
test (all stay). NOT changing the spec-debt gate that keeps a `--no-spec` story
unplannable until `link-spec` (decision 0014 — preserved). NOT touching external
tracker code (there is none — task mirroring is docs-only). No new decision
record (this is simplification within the existing model).

## Acceptance Criteria

1. `roadmap add --no-spec --reason "..."` succeeds with NO `--ac`; the story lands
   as spec-debt (`origin: "adhoc"`, `spec_debt_reason` set, no `spec`) and stays
   unplannable until `spec confirm` + `link-spec` (0014 gate unchanged).
2. `roadmap add --spec ...` still REQUIRES `--ac` (a confirmed-spec story with no
   acceptance criteria is refused, as today).
3. WORKFLOW.md's "Source of Truth" mirrors stories only — no "task state is
   mirrored into the tracker" language remains.
4. `docs/degraded-mode.md` documents manual `forge pr-link` as a fallback for when
   `pr-link.yml` can't run (e.g. CI disabled / cross-fork), noting Gate B
   automates it normally.

## Technical Approach

### `--ac` optional on `--no-spec` (the only code change)

- `factory/scripts/forge.py:184` — change `--ac` from `required=True` to
  `required=False` (argparse can't express "required unless --no-spec"; enforce in
  code).
- `factory/scripts/forge_cli/roadmap.py:475-477` — the unconditional
  `if not criteria: fail("--ac is required")` guard moves INTO the `if args.spec:`
  branch (`:505`), so a `--spec` story still refuses empty ACs. In the
  `elif no_spec:` branch (`:511`), `criteria` may be empty; store what's given
  (an adhoc story simply carries no ACs until its spec is linked). The
  `spec_debt_reason` + `origin: "adhoc"` markers and the `plans.py:117-125`
  unplannable-until-linked gate are untouched.

### Docs simplification (no code)

- `WORKFLOW.md:6-8` — reword so an external tracker mirrors **stories** (branch,
  PR, checks, review evidence per `:9`), dropping "decomposition and task state
  are mirrored into it." `WORKFLOW.md:281-283` — drop the "(mirror to a tracker
  ...)" aside on the task list, or narrow it to stories.
- `docs/degraded-mode.md` — add a new `## 3.` section: when `pr-link.yml` can't
  run, record the link by hand with `forge pr-link <story> <reference>` (the same
  command the workflow runs); normally Gate B does this automatically.

## Decisions

No new decision. All 28 active decisions reviewed (frontmatter). Relevant:
**0014** (specs-before-signoff) — the spec-debt planning gate is preserved, so
dropping `--ac` does not let an unspecced story be planned; **0032/0023** (JIT
contract) — unaffected; the traceable-board spec's "Remove, to keep it simple"
and "Ad-hoc capture — one path" sections are the source. No contradiction with any
active decision (no open contradiction signal).

## Surface Impact

One task (disjoint but all-tiny facets, kept cohesive to avoid the split rule):

- `factory/scripts/forge.py` — `--ac` `required=False`.
- `factory/scripts/forge_cli/roadmap.py` — conditional AC guard (required with
  `--spec`, optional with `--no-spec`).
- `WORKFLOW.md` — Source-of-Truth mirrors stories only.
- `docs/degraded-mode.md` — manual `pr-link` fallback section.
- `factory/tests/test_gates.py` — a test that `--no-spec` without `--ac` records
  spec-debt, and that `--spec` without `--ac` still fails.

## Task Decomposition

One leaf task (this story is small; a single implementation session + one review).

1. **FORGE-BOARD-3.1 — Ad-hoc capture + simplification** (no deps) — the `--ac`
   conditionalization, the WORKFLOW.md stories-only reword, and the degraded-mode
   `pr-link` fallback, with the test above.

## Risks

- **Refactor source-delta ratchet.** The story is `--kind refactor`; the code
  delta in `factory/scripts/` is near-neutral (a guard moves, one flag flips). If
  pr_ready's ratchet reds because the test additions tip the net source delta
  positive, re-scope the kind to `feature` (the story genuinely adds the
  `--no-spec`-without-`--ac` capability). Decide at pr_ready with the measured
  delta, not preemptively.
- **Existing tests pass `--ac` with `--no-spec`.** They stay green — `--ac` stays
  ACCEPTED (just not required); those tests don't assert on the adhoc story's ACs.

## Verify Plan

- **Gate test** (`factory/tests/test_gates.py`): `--no-spec` without `--ac` records
  `origin: adhoc` + `spec_debt_reason` and no `spec`; `--spec` without `--ac`
  still fails with the AC message; the existing `--no-spec` + spec-debt lifecycle
  tests stay green.
- **Determinism:** `python3 factory/scripts/check_dual_runtime.py` green;
  `python3 factory/scripts/verify.py` green.
- **Live smoke:** `forge roadmap add TEST-X "t" --story "..." --epic <e> --no-spec
  --reason "..."` (no `--ac`) succeeds and lands as spec-debt; `forge plan save`
  on it still refuses with the `link-spec` message.
