---
reader: codex (gpt-6.1-sol)
read_at: 2026-11-06T11:45:51.236034+00:00
seconds: 93.971
read_hash: 55dd5d9e5964df6172eb8b7f5b136dfd458189d0
round: 2
passed: yes
doc_seen: 55dd5d9e5964df6172eb8b7f5b136dfd458189d0
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 915e867a0c906bbc5744f1121460ab5be8eba460
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1b09f-3dfd-7aa1-84e5-10f23df882f5
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

1. Blocking: The new reuse path can skip reviewing an amended fix contract.
   Raise: Functional. `plans/FORGE-SPLITREVIEW-1.md:65-66` excludes records from the comparison and checks contract equality only for tasks. `src/forge/task.py:735-743` changes a fix’s Done-when inside `.factory` while retaining its review. After a clean review, an amendment and a clean merge can therefore produce an empty comparison, causing close to mark the new contract reviewed without checking it. Today, `src/forge/review.py:163-164` includes that contract in the fingerprint; `tests/test_close_refreshes_pull_request_contract.py:17-39` requires another review after amendment.
   Case: normal use - the owner clarifies a reviewed fix’s Done-when while main moves.
   Gain 4, Work 2, Harm 3
   Disposition: cut - Done-when details item 1 now requires every non-file part of the fingerprint to match at the last clean review and at the head (fix why and done_when, task story doc and roadmap entry, the three commit paragraphs, no skipped field); any difference keeps today's full review; test case (g) amends a fix after a clean review and expects a second review.

2. Blocking: Not done: item 1 leaves test selection unchanged despite promising all tests in full.
   Raise: Not done. `plans/FORGE-SPLITREVIEW-1.md:52,66` assumes existing close paths already provide full testing. `src/forge/review.py:366-375` instead chooses `fast_test` or a selection helper; `src/forge/fasttest.py:295-303` limits Jest and Vitest to changed tests. Keeping those paths does not deliver the promised full run or the stated guard for interactions with main.
   Case: normal use - a supported client repo closes a conflict fix using its configured fast tests.
   Gain 4, Work 2, Harm 3
   Disposition: cut - the plan now says what 'tests in full' means: the test run close does for any change, on the merged head on every path. The visible text (What changes, Done-when 1, Risks) was reworded to match, and the whole-suite alternative is open choice 6 for the owner. Test cases (a) and (b) count test runs through a marker file.

3. Blocking: Unproven: item 1’s proposed assertions cannot establish that only conflict lines reach the reviewer.
   Raise: Test. `plans/FORGE-SPLITREVIEW-1.md:67` records only changed filenames. A faulty snapshot base could include earlier reviewed edits and unrelated main edits within the conflicted file while passing every filename assertion and the prompt check. The base selection being replaced lives at `src/forge/review.py:930-934`; the test needs to check the actual supplied diff, including exclusion of previously reviewed lines in that same file.
   Case: normal use - one file contains both the conflict fix and earlier reviewed changes.
   Gain 3, Work 2, Harm 3
   Disposition: cut - the stub now logs the full patch between its base and HEAD, not file names; case (b) has one file with an earlier reviewed change on line 1, main's clean change on line 25 and the conflict fix on line 10, and asserts exactly one hunk, line 10; case (c) repeats it with two merges.

## Round 2

No findings.
