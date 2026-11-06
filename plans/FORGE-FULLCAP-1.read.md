---
reader: codex (gpt-6.1-sol)
read_at: 2026-11-06T10:12:11.519132+00:00
seconds: 396.617
read_hash: af21e63d6c4321e837d4c28d2a586cd92d1a09d5
round: 1
passed: no
doc_seen: af21e63d6c4321e837d4c28d2a586cd92d1a09d5
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1b052-22ca-7671-bc27-34bf0069924a
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

1. Blocking: Not done: item 1 leaves clean children built on another machine unmerged.
   Raise: Functional
   Case: normal use - a teammate builds and reviews the stacked child, and the coordinator merges its base.
   `plans/FORGE-FULLCAP-1.md:65` queues the retargeted children, including remote children recognized at `src/forge/merge.py:245-251`. But `src/forge/land.py:302-306` discovers queue entries only from local worktrees. Adding an `only` filter cannot include a child with no local checkout. The planned test creates both checkouts locally and misses this case.
   Gain 4, Work 2, Harm 2
   Disposition: cut - done-when 1 details now read each child's review from git without a checkout, and `land._queue(only=...)` makes a checkout with `close._worktree` for a child built on another machine; the test removes the child's local worktree and branch.

2. Blocking: Not done: item 3's proposed offline path can still call GitHub.
   Raise: Test
   Case: normal use - an unfinished story has a part that merged more than seven days ago, and the older pull-request cache is empty or expired.
   `src/forge/board.py:916-918` marks that part expired. Even with the proposed offline facts, `src/forge/nextstep.py:259-265` calls `board_facts.merged_before_weeks`. That reaches `gh pr list` through `src/forge/board_facts.py:363-367` and `:204-205`. The plan identifies only the login and URL lookups to suppress (`plans/FORGE-FULLCAP-1.md:59,76`); its fresh test fixtures would pass while this network path remains.
   Gain 4, Work 2, Harm 2
   Disposition: cut - the offline form of `startable` is now owned by STOP, skips `github_login`, the `gh pr view` and `merged_before_weeks`, and its test checks a part merged over seven days ago with an empty older-pull-request cache.

3. Blocking: RULE requires a passing test of a command that STOP implements later.
   Raise: Plan gap
   Case: normal use - the builder completes and verifies RULE before starting its dependent tasks.
   `plans/FORGE-FULLCAP-1.md:76` requires RULE's test to compare `forge next` with `forge hook stop`. That command has no route in `src/forge/cli.py:34-36`; STOP owns its route and implementation (`plans/FORGE-FULLCAP-1.md:114`) and waits for RULE. RULE's scope excludes both files, so it cannot deliver that required test in the stated order.
   Gain 4, Work 1, Harm 2
   Disposition: cut - RULE's test crosses `forge next` and `forge task start` only; `startable` gets its first call in CHAIN's test, and STOP's test checks `forge hook stop` against `forge next`.

4. Advisory: Cut or defer: repeated adopted-repo permutations of the same command behavior.
   Raise: Test
   `plans/FORGE-FULLCAP-1.md:45,70,77,85` repeats every behavioral case for both repo histories. The adopted fixture upgrades and syncs before entering the shared command path (`tests/test_close_keeps_reviews_for_unchanged_branch_diffs.py:23-47`). The Review rules require full new-repo coverage and one adopted-repo witness per rule; additional identical adopted cases are deletion candidates. Keep the distinct init and upgrade delivery checks.
   Gain 2, Work 1, Harm 1
   Disposition: cut - each rule now keeps full new-repo cases and one adopted case; only item 4's init and sync delivery checks run on both.
