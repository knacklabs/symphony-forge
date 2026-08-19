---
slug: accountable-engineering-loop
title: Accountable engineering loop: JIT contracts enforced, grills carry proof, diffs stay reviewable
status: confirmed
saved: 2026-08-14T12:23:42+00:00
---

# Accountable engineering loop: JIT contracts enforced, grills carry proof, diffs stay reviewable

> Captured 2026-08-13 from operator direction, inspired by
> https://blog.florianherrengt.com/ai-removing-middle-class-software-engineering.html —
> implementation is cheap; the harness must make judgment visible,
> evidence-backed, independently challenged, and impossible to skip by
> accident. Agents do the heavy lifting; humans decide only authority
> questions.

## Why

Decision 0032 mandates skeletal decomposition and JIT task contracts, but the
implementation does not enforce it end to end:

- `forge next` routes an implementing story straight to `stage start` with no
  contract-authoring or grill step (`forge_cli/phase.py`).
- `stage start` checks no grill and no contract completeness; the only grill
  gate is `delegate`, which is bypassed for `--read-only` runs and for tasks
  with an empty `write_scope` (which silently degrade to read-only).
- An empty task grill body records as a valid `pass`: the schema requires no
  questions, no evidence, no system understanding.
- The grill digest covers only four task fields and `--task-digest` is
  caller-supplied.
- Nothing bounds a stage diff from above — every existing measurement refusal
  fires when too little changed, never too much.
- `docs/FACTORY.md` still demands full upfront task contracts, contradicting
  0032.

## Behaviour

- **Skeletal future tasks by validation.** The decomposition recorder refuses
  execution detail (`write_scope`, `required_tests`, `verify_commands`) on any
  task after the earliest pending leaf. JIT authoring stays the existing
  re-record path; readiness is derived from field presence — no stored
  `contract_status`.
- **One shared readiness gate.** `require_ready_task()` (factory_lib) checks
  the current leaf has non-empty `write_scope`, `required_tests`,
  `verify_commands`, `reviewer_focus`, plus the existing fresh-grill check.
  Called from both `stage start` (first refusal point) and `delegate`
  (defence in depth). An active stage with empty `write_scope` refuses
  instead of silently becoming read-only; explicit `--read-only` exploration
  remains.
- **`forge next` is the rail.** For the earliest unfinished task it reports
  exactly one next state: author contract → grill → `stage start` →
  `delegate`.
- **Task grills carry proof.** A task-gate grill requires: `inspected_refs`
  (paths must exist), `current_flow`, `criteria_map` (total coverage of
  acceptance criteria), `decision` keep|split|block, and `new_abstractions`
  (declare-or-empty: each new abstraction/dependency/service/table with
  evidence existing mechanisms are insufficient, plus irreversible effects
  with rollback notes). A `pass` with split/block or unresolved items is
  refused. A `block` produces a human escalation packet — issue, evidence,
  recommendation, alternatives, rollback — never a transcript link.
- **Grounding digest derived internally.** The recorder derives the grill
  digest from the full task contract, the approved-plan digest, and a
  product-tree hash excluding `.factory/` and `plans/` — evidence commits and
  a task's own in-progress commits never stale its grill. The plan digest is
  computed excluding the appended `Implementation Assumptions` section, so
  `forge plan assume` does not stale every task grill in the story (lesson:
  the assumptions ledger stales the plan it appends to). Gates re-derive.
  Caller-supplied `--task-digest` is removed.
- **Review budget.** Default 8 changed files / 400 changed lines
  (additions+deletions since stage baseline, excluding `.factory/` and
  `plans/`) — a policy target (measured p90s: 5/256 product-only, 20/672
  all-paths). Tasks may lower it; raising it requires a written reason.
  `stage done` refuses an over-budget diff; the composed brief states the
  budget so the worker stops and returns `--incomplete` before crossing it.
- **Contracts feed review (FORGE-REV-2).** Recording the frontier task's JIT
  contract lands its grilled `criteria_map` as that task's `plan_contracts`,
  so the quality review must verdict each criterion implemented and
  `pr_ready` gates on it. No new review artifact; no per-commit review —
  cadence stays decision 0011.
- **Board task visibility.** The board renders the in-flight story's task
  rows — state (skeleton|ready|grilled|active|done), grill freshness, budget
  usage — from the same derivation `forge next` uses.
- **Division of labor.** Frontier contracts are authored in Claude plan mode
  from read-only Codex exploration (JIT re-records pin
  `generated_by: claude-code:plan-mode`); the grill is a second independent
  read-only pass. Every grill delivers its rounds to the human through
  AskUserQuestion: repo-answerable questions arrive already answered with
  citations and a recommended resolution, authority questions (product,
  scope, architecture, security/privacy, destructive migration, material
  cost, reliability) arrive as escalation packets. A grill records only
  after its rounds are sanctioned. Each declared gap needs either a matching
  rounds entry or a named-source citation; a zero-gap grill may validly have
  zero rounds, including when it records sanctioned resolutions.
- **Approval and closeout integrity (FORGE-ACC-3).** Approved `plan save`
  stores an `approved_plan_sha256` (excluding the sanctioned assumptions
  appendix) that every later gate rederives — an edited plan requires a
  fresh grill and human approval, and `plan approve` refuses without a
  fresh matching plan grill on an awaiting plan. The task grill records
  `approved_by`, stamped from the operator's sanctioned rounds AFTER the
  grill passes; `require_ready_task` refuses a grill without the approval
  stamp, bound to the same grounding digest — an approved-then-edited
  contract needs re-grill and re-approval. `forge next`'s planning branch
  routes a pre-draft requirements round: the confirmed spec is re-grilled
  against current repository state (rounds via AskUserQuestion) before
  story-plan drafting is instructed. The initial decomposition
  recording refuses execution detail (including `reviewer_focus` and
  `plan_contracts`) on every task; later recordings freeze the initial
  id/order/dependency skeleton and permit contract changes only on the
  frontier; completed task contracts are immutable under a full-contract
  digest. The per-stage local review is recorded: a clean-review stamp in
  `stages.json` bound to stage id, task digest, composed-brief SHA,
  baseline, and the exact pre-commit diff digest — `stage done` refuses a
  missing or stale stamp, refuses uncommitted or staged product changes,
  and requires a non-empty committed stage delta. Branch review binds to a
  fresh `review-brief --all`: all three lenses carry one `review_run_id`,
  the brief SHA, and the branch diff digest, and the recorder rejects
  incoherent lens sets. Closeout order is gated: all stages done → branch
  review → verify → functional (when `user_facing`) → outcome → `pr_ready`,
  with `pr_ready` also requiring a clean product worktree/index,
  repo-kind-aware evidence exclusions, and the outcome stamp bound to the
  same commit. Opening a Lite/quickfix/degraded write window while a stage
  is active refuses.

## Acceptance criteria

- Decomposition recorder refuses execution detail on tasks after the earliest
  pending leaf and accepts it on the frontier task.
- `stage start` and `delegate` both refuse an incomplete contract or a
  missing/stale grill; delegate refuses an active stage with empty
  `write_scope`; `--read-only` still passes.
- `forge next` reports author-contract / grill / stage-start / delegate as
  the single next action per task state; the board shows matching task rows.
- Task-contract, plan, and product-tree changes each stale a grill; commits
  touching only `.factory/` and `plans/` do not.
- A grill missing any required proof, with an unmapped criterion, an absent
  `new_abstractions` field, or `pass`+split/block is refused; a `block`
  without an escalation packet is refused; every declared gap needs either a
  matching structured round or a named-source citation, while a zero-gap
  grill may validly record zero rounds and sanctioned resolutions.
- The frontier task's `criteria_map` lands as `plan_contracts`; quality
  review refuses without per-contract verdicts (existing FORGE-REV-2
  enforcement).
- Default, lowered, justified-higher, and exceeded review budgets behave as
  specified at `stage done`; workflow-evidence paths are excluded from the
  count.
- Lite, quickfix, and degraded windows are unchanged, except that opening a
  write window while a stage is active refuses (FORGE-ACC-3).
- Approved-plan digest, frozen skeleton, immutable completed contracts,
  recorded local review, commit-before-done, coherent one-run branch review,
  and closeout ordering behave as specified (FORGE-ACC-3).

## Non-goals

- No per-commit review; review cadence stays decision 0011.
- No stored `contract_status` field; readiness is derived.
- No separate `forge stage budget` command; budget reporting rides `stage
  done` refusals and the board.
- No changes to Lite/quickfix/degraded window profiles.
