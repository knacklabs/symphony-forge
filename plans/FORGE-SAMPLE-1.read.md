---
reader: codex (gpt-6.1-sol)
read_at: 2026-11-02T18:09:17.889756+00:00
seconds: 332.415
read_hash: 64ca8423863c79d14ad9a54b05d281ab77f8c242
round: 1
passed: no
doc_seen: 64ca8423863c79d14ad9a54b05d281ab77f8c242
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a19d6e-7be6-7b40-930c-d15d57641a07
session:
loop_choice:
loop_reason:
---
# Cold read notes

Written by `forge read`. Under every blocking finding, write one disposition line, amend the
doc, then run `forge read <doc>` again until a round has no blocking notes. Notes marked
`Advisory:` are recorded without requiring a disposition or another round:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

A finding inside What counts is cut or deferred. Keep one only when it falls outside that boundary
or is factually wrong or not worth the change, and give as the reason the Leave out line, the
missing Raise line, the cited fact that disproves it, why it is not worth the change, or the
human's `Decided:` line.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. Blocking: Not done: item 2 leaves workers instructed to write and run tests.
   Raise: Not done.
   Case: normal use - a worker builds an ordinary sample-data prototype fix.
   [brief.md:633](/src/forge/templates/brief.md:633) requires demo tests and a green full run. [worker.py:579](/src/forge/worker.py:579) includes that block without checking sample-data status; line 56 explicitly tells workers not to read the coordinator guide. Neither file is in this plan's Scope, so changing the guide and emptying the test command leaves the worker's instructions contradicting the promised no-tests start.
   Gain 4, Work 2, Harm 3
   Disposition: cut - SETUP's Scope now has `src/forge/worker.py` and `templates/brief.md`; a sample-proof block replaces the test requirements for a sample-data prototype, and SETUP's `test_2` checks the recorded worker prompt.

2. Blocking: Plan gap: the small gap check requires a review-engine change outside SIGNOFF's Scope.
   Raise: Plan gap.
   Case: normal use - the first gap check runs on a sample-data prototype.
   Settled 4 requires narrowing the snapshot if the engine receives the whole product. [review.py:854](/src/forge/review.py:854) always takes the sign-off snapshot path: its first call compares the product against an empty root, retaining all product files except the stated exclusions. Changing the prompt does not narrow that snapshot. SIGNOFF excludes `review.py`, and its planned test checks prompt text without checking which files reach the reviewer.
   Gain 4, Work 2, Harm 3
   Disposition: cut - SIGNOFF's Scope now has `src/forge/review.py` (an `only` argument that removes every file except the brief, the design pages and the route files from the snapshot), and `test_1` checks which files reach the reviewer.

3. Blocking: Plan gap: SETUP and DESIGN cannot pass their assigned tests before SIGNOFF.
   Raise: Plan gap.
   Case: normal use - builders complete the tasks in the table's required order.
   [The test details:104](/plans/FORGE-SAMPLE-1.md:104) require SETUP's test to accept sign-off with Personal data open; DESIGN's test at line 106 requires the new gap-check prompt. Those behaviours belong to SIGNOFF, which waits for both tasks. Currently [records.py:326](/src/forge/records.py:326) refuses open topics, and line 541 constructs the existing whole-source prompt. The command-level integration assertions need an owner after SIGNOFF; helper stubs cannot satisfy them under the stated external-only mocking rule.
   Gain 4, Work 2, Harm 2
   Disposition: cut - the sign-off accepts-with-Personal-data-open case moved to SIGNOFF's `test_4`, the gap-check design cases moved to SIGNOFF's new `test_8`, and SETUP and RECORD tests write the accepted sign-off as a file, so every part passes its own tests in order.

4. Blocking: Unproven: item 1 does not cover a non-P0 gap with Gain 5.
   Raise: Test.
   Case: normal use - the gap check reports a missing main demo route as P1 with Gain 5.
   The plan says `_signoff_known` already sends every non-P0 finding to Known issues. [records.py:460](/src/forge/records.py:460) explicitly excludes findings that `score.holds(..., "P0")`; [score.py:130](/src/forge/score.py:130) holds scored findings by their scores, including Gain 5, regardless of P1 priority. Reusing that helper leaves this finding unsettled. The planned lesser-finding case names P1 and Harm 3 but does not pin this existing score-based exception.
   Gain 3, Work 2, Harm 3
   Disposition: cut - Done-when 1, Settled 5 and the details now say a P1 with Gain 5 or Harm 4 or more is held like a P0 (the `score.holds` test that `_signoff_known` uses) and comes to the owner at once; `test_1` has the Gain 5, Harm 1 case and a Gain 4, Harm 3 case.

5. Blocking: Plan gap: the required upstream build order and test repair have no task ownership.
   Raise: Plan gap.
   Case: normal use - Forge starts SETUP or DESIGN while the upstream approval change is unfinished.
   [Notes:158](/plans/FORGE-SAMPLE-1.md:158) require SETUP, DESIGN and SIGNOFF to follow `FORGE-ONEPLAN-1/GATES`, and require this second story to repair `tests/test_one_plan.py::test_1`. The task table contains neither that external dependency nor that test in any Scope. [task.py:418](/src/forge/task.py:418) schedules dependencies from the After cell, so the prose does not establish the required order. The dependency and the named test repair need explicit task ownership.
   Gain 4, Work 1, Harm 2
   Disposition: cut - SETUP, DESIGN and SIGNOFF list `FORGE-ONEPLAN-1/GATES` in After, `tests/test_one_plan.py` is in SETUP's and DESIGN's Scope, and the Notes now say the owner dropped the screenshot-file refusal and kept the client's tick.
