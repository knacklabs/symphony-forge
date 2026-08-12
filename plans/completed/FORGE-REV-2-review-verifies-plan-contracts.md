---
issue: FORGE-REV-2
title: Review verifies plan contracts
status: approved
saved: 2026-08-12T12:17:24+00:00
story: FORGE-REV-2
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
  - 0033-gate-a-declares-all-work-records
  - 0034-vendored-docs-are-client-safe
  - 0035-commit-belt-keeps-ledger-fresh
  - 0036-client-gates-arm-on-roadmap
  - 0037-strict-role-split
  - 0038-portable-fail-closed-hooks
---

# FORGE-REV-2 — Review verifies plan contracts

## Problem

Review is plan-blind, so incomplete implementation is invisible to it. The
decomposition schema carries objective, acceptance_criteria, write_scope,
required_tests, verify_commands, and reviewer_focus — but no field for the
plan invariants a task must satisfy, and reviewer_focus is one free-text
string. The reviewer never receives the plan or the task's contracts, and
nothing asks it for a completeness verdict: it can only judge code that
exists, so missing code looks like nothing. Review findings
({category, area, summary}) have no place to record "contract X:
implemented / partial / missing", so even a diligent completeness check
evaporates instead of becoming a recordable, gateable artifact. pr_ready.py
checks that review artifacts exist, not that every plan contract was
verified implemented. The implementer side already has the right pattern:
compose_brief inlines the task contract into the delegation brief. Review
needs the same treatment.

## Scope / Non-goals

In scope: factory/schemas/decomposition.json, factory/schemas/review.json,
factory/scripts/record_decomposition_from_json.py,
factory/scripts/record_review_from_json.py, a new small
factory/scripts/forge_cli/review_brief.py module registered in
factory/scripts/forge.py, factory/scripts/pr_ready.py,
factory/prompts/reviewer.md, factory/prompts/pr-ready.md,
factory/tests/test_gates.py.

Non-goals (deliberately lazy): no new artifact type (verdicts ride the
existing quality review), no new recorder script, no structured replacement
for reviewer_focus, no change to tasks without plan_contracts — fully
backward compatible; quickfixes stay ceremony-free.

## Acceptance Criteria

- record_decomposition_from_json.py refuses a malformed plan_contracts
  entry (non-object, wrong/missing keys, empty strings, duplicate contract
  id across the decomposition) and accepts well-formed entries.
- `./forge review-brief <task-id>` writes
  .factory/review-briefs/<task-id>.md (repo-relative on purpose —
  autoreview's --prompt-file requires it) containing the task's
  plan_contracts, reviewer_focus, and the verdict instruction; `--all`
  writes the branch-wide brief with every task's contracts for closeout.
- record_review_from_json.py refuses a quality artifact that omits a
  verdict for any declared contract, refuses unknown contract ids and bad
  verdict values, and records any partial/missing verdict as a blocking
  finding.
- pr_ready.py refuses while any task with plan_contracts lacks a quality
  review with all-implemented verdicts.
- Decompositions without plan_contracts behave exactly as today (existing
  suite green).

## Technical Approach

1. Schema factory/schemas/decomposition.json: document optional per-task
   plan_contracts — list of {id, statement, source} (source = plan
   file+section). Task-level validation lives in
   record_decomposition_from_json.py like required_tests: exactly the three
   non-empty string keys, ids unique across the whole decomposition (so
   verdicts map unambiguously).
2. Review brief composer: new small forge_cli/review_brief.py (NOT in
   delegate.py — delegate_mod is None on Windows and brief composition is
   pure file writing that must work there). `./forge review-brief
   [task-id|--all]` writes .factory/review-briefs/<task-id>.md (or all.md)
   via safe_factory_write_bytes, containing plan_contracts, reviewer_focus,
   and: "For each contract, emit a verdict — implemented | partial |
   missing — with file:line evidence. Then review the diff normally; the
   contract check does not replace the quality/perf/security lenses."
3. factory/prompts/reviewer.md step 1: run autoreview with --prompt-file
   .factory/review-briefs/<task-id>.md when the task declares
   plan_contracts; the quality artifact must include contract_verdicts.
4. Schema factory/schemas/review.json: optional contract_verdicts —
   [{contract_id, verdict: implemented|partial|missing, evidence}].
   record_review_from_json.py: when the recorded decomposition declares any
   plan_contracts, a quality artifact must verdict every one of them;
   partial/missing verdicts are appended to blocking_findings as structured
   findings (category plan-contract-<verdict>, area = contract source), so
   the existing review_passed gate does the blocking.
5. Gate pr_ready.py: after review_problems, refuse when any declared
   contract lacks an "implemented" verdict in the recorded quality review —
   a backstop independent of the recorder, since evidence can predate the
   schema change.
6. Closeout factory/prompts/pr-ready.md: the branch-wide autoreview at
   closeout takes `./forge review-brief --all` (all tasks' contracts) as
   its prompt file — catches a later stage undoing an earlier stage's
   contract, which per-task review can't see.

## Decisions

No new decision record: this extends the existing review evidence chain
under 0001 (schema-validated recorders), 0011 (orchestrator runs
autoreview), and 0018 (delegation gates). No active decision is
contradicted; reviewed list attested in frontmatter.

## Surface Impact

New forge subcommand `review-brief` (available on Windows). New optional
schema fields (decomposition task plan_contracts; review
contract_verdicts). New refusals only when plan_contracts are declared.
Prompt contracts reviewer.md and pr-ready.md gain the contract-check
instruction. No changes for existing decompositions or client repos until
they declare contracts.

## Task Decomposition

One bounded task, REV2-T1 (see recorded decomposition): the whole chain
lands together — schema fields without the recorder/gate would be dead
metadata, and the gate without the brief composer would be unsatisfiable.
Write scope: the nine files in Scope. Sequential; no parallelism.

## Risks

- Story-level quality artifact vs per-task contracts: resolved — the single
  quality artifact must verdict the union of all tasks' contracts; recorder
  refuses partial coverage.
- Evidence recorded by an older recorder omitting verdicts: pr_ready
  backstop refuses independently.
- Windows: review_brief.py imports no delegate/companion machinery;
  registered unconditionally in forge.py.
- Legacy decompositions: plan_contracts absent → every new branch is a
  no-op (regression suite proves it).

## Verify Plan

- python3 factory/scripts/verify.py (deterministic verify).
- python3 -m pytest factory/tests/test_gates.py -q — new cases:
  decomposition recorder refusals/acceptance for plan_contracts;
  review-brief content per-task and --all; quality recorder refusal without
  verdicts, blocking finding on partial; pr_ready refusal until
  all-implemented; regression: no-contract decomposition unchanged.
- python3 factory/scripts/check_dual_runtime.py stays green.
