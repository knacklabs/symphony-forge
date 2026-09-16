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
  `stage done` measures the completed diff and reports an over-budget result
  with the whole change visible. A result above twice the declared line budget
  refuses closure and instructs the operator to split the task. A measured
  scope or budget amendment does not require another cold read when task
  meaning is unchanged; a material change to the task contract or intent still
  follows the current reapproval and regrill gates.
- **Contracts feed review (FORGE-REV-2).** Recording the frontier task's JIT
  contract lands its grilled `criteria_map` as that task's `plan_contracts`,
  so the quality review must verdict each criterion implemented and
  `pr_ready` gates on it. No new review artifact; no per-commit review —
  cadence stays decision 0011.
- **Board task visibility.** The board renders the in-flight story's task
  rows — state (skeleton|ready|grilled|active|done), grill freshness, budget
  usage — from the same derivation `forge next` uses.
- **One independent cold read.** Each grill gate/pass uses one independently
  ledgered cold result. Every authenticated finding maps one-to-one to a
  disposition, and every cold-input-to-final-artifact change has an exact
  finding-bound amendment bridge. Unexplained changes refuse. Repeated cold
  rereads, round floors, and fake frontier questions are not authority.
- **Native revision-bound approval.** Claude and Codex both approve the exact
  final story or task artifact through the shared recorder and the supported
  host completion event. The record binds the current digest, plan kind,
  story/task, runtime, and stable session/event identity; stale, replayed, or
  ambiguous events refuse. Manual `plan approve` and `task approve` commands
  are not part of normal runtime.
- **Task proof and closeout integrity.** Task proof is the task-scoped
  `verify.json`, `tests.json`, and selected immutable review generation. The
  orchestrator runs one three-lens task review pass, delegates fixes, and
  re-reviews until clean; task-local pre-commit review and branch-wide fixed
  lens files are not authority. Close and seal bind the task marker and
  PR-ready proof to the reviewed delta. Standing human authorization carries
  through bounded corrections; material task-contract or intent changes
  still take the current reapproval and regrill path.
  Before task-wide proof and formal review, the orchestrator checks the
  implementer's handoff checklist: every assigned requirement names its
  concrete code or documentation change and actual focused command/result.
  Any row without actual proof remains incomplete; the final three-lens
  review remains authoritative.
- **Bounded outage exception.** A degraded window may open during an active
  stage only for the documented bounded host/companion outage exception.
  Lite and quickfix retain their separate profiles and do not become a general
  bypass for active-stage authority.

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
  without an escalation packet is refused. One independent cold result binds
  the inspected input; every finding has one disposition, every resulting
  artifact change has a finding-bound amendment bridge, and unexplained
  changes refuse without repeated cold reads or round floors.
- The frontier task's `criteria_map` lands as `plan_contracts`; quality
  review refuses without per-contract verdicts (existing FORGE-REV-2
  enforcement).
- Default, lowered, justified-higher, and exceeded review budgets behave as
  specified at `stage done`; workflow-evidence paths are excluded from the
  count.
- Native approval records the exact final digest through the supported Claude
  or Codex completion event and refuses stale, replayed, ambiguous, or
  identity-free events; manual approval commands are not normal runtime.
- Task-scoped verify, tests, and selected immutable review proof bind close and
  seal to the reviewed delta. One orchestrator-run three-lens pass is fixed and
  re-run after delegated corrections until clean; no task-local or fixed-file
  review authority returns.
- Scope and review-budget amendments preserve the current cold result when
  task meaning is unchanged; material contract or intent changes re-enter the
  current approval and grill gates. Only the documented bounded degraded
  host/companion outage exception may open during an active stage.

## Non-goals

- No per-commit review; review cadence stays decision 0011.
- No stored `contract_status` field; readiness is derived.
- No separate `forge stage budget` command; budget reporting rides `stage
  done` measurement and the board.
- No general mid-stage escape hatch: the degraded exception stays bounded to
  a documented host/companion outage, and Lite/quickfix remain separate.
