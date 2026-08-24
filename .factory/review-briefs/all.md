# Branch-wide plan-contract review brief

For each contract, emit a verdict — implemented | partial | missing — with file:line evidence, recorded as contract_verdicts in the quality artifact. Then review the diff normally; the contract check does not replace the quality/performance/security lenses.

## Task post-tool-use-ledgers

### Plan contracts

- **ptl-1**
  - Source: plans/active/plan-mode-and-grill-provenance-plan-mode-and-grill-provenance-are-enforced-not-advisory.md#task-decomposition
  - Statement: forge hook post_tool_use records <scope>/plan-mode/<uuid>.json with path (absolute, may be outside the repo such as ~/.claude/plans/x.md), sha256 (raw bytes), sha256_body (plan_digest_without_assumptions), at, session_id ('' when absent), generated_by 'claude-code:plan-mode' for Write/Edit/MultiEdit made with permission_mode plan, and nothing for other modes; root-level dirs are used when no story is active
- **ptl-2**
  - Source: plans/active/plan-mode-and-grill-provenance-plan-mode-and-grill-provenance-are-enforced-not-advisory.md#task-decomposition
  - Statement: the same hook records <scope>/grill-rounds/<uuid>.json with questions (question, options, chosen — chosen null when tool_response is absent or not among the options), at, session_id ('' when absent), generated_by 'claude-code:plan-mode' for every AskUserQuestion whose tool_input.questions is usable; unparseable input exits 0 without writing
- **ptl-3**
  - Source: plans/active/plan-mode-and-grill-provenance-plan-mode-and-grill-provenance-are-enforced-not-advisory.md#task-decomposition
  - Statement: both record kinds validate against new schemas; .claude/settings.json wires PostToolUse for Write|Edit|MultiEdit|AskUserQuestion; gate tests cover both record kinds and the fail-open path

### Reviewer focus

Fail-open is real (every error path exits 0 and writes nothing); no AskUserQuestion free text (notes) is persisted; marker digests use the same body exclusion as plan_digest_without_assumptions; records land under the story scope via evidence_path, never a hand-built path; settings.json PostToolUse command exits 0, PreToolUse entries untouched.

## Task plan-mode-gate

### Plan contracts

- **pmg-1**
  - Source: plans/active/plan-mode-and-grill-provenance-plan-mode-and-grill-provenance-are-enforced-not-advisory.md#task-decomposition
  - Statement: require_plan_mode_marker matches the digest of the plan BODY excluding both the harness-stamped frontmatter block and the Implementation Assumptions block (plan save re-stamps status/saved, which must not invalidate the marker), searching the active story scope then the root scope; plan save, plan approve, task plan save and task approve all call it
- **pmg-2**
  - Source: plans/active/plan-mode-and-grill-provenance-plan-mode-and-grill-provenance-are-enforced-not-advisory.md#task-decomposition
  - Statement: gate tests prove refusal without a marker and success with one for both story and task plans

### Reviewer focus

One shared plan_body_digest helper used by both the hook and the gate (no second implementation); markers read through evidence_path story-then-root, never a hand-built path; fixtures create markers only via the real hook (no env bypass, no hand-written markers); the restamp test proves approve works after save without a fresh plan-mode round; quickfix/degraded untouched.

## Task round-provenance-gate

### Plan contracts

- **rpg-1**
  - Source: plans/active/plan-mode-and-grill-provenance-plan-mode-and-grill-provenance-are-enforced-not-advisory.md#task-decomposition
  - Statement: record_grill_from_json refuses, for spec/requirements/plan/task gates, rounds that do not match a logged record, counts below spec 2 / requirements 1 / plan 2 / task 1, and a final round without frontier_empty true; byte-identical re-records may reuse rounds
- **rpg-2**
  - Source: plans/active/plan-mode-and-grill-provenance-plan-mode-and-grill-provenance-are-enforced-not-advisory.md#task-decomposition
  - Statement: a task grill is refused when task-plans/<id>.md is absent, with a one-time tolerance for grills older than a later-saved task plan; task_frontier_state and tasks.cmd_plan_save implement author-task-plan before grill; forge next prints the enforced planning and implementing order
- **rpg-3**
  - Source: plans/active/plan-mode-and-grill-provenance-plan-mode-and-grill-provenance-are-enforced-not-advisory.md#task-decomposition
  - Statement: existing inverse-order gate tests are flipped, new refusal and happy-path tests pass

### Reviewer focus

Rounds matched against ledger records read via evidence_path story-then-root, never hand-built paths; GATE_ROUND_FLOORS a named constant (spec 2, requirements 1, plan 2, task 1); frontier_empty required on the final round only; chosen equality exact when the ledger entry has non-null chosen; the task-plan tolerance keyed on timestamps and tested; every fixture logs rounds through the real hook; epics/signoff gates explicitly unchanged; no weakening of digest freshness.

## Task docs-and-decision

### Plan contracts

- **dad-1**
  - Source: plans/active/plan-mode-and-grill-provenance-plan-mode-and-grill-provenance-are-enforced-not-advisory.md#task-decomposition
  - Statement: decision 0048 accepted by a human; accountable-engineering-loop.md zero-rounds sentence and plan-approval.md not-the-signal sentence replaced; both specs re-confirmed with recorded grills
- **dad-2**
  - Source: plans/active/plan-mode-and-grill-provenance-plan-mode-and-grill-provenance-are-enforced-not-advisory.md#task-decomposition
  - Statement: WORKFLOW.md task-loop paragraph states the new order; check_dual_runtime and check_vendor_integrity green

### Reviewer focus

Spec clauses match the shipped enforcement exactly (floors, frontier_empty, ledger match, plan_body_digest); 0048 supersedes clause-level only; both spec re-confirm grills recorded under the new enforcement; the doc test is string-level like existing doc gates.

## Task flip-frontier-routing-test

### Plan contracts

- **fft-1**
  - Source: plans/active/plan-mode-and-grill-provenance-plan-mode-and-grill-provenance-are-enforced-not-advisory.md#task-decomposition
  - Statement: test_forge_next_routes_the_jit_frontier_states asserts the enforced order (author-task-plan first, then task plan save + approve in the fixture, then the grill action); no assertion deleted; no production code changed
- **fft-2**
  - Source: plans/active/plan-mode-and-grill-provenance-plan-mode-and-grill-provenance-are-enforced-not-advisory.md#task-decomposition
  - Statement: full gate suite green: the one failing test passes and no other test regresses

### Reviewer focus

The test asserts the new order end to end rather than deleting assertions; the fixture uses the real task plan save / task approve commands and the real hook for the marker.
