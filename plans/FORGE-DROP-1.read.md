---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-17T17:38:17.371722+00:00
seconds: 389.012
read_hash: 06c8300fbdbdff393a221c49f48f6b23aec27906
round: 1
passed: no
doc_seen: 06c8300fbdbdff393a221c49f48f6b23aec27906
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a14aeb-7a84-7a60-b4e4-9527fe202eea
session:
blocked_rounds: 1
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

1. Blocking: Removing the worktree can permanently delete ignored local data.
   Raise: Data loss. [The plan](/plans/FORGE-DROP-1.md:52) adopts merge cleanup while claiming no irreversible risk. [Merge cleanup](/src/forge/merge.py:162) excludes ignored files from its dirty check. [Git’s removal implementation](https://github.com/git/git/blob/v2.47.1/builtin/worktree.c#L1180-L1268) then deletes the directory, including ignored files. A local database under ignored `data/` is absent from the pushed branch and cannot be restored. The plan specifies neither protection nor a test for it.
   Gain 5, Work 3, Harm 4
   Disposition: cut

2. Blocking: Restoring a ready fix cannot preserve its previous next step.
   Raise: Plan gap. [The undo contract](/plans/FORGE-DROP-1.md:61) adds another commit but promises the same next step. For a ready fix, that step is merge. [Readiness requires evidence matching the current commit](/src/forge/nextstep.py:759), and [merge refuses a changed pull-request head](/src/forge/merge.py:67). The plan must resolve this contradiction; its round-trip test does not require a previously ready fix.
   Gain 3, Work 1, Harm 3
   Disposition: cut

3. Blocking: Dropping a base fix leaves its stacked fixes with an impossible next step.
   Raise: Plan gap. [Fix creation automatically records an unfinished parent](/src/forge/task.py:520). If that parent is dropped, [the merge queue still requires it to merge and directs the agent to land it](/src/forge/land.py:347), although its worktree is gone and its pull request is closed. [The drop rules](/plans/FORGE-DROP-1.md:54) define neither a refusal nor dependent-fix behavior, and no planned test covers this ordinary stacking case.
   Gain 3, Work 2, Harm 3
   Disposition: cut

4. Advisory: A failed GitHub operation leaves drop and undo without a defined retry contract.
   Raise: Plan gap. [The command changes git state, pull-request state and local checkouts separately](/plans/FORGE-DROP-1.md:48). A normal GitHub authorization or network failure can leave a recorded drop with an open pull request. Neither repeated-command behavior nor precedence between those conflicting states is specified at [the shared-state rule](/plans/FORGE-DROP-1.md:65). Existing [git execution](/src/forge/repo.py:247) provides no transaction across these operations. The planned successful round trips would pass without proving recovery.
   Gain 3, Work 3, Harm 3
   Disposition: keep - below the bar (follow-up)

5. Advisory: Unproven: item 3: a teammate who already has the fix checked out.
   Raise: Test. [The second-clone test](/plans/FORGE-DROP-1.md:65) does not require an existing fix worktree. Fetch updates remote references without updating that worktree. [The queue reads its local state directly](/src/forge/land.py:294), while [the board initially prefers local copies](/src/forge/board.py:905). A fresh-clone test can pass while an existing teammate checkout still displays or queues the dropped fix.
   Gain 3, Work 3, Harm 3

Implementation skipped; the data-loss risk above remains unresolved.
   Disposition: keep - below the bar (follow-up)
