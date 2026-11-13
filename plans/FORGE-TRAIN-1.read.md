---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-12T17:31:52.176530+00:00
seconds: 484.965
read_hash: 677a6c3b262e1376e2d8ddc4b5340c931d907be3
round: 2
passed: no
doc_seen: 677a6c3b262e1376e2d8ddc4b5340c931d907be3
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 3492a898fe5d10c76c718be8f057b66105bed603
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1d0b8-c881-76f3-b5c7-ef3e26602e64
session:
loop_choice: accept
loop_reason: The owner chose: accept, and correct the blocking note and the six small ones in the builder notes
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

1. Blocking: The temporary branch can overwrite and delete a team’s existing work.
   Raise: Data loss  
   Case: normal use - A repo already has a branch named `forge-train`. The plan force-pushes to it before checking ownership, then reuses and closes any open pull request from that branch and deletes it. Existing merge cleanup protects a branch with a lease instead. [Plan](/plans/FORGE-TRAIN-1.md:84), [merge.py](/src/forge/merge.py:286)  
   Adds work: protect branch ownership and cleanup; F 1 x H 3 = 3; 2 x C = 4  
   Gain 2, Work 2, Harm 4
   Disposition: cut

2. Blocking: Not done: a changed pull request head can merge without the combined check covering it.
   Raise: Not done  
   Case: normal use - Someone updates and closes a later train member while the combined check is running. The plan checks the default branch’s tree, but does not compare that member’s current head with the head used to build the train. `forge merge` accepts a newly ready head and passes that current head to GitHub, so it can merge after earlier members without testing that combination. [Plan](/plans/FORGE-TRAIN-1.md:83), [merge.py](/src/forge/merge.py:71)  
   Gain 5, Work 2, Harm 3
   Disposition: cut

3. Blocking: Not done: a failed job is handled before the other jobs finish.
   Raise: Not done  
   Case: normal use - One test group fails while another is still running. The existing wait stops on the first red check; the planned log reader returns `None` for a pending check, so Forge falls back to individual merges without identifying the failed file or retrying an unnamed failure. The generated workflow runs groups in parallel. [checks.py](/src/forge/checks.py:290), [prcheck.py](/src/forge/prcheck.py:81), [plan](/plans/FORGE-TRAIN-1.md:128)  
   Gain 4, Work 2, Harm 3
   Disposition: cut

4. Blocking: Not done: the up-to-date rule is missed when the pull requests start up to date.
   Raise: Not done  
   Case: normal use - Two ready pull requests both contain the current default branch, and GitHub requires them to stay up to date. Their status is `CLEAN`, not `BEHIND`, so the plan starts a train; the first merge makes the second pull request behind and forces its own check. The planned test moves the default branch first and only covers the `BEHIND` answer. [Plan](/plans/FORGE-TRAIN-1.md:81), [existing status test](/tests/test_mainonce_clash.py:62)  
   Gain 4, Work 2, Harm 3
   Disposition: cut

5. Blocking: Not done: train selection can use stale test settings.
   Raise: Not done  
   Case: normal use - A settings change has merged, but the main checkout has not been updated. The queue fetches the default branch, then the plan reads `forge.toml` from the checkout. It can start a train after the repo switched to laptop tests, or miss one after it switched to CI. The repo already has a reader for the fetched default branch’s settings. [Plan](/plans/FORGE-TRAIN-1.md:81), [land.py](/src/forge/land.py:296), [repo.py](/src/forge/repo.py:715)  
   Gain 4, Work 1, Harm 3
   Disposition: cut

6. Blocking: Not done: the local combination can pass while GitHub cannot merge its members.
   Raise: Not done  
   Case: normal use - First parts of two stories each bring a new entry into `plans/roadmap.json`. Forge’s local merge rule can combine those entries, but GitHub does not have that local rule. After the first pull request merges, the second can conflict on GitHub and require its own new check. The planned passing test uses fixes, which do not exercise this story-part path. [task.py](/src/forge/task.py:272), [merge rule](/src/forge/sync.py:385), [GitHub-style merge test](/tests/test_mainonce_spotted.py:21)  
   Gain 4, Work 2, Harm 3
   Disposition: cut

7. Blocking: Not done: a two-change failure leaves no rule for testing the remaining change first.
   Raise: Not done  
   Case: normal use - A two-member train fails and its log names the older member. Only one change remains, so the plan does not start a second train. Both unmerged changes return to the ordinary queue, where the named older change can merge first using its already-green check, without the promised check on a newer default branch. [Plan](/plans/FORGE-TRAIN-1.md:130), [land.py](/src/forge/land.py:383), [merge.py](/src/forge/merge.py:99)  
   Gain 4, Work 2, Harm 3
   Disposition: cut

8. Blocking: The passing test can pass when the combined check omits a member’s changes.
   Raise: Test  
   Case: normal use - The candidate commit has all three members as parents but its tree omits one member’s files. The stub still reports a green train check, and the separately merged pull requests put all files on the default branch. The planned assertions check the parents and the final default branch, but not the candidate tree that CI tested. [Plan](/plans/FORGE-TRAIN-1.md:109)  
   Gain 5, Work 1, Harm 3
   Disposition: cut

9. Blocking: The named-failure test does not prove the named change’s new check failed.
   Raise: Test  
   Case: normal use - The combined check fails while the named member’s original pull request remains green. The planned stub instead turns that original check red as soon as the train fails. Ordinary `land` can then stop during close, before pushing or checking a new combined head, and still meet the stated `Needs you` assertion. [Plan](/plans/FORGE-TRAIN-1.md:123), [close.py](/src/forge/close.py:462)  
   Gain 3, Work 1, Harm 3
   Disposition: cut

10. Blocking: Ready changes remain excluded after their base has merged.
    Raise: Not done  
    Case: normal use - A follow-up part is ready after its parent merged. The plan excludes every change with `stacked_on`, while Forge retains that field and checks whether the parent actually merged. Several such ready parts therefore cannot form the promised train, and the stated reason that their bases have not merged is wrong. [Plan](/plans/FORGE-TRAIN-1.md:81), [task.py](/src/forge/task.py:501), [merge.py](/src/forge/merge.py:54)  
    Gain 3, Work 1, Harm 3
   Disposition: cut

11. Blocking: The five-change limit is applied before clashes are removed.
    Raise: Plan gap  
    Case: normal use - Six changes are ready, but four of the first five clash; the fifth and sixth could run together. The plan excludes the sixth before `_combine` discovers the clashes, then has fewer than two members. It also says the train already has five when it does not. [Plan](/plans/FORGE-TRAIN-1.md:81)  
    Gain 3, Work 2, Harm 3
   Disposition: cut

12. Blocking: A change sharing a file with the train cannot close while the train runs.
    Raise: Not done  
    Case: normal use - A younger change is still in review and edits a different part of a file touched by an older train member. The plan keeps train members unfinished for the existing overlap hold, so that change waits instead of closing during the combined check, contrary to the plan’s stated behavior. [Plan](/plans/FORGE-TRAIN-1.md:12), [land.py](/src/forge/land.py:383)  
    Gain 3, Work 1, Harm 3
   Disposition: cut

13. Advisory: The planned CI activity records use the wrong round.
    Raise: Functional  
    Case: normal use - A member has completed a worker round. The plan records its train wait from the main checkout, where that unmerged member’s state is absent, so the record gets round zero. The board filters activity by the member’s actual round and does not show the promised running CI step. The additional members’ records also default to a failed outcome. [Plan](/plans/FORGE-TRAIN-1.md:84), [repo.py](/src/forge/repo.py:504), [board.py](/src/forge/board.py:456)  
    Gain 2, Work 1, Harm 1
   Disposition: keep - below the bar (live with)

## Round 2

14. Blocking: A failed check with the same name as Forge’s review job can be ignored.
    Raise: Functional  
    Case: normal use - A repo has another CI job named `Review pull request` that passes on each member but fails on their combination. The plan ignores every check with that name, so the train can pass and merge the broken combination. GitHub permits the same job name in different workflows. [Plan](/plans/FORGE-TRAIN-1.md:78), [checks.py](/src/forge/checks.py:290), [GitHub’s status-check guidance](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)  
    Gain 5, Work 2, Harm 3
   Disposition: keep - The owner chose: accept, and correct the blocking note and the six small ones in the builder notes

15. Advisory: The new merge-rule exclusion misses a conflict already on the default branch.
    Raise: Functional  
    Case: normal use - A ready story part and the default branch both added roadmap entries after the part was closed. The new rule checks for shared merge-rule files only between train members. The initial merge against the default branch can use Forge’s local rule and appear clean even though GitHub cannot merge that pull request without another check. [Plan](/plans/FORGE-TRAIN-1.md:84), [merge rule](/src/forge/sync.py:385), [Git’s merge-tree documentation](https://git-scm.com/docs/git-merge-tree)  
    Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)

16. Advisory: The branch-ownership test does not exercise a branch-name collision.
    Raise: Test  
    Case: normal use - The exact branch name chosen for a train already exists. The test creates `forge-merge-train/keep`, but the train uses a different name. An implementation that force-pushes over its actual target would still leave `keep` untouched and pass the stated assertions. [Plan](/plans/FORGE-TRAIN-1.md:121)  
    Gain 3, Work 1, Harm 2
   Disposition: keep - below the bar (follow-up)

17. Advisory: The stacked-part test cannot prove that an eligible stacked change joins.
    Raise: Test  
    Case: normal use - A ready change’s parent has already merged. The test requires the train to contain exactly `aa`, `bb`, `ff`, `gg` and `hh`, leaving `jj` outside the five places regardless of its merged parent. An implementation that still excludes every stacked change can pass. [Plan](/plans/FORGE-TRAIN-1.md:123), [merge.py](/src/forge/merge.py:54)  
    Gain 3, Work 1, Harm 2
   Disposition: keep - below the bar (follow-up)

18. Advisory: Ready changes left out after selection cannot close during the train.
    Raise: Functional  
    Case: normal use - Six eligible changes are ready, so the sixth stays out of the five-place train. The plan puts all candidates in `training` before `_combine` chooses the members, and starts none of them until the thread ends. The sixth therefore cannot run close during the check, although the plan promises that ready changes left out can do so. [Plan](/plans/FORGE-TRAIN-1.md:82), [land.py](/src/forge/land.py:88)  
    Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)

19. Advisory: Repositories that cannot create draft pull requests never get a train.
    Raise: Functional  
    Case: normal use - A private repository on a GitHub plan without draft pull requests uses CI and agent merges. The planned draft creation fails on every run, so changes fall back to individual merges. Forge already handles this GitHub limitation for ordinary pull requests. [Plan](/plans/FORGE-TRAIN-1.md:85), [close.py](/src/forge/close.py:915), [GitHub’s pull-request documentation](https://docs.github.com/en/rest/pulls/pulls)  
    Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)

20. Advisory: Cleanup lacks a pull-request identifier when the read after creation fails.
    Raise: Plan gap  
    Case: normal use - GitHub creates the draft, but the following `gh pr view` fails during a network problem. The plan obtains the number and URL from that read, then requires cleanup and its failure message to use them. It does not specify how to close or identify the draft in this case. [Plan](/plans/FORGE-TRAIN-1.md:85), [close.py](/src/forge/close.py:899)  
    Gain 3, Work 1, Harm 2
   Disposition: keep - below the bar (follow-up)
