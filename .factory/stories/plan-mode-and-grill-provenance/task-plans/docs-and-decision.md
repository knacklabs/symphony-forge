# Task plan — docs-and-decision (story plan-mode-and-grill-provenance)

## Objective
Make the record corpus state the enforced rule once: accept decision 0048,
amend the two spec clauses that now contradict shipped behaviour, and state
the new task order in WORKFLOW.md.

## State left by prior work
Tasks 1–3 shipped and closed: the PostToolUse ledgers, the plan-mode marker
gate (`plan_body_digest`, story-then-root), and the round-provenance gate
(ledger match, floors 2/1/2/1, `frontier_empty`, task plan before task
grill, frontier + `forge next` flipped). Decision 0048 is drafted
(committed, `status: proposed`). Contradicting clauses:
`docs/specs/accountable-engineering-loop.md:93` and its restatement at
`:139` ("a zero-gap grill may validly record zero rounds");
`docs/specs/plan-approval.md:20-22` ("plan mode cannot be the enforcement
signal"). `WORKFLOW.md` §Task Planning (line ~431) still describes the old
order.

## Steps (orchestrator directly — docs and decisions are the coordinator's;
the only write scopes are docs/ and WORKFLOW.md, no product code)
1. **Decision 0048** — update the draft with the as-built facts: marker
   digest is `plan_body_digest` (frontmatter + assumptions excluded),
   story-then-root scope; `tool_response` IS delivered (live-proven), so no
   fallback clause; floors and `frontier_empty`; the restamp and root-scope
   findings; then present for human acceptance and record
   `decision accept --by`.
2. **accountable-engineering-loop.md** — replace both zero-rounds sentences
   with: every spec/requirements/plan/task grill delivers ledger-matched
   AskUserQuestion rounds meeting GATE_ROUND_FLOORS with `frontier_empty`
   attested on the final round (0048); re-save + spec grill (2 rounds via
   AskUserQuestion under the NEW enforcement) + confirm.
3. **plan-approval.md** — rewrite the "cannot be the enforcement signal"
   sentence: ExitPlanMode still fires no hook, but `permission_mode:
   "plan"` on Write/Edit is the authorship proof (0048); the human approval
   command stands unchanged; re-save + spec grill + confirm.
4. **WORKFLOW.md** — Task Planning paragraph states: author the task plan
   in plan mode (hook records it) → task grill via AskUserQuestion until
   frontier_empty → human task approve → stage start → delegate.
5. **Proof test** — `test_docs_state_enforced_order` in
   `factory/tests/test_gates.py`: asserts the specs contain no
   "zero rounds" grant, plan-approval names permission_mode as the proof,
   and WORKFLOW.md names the order (string-level, like existing doc gates);
   written by Codex via a one-file delegation since tests are product code.
6. `check_dual_runtime.py` green.

## Write scope
`docs/decisions/0048-plan-mode-and-grill-provenance.md`,
`docs/specs/accountable-engineering-loop.md`,
`docs/specs/plan-approval.md`, `WORKFLOW.md`,
`factory/tests/test_gates.py`.

## Proof (required_tests)
`uvx --with pytest --with psutil python3 -m pytest {path}::{id} -q -o
junit_family=legacy --junitxml={report}` on `factory/tests/test_gates.py`
for `test_docs_state_enforced_order`.

## Verify commands
`python3 factory/scripts/check_dual_runtime.py`.

## Reviewer focus
The spec amendments say exactly what the code enforces (no drift between
clause and GATE_ROUND_FLOORS); 0048's supersessions stay clause-level
(0044's zero-rounds sentence, 0029's not-the-signal sentence); both spec
re-confirms are recorded under the new enforcement — their own rounds must
be ledger-matched, floored, and frontier_empty-attested.

## Task grill (1 round, 1 question; frontier empty)
- Delivered via AskUserQuestion in this session and recorded by the hook;
  this grill is itself subject to the task-gate floor (1) and ledger match
  shipped in task 3.

## Risk
The two spec grills are the first recorded under full enforcement — if the
recorder refuses them, that is a finding on task 3, not something to bypass.
