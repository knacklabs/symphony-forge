---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-18T08:37:37.845341+00:00
seconds: 47.415
read_hash: 66cefdc3ec8b9a203ddf3de95c947ab65e9f90aa
round: 2
passed: yes
doc_seen: 66cefdc3ec8b9a203ddf3de95c947ab65e9f90aa
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: a8bae358cb43d4c74ff43e26a20881bc111618a7
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a14e24-b825-7e62-8345-b073a509ec24
session:
blocked_rounds: 0
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
or is factually wrong, and give as the reason the Leave out line, the missing Raise line, the
cited fact that disproves it, or the human's `Decided:` line.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. Blocking: Trap: the proposed root cache does not distinguish linked worktrees.
   Raise: Plan gap. The plan routes root lookups through `command_fact`, whose key uses the shared Git directory ([repo.py:118](/src/forge/repo.py:118)). During close, `_answer_by_default` changes into the item's worktree before starting follow-up fixes ([close.py:519](/src/forge/close.py:519)). Reusing the caller's cached root makes `fix_start` inspect the wrong branch and lose the intended stacking relationship. The plan needs a checkout-specific root key.
   Gain 3, Work 2, Harm 3
   Disposition: cut

2. Blocking: Remembering ref lookups for the whole command lacks a mutation rule.
   Raise: Plan gap. Close can fingerprint an earlier-release review before fetching and merging main, then fingerprint `HEAD` again afterward ([close.py:167](/src/forge/close.py:167), [close.py:233](/src/forge/close.py:233)). Those fingerprints read `merge-base`, `diff` and `ls-tree`, exactly the operations being cached. Existing invalidation clears only commit-history entries ([repo.py:179](/src/forge/repo.py:179)). Without immutable-ref keys or invalidation, the second fingerprint can describe the pre-merge tree and change review-freshness decisions.
   Gain 3, Work 2, Harm 3
   Disposition: cut

3. Blocking: Skipping the generated-file check based on this commit breaks subsequent commits in an upgrade fix.
   Raise: Functional. The plan permits skipping when no generated file or template is in the commit. However, `_promote` counts the entire fix from its base to the index ([githooks.py:194](/src/forge/githooks.py:194)). After committing generated updates, a second commit changing only ordinary source still includes those generated files in the cumulative count. Skipping their exemption falsely refuses that commit. The existing upgrade test establishes that generated output can exceed five files ([test_fix_sync_output_skips_fix_limit.py:50](/tests/test_fix_sync_output_skips_fix_limit.py:50)).
   Gain 3, Work 2, Harm 3
   Disposition: cut

4. Advisory: Trap: timing the whole commit does not isolate the generated-check budget.
   Raise: Test. Done-when 2 limits the generated check's added time, but the builder instructions test whether the commit stays under that limit ([FORGE-GITCOST-1.md:56](/plans/FORGE-GITCOST-1.md:56)). The hook performs several Git operations before that check ([githooks.py:194](/src/forge/githooks.py:194)). A correct optimization can therefore fail the proposed test because of unrelated startup costs or machine load.
   Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)

## Round 2

No findings.
