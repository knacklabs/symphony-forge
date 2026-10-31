---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-31T10:12:02.448557+00:00
seconds: 300.695
read_hash: 8e348a250b72b54fe39d61b8ec02f5bb044f5ec2
round: 1
passed: no
doc_seen: 8e348a250b72b54fe39d61b8ec02f5bb044f5ec2
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1916d-590b-7ef2-a191-d2e0083e6a2f
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

1. Blocking: Trap: an existing local branch prevents pickup: item 1.
   Raise: Functional.
   Case: normal use - the recipient previously inspected the item’s branch, then switched back to the default branch.
   `plans/FORGE-HANDOVER-1.md:46` always uses `worktree add -b`, which fails when the local branch already exists. Neither caller finds a checkout in this case (`src/forge/worker.py:98-101`, `src/forge/close.py:639-643`). The cited precedent explicitly reuses an existing branch (`src/forge/task.py:744-749`); the proposed helper omits that path.
   Gain 3, Work 2, Harm 3
   Disposition: cut - `pick_up` now reuses an existing local branch (`worktree add <folder> <branch>`, then fast-forward to `origin/<branch>`) and refuses on diverged work, like `fix_drop`; the merge test has a case with an earlier local branch.

2. Blocking: Unfinished items still tell the recipient that work runs on someone else’s machine.
   Raise: Functional.
   Case: normal use - an unfinished task or fix is pushed and handed over before it is ready.
   `plans/FORGE-HANDOVER-1.md:50` explicitly preserves this message. `src/forge/nextstep.py:1043-1045` returns it without a next command, before reaching the normal work or close advice. Reassignment does not change that condition. The guide’s instruction to continue through `forge next` therefore stops at the old machine restriction.
   Gain 3, Work 2, Harm 3
   Disposition: cut - an unfinished pushed item with no checkout now says "has no checkout on this machine. Next: forge work <item>" instead of the old machine restriction; the three old assertions of that wording change with it.

3. Blocking: The merge test retains the local ready record it needs to prove unnecessary.
   Raise: Test.
   Case: normal use - a fresh clone merges an item using only the ready record published on GitHub.
   `plans/FORGE-HANDOVER-1.md:37,52` simulates machine B by removing the worktree and branch after a real close. Close writes the ready record under the shared Git directory (`src/forge/close.py:470-481`, `src/forge/repo.py:752-755`); those removals leave it intact. The current merge reads that local record first (`src/forge/merge.py:46-55`). The proposed positive test can therefore pass with the GitHub-record fallback entirely missing. It needs an independent clone or explicit removal of the local ready record.
   Gain 4, Work 2, Harm 3
   Disposition: cut - the test now uses an independent clone as machine B, so no local ready record exists there and the GitHub-record fallback is the only way merge can pass.
