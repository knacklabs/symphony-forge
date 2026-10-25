---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-25T03:00:40.996409+00:00
seconds: 115.584
read_hash: 89af9a90ea3a7fe6e4c74dd42f92378b7a7c641b
round: 2
passed: no
doc_seen: 89af9a90ea3a7fe6e4c74dd42f92378b7a7c641b
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e6c8ab106bbeba0d7ed3c0e7ddefe8202c0b60ff
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a170f6-e233-7c53-9998-63c522ea35e5
session:
loop_choice: more
loop_reason: The owner chose to fix the pytest-only empty-group rule and the test name clash, then read once more
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

## Round 2

6. Blocking: The new empty-group rule turns real failures from other runners into passes.
   Raise: Functional. Case: normal use - a client sets `groups = 2` with `test = "mocha"`, and five tests fail. [Mocha’s exit handler](https://github.com/mochajs/mocha/blob/v11.7.5/lib/cli/run-helpers.js#L281) returns the failure count, so this run exits 5. Forge preserves that status for other runners (`src/forge/fasttest.py:272`), but the new unconditional conversion at `plans/FORGE-GROUPS-1.md:61` changes it to success. Both groups can therefore pass a failing suite, and `review.test_run` caches that false pass at `src/forge/review.py:526`. The new tests cover only pytest’s meaning of status 5.
   Gain 5, Work 3, Harm 3

7. Advisory: The added validation test duplicates criterion 1 and fails the repository’s test gate.
   Raise: Gate. Case: normal use - ANYRUNNER implements the two prescribed tests. `plans/FORGE-GROUPS-1.md:80` names `test_1_groups_split_the_test_job`, while `:108` adds `test_1_groups_refuses_a_bad_value` in the same module. `tests/test_rules.py:49` keys tests by story and criterion number and rejects duplicates at `:50`. Following these names makes the suite fail.
   Gain 3, Work 1, Harm 1
   Disposition: keep - below the bar (follow-up)
