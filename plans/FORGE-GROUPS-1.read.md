---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-25T02:54:18.166162+00:00
seconds: 268.638
read_hash: b8137876bd0b8bf79cb585110537087791a1c3c3
round: 1
passed: no
doc_seen: b8137876bd0b8bf79cb585110537087791a1c3c3
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a170f6-e233-7c53-9998-63c522ea35e5
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

1. Blocking: Retrying a failing pytest group can turn a persistent failure green.
   Raise: Functional. Case: normal use - two related files split between two groups, and group 2’s test fails. `src/forge/review.py:498` retries failed files; `src/forge/fasttest.py:437` replaces collection arguments with those files. Pytest-split then assigns the reduced collection again: its installed `LeastDurationAlgorithm` assigns a single remaining test to group 1, leaving group 2 empty. The proposed exit-status-5 conversion (`plans/FORGE-GROUPS-1.md:103`) reports success without rerunning the failure. The planned pytest tests exercise passing and empty groups, so they miss this false green.
   Gain 5, Work 3, Harm 3
   Disposition: cut item 3 now makes close's one retry run the failed files unsplit (the results hook clears pytest-split's options on a retry), with test case (e)

2. Blocking: Empty groups still fail when pytest runs directly through `fast_test`.
   Raise: Not done. Case: normal use - a pytest-split client sets multiple groups and uses a direct pytest `fast_test`. `src/forge/review.py:390` bypasses the picker when `fast_test` exists and returns that command at `:396`. The proposed `repo.grouped` adds splitting there, but empty-group success handling exists only inside `fasttest.pytest_tests` (`plans/FORGE-GROUPS-1.md:102`). An empty direct run therefore returns 5 through `review.test_run`, failing the required check. All proposed execution cases use `test`, leaving this supported path untested.
   Gain 4, Work 2, Harm 3
   Disposition: cut the empty-group pass moved to one place in `review.test_run` (shared names), which every grouped command reaches, with a direct pytest `fast_test` case (d) in item 3's test

3. Blocking: The nightly full-run path leaves shard placeholders unresolved.
   Raise: Plan gap. Case: normal use - a client follows the documented `test = "vitest run --shard={group}/{groups}"` configuration and runs its nightly full suite. `plans/FORGE-GROUPS-1.md:81` names only three substitution sites. The companion FULLRUN plan (`story/FORGE-TESTPLACE-1:plans/FORGE-TESTPLACE-1.md:147`) instead sends raw `test` directly to `review.test_run`. That execution path performs no placeholder substitution (`src/forge/review.py:475`, `src/forge/fasttest.py:491`). The runner receives literal braces, contradicting the promised nightly group 1 of 1; neither task owns this integration.
   Gain 4, Work 2, Harm 3
   Disposition: cut item 2 names `review.test_run` as the direct-command substitution site, which covers FULLRUN's raw `test` call (group 1 of 1, no matrix), with a direct `fast_test` case in test_2

4. Advisory: Item 4’s prescribed recorder can bypass the cache being tested.
   Raise: Test. Case: normal use - the cache regression reuses the named Vitest stub. That stub writes `observed.json` inside the checkout (`tests/test_node_test_worker_budget.py:135`), making it dirty. `src/forge/review.py:570` disables cached passes whenever status shows changes. The second group consequently runs even without the proposed cache-key repair. `plans/FORGE-GROUPS-1.md:129` specifies neither a clean checkout after recording nor evidence that cache reuse was active, so its assertions can pass with the defect intact.
   Gain 3, Work 2, Harm 2
   Disposition: cut item 4's test records outside the checkout and first shows a cached skip for group 1, so it fails without the key repair

5. Advisory: The new setting’s refusal rule has no planned command-level proof.
   Raise: Test. Case: normal use - a client writes `groups = 0` or `groups = true`. `plans/FORGE-GROUPS-1.md:46` requires a specific refusal, but every named test supplies a valid positive integer. Current validation handles strings, lists and enumerated choices, with no integer validation branch (`src/forge/repo.py:791`). Adding the key while omitting its validation would pass the proposed tests, violating the repository’s required refusal-message coverage.
   Gain 3, Work 2, Harm 2
   Disposition: cut shared names now name the `kind is int` branch in `repo._config_problem`, and item 2 adds a refusal test for 0, true and a string
