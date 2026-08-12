---
slug: plan-contract-review
title: Review verifies plan contracts, not just the diff
status: confirmed
saved: 2026-08-12T12:15:02+00:00
---

# Review verifies plan contracts, not just the diff

> Captured 2026-08-12 from operator direction: review is plan-blind, so
> incomplete implementation is invisible to it. The reviewer can only judge
> code that exists; missing code looks like nothing.

## Why

The implementer side already binds the plan to the work: `compose_brief`
inlines the task contract into the delegation brief. Review has no such
input. `reviewer_focus` is one free-text string, findings are
`{category, area, summary}`, and `pr_ready.py` checks that review artifacts
exist — not that every plan invariant was verified implemented. A diligent
reviewer's completeness check has nowhere recordable to land, so it
evaporates instead of becoming a gateable artifact.

## Behaviour

- A decomposition task MAY declare `plan_contracts`: the invariants from the
  plan it must satisfy, each `{id, statement, source}` (source = plan
  file+section). The recorder validates them like `required_tests`; ids are
  unique across the decomposition.
- `./forge review-brief <task-id>` composes
  `.factory/review-briefs/<task-id>.md` from the task's `plan_contracts` and
  `reviewer_focus`, instructing the reviewer: for each contract, emit a
  verdict — implemented | partial | missing — with file:line evidence, then
  review the diff normally (the contract check does not replace the
  quality/perf/security lenses). Repo-relative path on purpose —
  autoreview's `--prompt-file` requires it. `--all` composes the branch-wide
  brief (every task's contracts) for the closeout review, which catches a
  later stage undoing an earlier stage's contract.
- The quality review artifact carries `contract_verdicts`:
  `[{contract_id, verdict, evidence}]`. The recorder refuses a quality
  artifact that omits verdicts when the recorded decomposition declares
  `plan_contracts`; any partial/missing verdict is recorded as a blocking
  finding.
- `pr_ready.py` refuses while any declared contract lacks an
  all-implemented quality verdict.
- Tasks without `plan_contracts` behave exactly as today: no new artifact
  type, no new recorder, quickfixes stay ceremony-free.

## Acceptance criteria

- `record_decomposition_from_json.py` refuses a malformed `plan_contracts`
  entry (non-object, missing/empty id/statement/source, duplicate id) and
  accepts a well-formed one.
- `./forge review-brief <task-id>` writes
  `.factory/review-briefs/<task-id>.md` containing every declared contract
  and the verdict instruction; `--all` writes the branch-wide brief.
- `record_review_from_json.py --aspect quality` refuses an artifact without
  a verdict for every declared contract; a partial/missing verdict lands as
  a blocking finding in the recorded artifact.
- `pr_ready.py` refuses while any declared contract lacks an
  all-implemented quality verdict, and passes once all are implemented.
- A decomposition without `plan_contracts` records, reviews, and gates
  exactly as before (regression: existing suite stays green).

## Non-goals

- No separate completeness artifact or recorder — verdicts ride the
  existing quality review.
- No structured replacement for `reviewer_focus`; it stays free text
  alongside the contracts.
