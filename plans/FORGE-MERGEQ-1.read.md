---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-18T05:52:03.089592+00:00
seconds: 212.901
read_hash: da2153776227908c67f2e826854deca3dfa5b3ff
round: 3
passed: no
doc_seen: 4c9e0ca6c9467855d35c17d89d5d5a2fdf904dd0
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: c44acd520e14bfa130456b087bf45092e8c1570b
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1ece5-0260-7cd2-b5a1-0a941555a861
session:
loop_choice: accept
loop_reason: Owner accepted read round 3: note 14 fixed in the builders' section, note 13 kept
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

1. Blocking: Not done: item 1: Push tests can use the wrong default branch.
   Raise: Not done  
   Case: normal use - The default branch is named `master`.  
   The plan moves `origin/master` but does not set `origin/HEAD` ([plan](/plans/FORGE-MERGEQ-1.md:63)). Actions checkouts can lack that symbolic reference ([existing test](/tests/test_testplace_fullrun.py:257)); Forge then falls back to `main` ([repo.py](/src/forge/repo.py:475)), so the test command fails or selects the wrong base.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - on a push the test jobs run `git remote set-head origin --auto` first, as the full-suite job does; the push test uses a default branch named `master` with no `origin/HEAD`.

2. Blocking: The push test can include changes that merged earlier.
   Raise: Functional  
   Case: normal use - A pull request merged the default branch into its own branch and is then merged with a merge commit.  
   The planned reference change leaves `forge test --change`’s merge-history widening intact ([fasttest.py](/src/forge/fasttest.py:359)). It finds the pull request’s earlier merge and moves the base back to the branch’s old fork, selecting tests for changes already on the default branch. That contradicts the promised run of only tests related to this merge.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - the push passes its base in `FORGE_PUSH_BASE`, and `forge test --change` then uses it and skips the widening over merges; a new test covers a pull request that had merged the default branch in.

3. Blocking: Not done: item 2: A failure can disappear beyond the ten-commit limit.
   Raise: Not done  
   Case: normal use - A queue merges eleven ready changes while their default-branch tests are still running; the first run then fails.  
   The planned scan stops after ten commits ([plan](/plans/FORGE-MERGEQ-1.md:64)), so it misses that failure and permits further merges without a green full run. The existing ten-commit full-run check fails closed when it finds no proof ([fullrun.py](/src/forge/fullrun.py:54)); the proposed red check would instead report no failure.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - the ten-commit window of failures is gone: the newest finished result decides; the 30-commit look-back only finds the newest commit that has a result, and Risks names what that gives up.

4. Blocking: Not done: item 2: An older full-run success can hide a later failure on the same commit.
   Raise: Not done  
   Case: normal use - A full run passes, then a rerun of the related tests on the same default-branch commit fails.  
   The planned scan stops at a commit with a green full-run status before considering its test failures ([plan](/plans/FORGE-MERGEQ-1.md:64)). It therefore clears a failure for which there is no later green full run.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - on one commit the result that finished last decides, so a failed rerun after a green full run is red; the red-wait test has both orders.

5. Blocking: Unproven: item 2: A waiting merge may never see the repair.
   Raise: Test  
   Case: normal use - The owner merges the repair, creating a new default-branch commit, and its full run passes.  
   The plan polls `origin/<default>`, but does not require refreshing it during the wait; the current merge fetches before its loop and after its check wait ([merge.py](/src/forge/merge.py:55)). The proposed test puts the green status on the unchanged head ([plan](/plans/FORGE-MERGEQ-1.md:75)), so it passes even if the waiter never sees the repaired commit.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - each 60-second check fetches the default branch; the test adds a repair commit with a green run and expects the waiting merge to see it.

6. Blocking: Unproven: item 2: The default branch can turn red during the pull request’s check wait.
   Raise: Test  
   Case: normal use - A merge starts while the default-branch run is pending; that run fails while Forge waits for the pull request’s combined checks.  
   The current path can wait for those checks before calling GitHub to merge ([merge.py](/src/forge/merge.py:162)). The planned test starts with the branch already red, so an implementation that checks only on entry would pass while still merging after the failure.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - the red check runs right before `gh pr merge`, after any check wait; the test turns the branch red during that wait.

7. Blocking: Unproven: item 2: A successful rerun of related tests can hide the earlier failure.
   Raise: Test  
   Case: normal use - The default-branch test fails and someone reruns that same test successfully, without running the full suite.  
   The planned test uses a failed parent and a green child ([plan](/plans/FORGE-MERGEQ-1.md:75)). It would pass if the new reader used only the latest check attempt. Forge’s history reader explicitly requests all attempts to retain failures ([backfill.py](/src/forge/backfill.py:77)).  
   Gain 3, Work 2, Harm 3
   Disposition: keep - by the chosen rule a green rerun of the failed tests is a green result, as the owner's decision 4 says (green clears the stop); Risks names it as an accepted limit and the nightly full run is the backstop; settled by the owner, 18 Nov 2026.

8. Blocking: Unproven: item 2: The laptop-test red wait has no failure test.
   Raise: Test  
   Case: normal use - A repo tests on the laptop and its full run reports failure.  
   The plan says this mode reads `forge-full-suite` ([plan](/plans/FORGE-MERGEQ-1.md:64)), but its red-wait test supplies a failed `tests` check instead. All named tests could pass if failed full-run statuses were ignored and laptop-test repos continued merging.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - a laptop-test test now checks that a failed `forge-full-suite` result stops the merge and a green one lets it go.

## Round 2

9. Blocking: A red-branch wait can outlive permission for agent merges.
   Raise: Security  
   Case: normal use - While a merge waits for a failed default branch, the owner switches the repo to human merges; a later test run passes.  
   The current merge path checks permission before its final GitHub call ([merge.py](/src/forge/merge.py:194)). The amended plan inserts a potentially 90-minute wait after that check and then merges when the result is green ([plan](/plans/FORGE-MERGEQ-1.md:67)), without requiring permission to be checked again. Forge can therefore merge after the owner has withdrawn permission.  
   Gain 4, Work 2, Harm 4
   Disposition: cut - after any red wait, merge checks the merge setting on the newest default branch again right before `gh pr merge`, as `merge.py:194-196` does, and stops with the usual human-merge refusal; the red-wait test withdraws permission during the wait (builders' section only).

10. Advisory: A repair can bypass the combined test for overlapping changes.
    Raise: Functional  
    Case: normal use - A waiting pull request and the repair both edit different lines of the same file.  
    The amended plan fetches the repair during the red wait and then merges ([plan](/plans/FORGE-MERGEQ-1.md:67)). The existing overlap comparison happens before that wait ([merge.py](/src/forge/merge.py:108)), so the new default-branch change can be merged without the combined run promised for overlapping files.  
    Gain 3, Work 2, Harm 3
    Disposition: cut - fixed in the builders section: after any red wait, merge goes back to the start of its loop (`merge.py:108`), so the overlap comparison, any combined run and the red check run again on the fetched default branch; the red-wait test has a repair that overlaps the item.

11. Advisory: Disputed keep 7: A pending rerun can hide the last failed result.
    Raise: Functional  
    Case: normal use - Someone reruns a failed default-branch test and the new attempt is still running.  
    The amended rule requests GitHub’s latest attempt and ignores pending results ([plan](/plans/FORGE-MERGEQ-1.md:67)). The pending attempt can hide the earlier failure, letting the scan fall back to an older green commit before any rerun passes. Forge’s existing history reader requests all attempts for this reason ([backfill.py](/src/forge/backfill.py:77)). This differs from the accepted green rerun.  
    Gain 3, Work 2, Harm 3
    Disposition: cut - fixed in the builders section: this is not the accepted green-rerun limit; the red check now reads every attempt (`filter=all`, as `backfill.py:77`), so a rerun still in progress leaves the earlier failure as the last finished result, and the test covers it.

12. Advisory: Unproven: item 1: A CI repo with custom check names can get no push test.
    Raise: Test  
    Case: normal use - `test_place` is `ci`, and a required `build` check runs the app tests without a check named `tests`.  
    The current workflow generator removes its test jobs unless `checks` contains `tests` ([prcheck.py](/src/forge/prcheck.py:294)). The amended plan promises a push run for CI-test repos but tests only the standard setup ([plan](/plans/FORGE-MERGEQ-1.md:75)); that test can pass while this supported configuration gets no post-merge test.  
    Gain 3, Work 2, Harm 3
    Disposition: keep - a repo whose required checks are its own (no Forge `tests` job) runs its tests in its own workflow, which Forge does not generate; the push run covers Forge's generated test jobs only, and that repo's own main CI stays its owner's (coordinator ruling, not worth a second generator path)

## Round 3

13. Advisory: Disputed keep 12: A failing custom push test does not stop merges.
    Raise: Functional  
    Case: normal use - A repo’s own `build` check runs tests on both pull requests and the default branch, and its default-branch run fails.  
    Even when the owner supplies that push workflow, the planned red check reads only `tests` and `forge-full-suite` ([plan](/plans/FORGE-MERGEQ-1.md:67)). It ignores the failed `build` result and can continue merging. This is distinct from whether Forge generates the repo’s push workflow.  
    Gain 3, Work 2, Harm 3
    Disposition: keep - a repo whose required checks are its own runs its own default-branch CI; Forge does not generate it, and the red check reads only the runs Forge generates (`tests`) and the full run, as the owner accepted on 18 Nov 2026.

14. Advisory: A cancelled test rerun can clear the red wait without passing.
    Raise: Functional  
    Case: normal use - The default-branch test fails, someone reruns it, then cancels the rerun.  
    The plan reads all attempts, selects the latest completed check, and treats conclusions other than failure or timeout as not red ([plan](/plans/FORGE-MERGEQ-1.md:67)). A cancelled attempt therefore clears the earlier failure, contrary to the same rule’s requirement to stay red until the rerun ends green. Forge’s existing result reader retains the earlier finished attempt after cancellation ([board_facts.py](/src/forge/board_facts.py:457)).  
    Gain 3, Work 2, Harm 3
    Disposition: cut - fixed in the builders section: only a `tests` run that ended `success`, `failure` or `timed_out` is a result; a cancelled, skipped or neutral run never counts as green, so a cancelled rerun leaves the earlier failure red; the red-wait test covers a cancelled and a skipped rerun.
