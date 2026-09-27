---
status: superseded
superseded_by: 0093-lean-forge-rebuild
confirmed_by: "Ravi Kiran Vemula"
date: 2026-08-13
stories: [FORGE-ACC-1, FORGE-ACC-2, FORGE-ACC-3]
---

# Accountable Engineering Loop

## Context

Decision 0032 mandates skeletal decomposition and JIT task contracts, but
enforcement stops at `forge delegate`: `forge next` never routes contract
authoring or grilling, `stage start` accepts an ungrilled or incomplete
contract, an empty grill body records as a passing grill, the freshness
digest covers four fields and is caller-supplied, nothing bounds a stage
diff from above, and `docs/FACTORY.md` still demands full upfront contracts.
The confirmed `accountable-engineering-loop` spec captures the operator
direction (after the Herrengt article): judgment must be visible,
evidence-backed, independently challenged, and impossible to skip by
accident, with agents doing the heavy lifting and humans deciding only
authority questions.

## Decision

Amend 0032's enforcement, not its substance: readiness is derived from
contract-field presence and gated by a shared `require_ready_task()` at both
`stage start` and `delegate`; `forge next` routes author-contract → grill →
start → delegate; task grills must carry proofs (inspected refs, current
flow, total criteria mapping, keep/split/block, declare-or-empty new
abstractions with irreversibility notes) and a `block` emits a human
escalation packet; the grounding digest is derived internally from the full
contract, the approved-plan digest (excluding appended assumptions), and a
product-tree hash excluding `.factory/` and `plans/`; `stage done` refuses a
diff over the task's review budget (default 8 files / 400 lines — a policy
target, not a derived p90); the grilled `criteria_map` lands as FORGE-REV-2
`plan_contracts`.

## Consequences

- The frontier task is the only task with execution detail; the recorder
  refuses detail beyond it. Legacy decompositions keep completed history.
- Review cadence is unchanged (0011): task diff at `stage done`, one story
  autoreview, PR proofs — no per-commit review.
- Lite, quickfix, and degraded windows are untouched.
- Caller-supplied `--task-digest` is removed; recorders and gates derive.
- Over-budget work must split at the frontier (grill `split`) or carry a
  written reason for a higher budget; unreviewable diffs stop being
  representable.
- The board gains task rows (state, grill freshness, budget) derived from
  the same routing state as `forge next`.
- Amendment (2026-08-13, operator-sanctioned after the cross-model rescue
  audit): every grill delivers its rounds via AskUserQuestion — zero rounds
  refused; JIT re-records pin `generated_by: claude-code:plan-mode`; the
  initial decomposition is fully skeletal with a frozen task graph and
  immutable completed contracts; FORGE-ACC-3 adds approval and closeout
  integrity (approved-plan digest binding, recorded local review gating
  stage done, commit-before-done, one coherent branch review bound to
  review-brief --all, ordered closeout gates, clean-tree pr_ready, and
  write-window refusal during active stages).
