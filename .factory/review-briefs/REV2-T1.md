# Plan-contract review brief — REV2-T1

For each contract, emit a verdict — implemented | partial | missing — with file:line evidence, recorded as contract_verdicts in the quality artifact. Then review the diff normally; the contract check does not replace the quality/performance/security lenses.

## Task REV2-T1

### Plan contracts

- **REV2-C1**
  - Source: plans/active/FORGE-REV-2-review-verifies-plan-contracts.md#technical-approach
  - Statement: A decomposition task may declare plan_contracts entries {id, statement, source}; the recorder validates shape and cross-decomposition id uniqueness like required_tests, refusing malformed entries with the task and position named.
- **REV2-C2**
  - Source: plans/active/FORGE-REV-2-review-verifies-plan-contracts.md#technical-approach
  - Statement: ./forge review-brief <task-id> writes .factory/review-briefs/<task-id>.md with the task's contracts, reviewer_focus, and the implemented|partial|missing verdict instruction; --all writes the branch-wide union brief; the command works on Windows.
- **REV2-C3**
  - Source: plans/active/FORGE-REV-2-review-verifies-plan-contracts.md#technical-approach
  - Statement: record_review_from_json.py refuses a quality artifact that does not verdict every declared contract (unknown ids, bad verdicts, empty evidence also refuse); each partial/missing verdict is appended to blocking_findings as a structured finding.
- **REV2-C4**
  - Source: plans/active/FORGE-REV-2-review-verifies-plan-contracts.md#technical-approach
  - Statement: pr_ready.py refuses while any declared contract lacks an implemented verdict in the recorded quality review, independent of the recorder's own enforcement.
- **REV2-C5**
  - Source: plans/active/FORGE-REV-2-review-verifies-plan-contracts.md#technical-approach
  - Statement: reviewer.md instructs per-task --prompt-file usage and contract_verdicts in the quality artifact; pr-ready.md instructs the closeout branch-wide autoreview to use ./forge review-brief --all as its prompt file.
- **REV2-C6**
  - Source: plans/active/FORGE-REV-2-review-verifies-plan-contracts.md#scope--non-goals
  - Statement: A decomposition without plan_contracts records, reviews, and gates exactly as before; the pre-existing test suite passes unmodified.

### Reviewer focus

Refusal messages must name the task/entry; the verdict union must cover EVERY task's contracts, not the last task's; review_brief.py must import no delegate machinery (Windows); pr_ready's backstop must not trust the recorder; no-contract decompositions must be behaviorally byte-identical.
