---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-18T03:46:51.938873+00:00
seconds: 700.714
read_hash: 878e8a52a049c2315c3aa9bce720eb878bfa30a9
round: 1
passed: no
doc_seen: 878e8a52a049c2315c3aa9bce720eb878bfa30a9
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1ecb9-0d2c-7ba3-967f-9b980e7a0a1b
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

1. Blocking: Not done: the default-branch test command does not exist.
   Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:90); [fasttest.py](/src/forge/fasttest.py:19).
   Case: normal use - After a merge, `forge test --change --base <before>` is rejected because `forge test` has no `--base` option. Its existing `--pytest` option takes a different path and does not run the starter’s `fast_test`. The required command change is outside MERGE’s Scope.
   Gain 5, Work 3, Harm 3
   Disposition: cut - no new option: on a push, one workflow line points origin/<default> at the push's previous commit, so the unchanged `forge test --change` selects only what the merge brought; it is in MERGE's Scope (`prcheck.py` whole).

2. Blocking: Not done: the red-branch check cannot recognize the planned push result.
   Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:89); [prcheck.py](/src/forge/prcheck.py:119).
   Case: normal use - On a push, both generated workflow shapes name the result `tests (other event)`, while the plan looks for `tests`. A failed post-merge run can therefore be missed. The planned workflow assertion does not check the result’s name.
   Gain 5, Work 2, Harm 3
   Disposition: cut - the gate is now named `tests` on `pull_request` and `push` (`tests (other event)` stays for `pull_request_target`), and the MERGE test asserts that name.

3. Blocking: Plan gap: MERGE’s Scope excludes the workflow wiring it requires.
   Raise: Plan gap — [task table](/plans/FORGE-CITIME-1.md:122); [prcheck.py](/src/forge/prcheck.py:74).
   Case: normal use - The push needs the previous commit in `BASE_SHA` and a different test command. MERGE may change only triggers and job `if` lines, but the current base value and command are elsewhere in the workflow generator.
   Gain 4, Work 1, Harm 2
   Disposition: cut - MERGE's Scope now holds `src/forge/prcheck.py` whole, after GROUPS.

4. Blocking: Plan gap: a persistent failure on the default branch has no permitted repair path.
   Raise: Plan gap — [plan](/plans/FORGE-CITIME-1.md:89); [fullrun.py](/src/forge/fullrun.py:75).
   Case: normal use - A real regression makes the default branch red. The rule blocks the repair pull request as well, and a full run can test only the current default-branch commit. The refusal’s instruction to fix the branch cannot be completed through the stated flow.
   Gain 5, Work 3, Harm 3
   Disposition: cut - repair path written: the agent fixes the break in a fix, the owner merges it on GitHub, the agent starts a full run, and its green status clears the red; the refusal's Next says so, and Risks names the owner's one merge.

5. Blocking: Not done: the red-branch rule does not cover human merges.
   Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:32); [land.py](/src/forge/land.py:163).
   Case: normal use - Human merge is the default. Forge hands the person a pull-request link without calling `merge.merge`, the only place assigned the red-branch wait, so the promised rule does not stop that merge.
   Gain 5, Work 3, Harm 3
   Disposition: cut - narrowed to Forge's merges in What changes and Done-when 6; land's human hand-off line adds a red note, and Risks says Forge cannot stop a GitHub merge.

6. Blocking: Not done: a later commit’s green check can hide the latest failure.
   Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:89); [merge.py](/src/forge/merge.py:108).
   Case: normal use - Two changes merge while their default-branch checks run concurrently. The newer commit’s narrow check finishes green first; the older commit’s check then fails. Walking commits newest first finds the green result and permits another merge even though the latest finished run is red.
   Gain 4, Work 2, Harm 3
   Disposition: cut - red now means any failed `tests` run or full run since the last green full run, within ten first-parent commits; a later green narrow run does not clear it.

7. Blocking: Not done: an up-to-date branch rule forces another check for a non-overlapping change.
   Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:31); [merge.py](/src/forge/merge.py:220).
   Case: normal use - GitHub can require a pull request to include the current default branch before merging. Forge’s existing response to `BEHIND` runs close again, including a new check, even when the files do not overlap. The plan’s test uses a permissive GitHub stub.
   Gain 4, Work 2, Harm 3
   Disposition: cut - when GitHub requires up-to-date branches (`land._up_to_date_rule`), merge keeps today's push and wait; named in What changes, Done-when 5, Risks and the MERGE test.

8. Blocking: Not done: an item’s own guide edits are mistaken for a merge repair.
   Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:87); [merge.py](/src/forge/merge.py:128).
   Case: normal use - A ready item edits a Forge guide and the default branch gains an unrelated file. The existing comparison sees the item’s guide edits in the combined tree, sets `overlap`, and starts another check even though no guide repair occurred.
   Gain 3, Work 2, Harm 3
   Disposition: cut - a guide repair counts only for a skills path whose merged content differs from both the item's head and the gained default branch; the MERGE test's item edits the guide.

9. Blocking: Plan gap: TIME and OXLINT cannot start together with their stated Scopes.
   Raise: Plan gap — [plan](/plans/FORGE-CITIME-1.md:129); [task.py](/src/forge/task.py:516).
   Case: normal use - Both parts own the guide template, both host copies and the brief. Forge checks whole-file Scope overlap across started stories; different sections do not allow two unreviewed parts to start together.
   Gain 4, Work 1, Harm 2
   Disposition: cut - TIME no longer touches guide files; the text moved to a new RULES part that starts after OXLINT merges; guide copies are refreshed by `forge sync` and left out of every Scope.

10. Blocking: Not done: the small-change rule drops a shared setting before checking it.
    Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:82); [docskip.py](/src/forge/docskip.py:130).
    Case: normal use - A change to `conftest.py` matches the prescribed test-file globs and is dropped before the shared-settings check. It is then classified as small, although the plan explicitly requires all groups for that file.
    Gain 3, Work 1, Harm 3
    Disposition: cut - the lockfile and shared-settings check now runs on all changed paths before test files are dropped; the GROUPS test has a `conftest.py` case.

11. Blocking: Not done: five commits are not five pushes.
    Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:77); [close.py](/src/forge/close.py:419).
    Case: normal use - A developer pushes several commits at once. The previous push’s tested head can fall outside the last five commits even though it is among the last five pushes, so close and doctor can miss the slower run the owner chose to report.
    Gain 3, Work 2, Harm 3
    Disposition: cut - Forge reads the last 30 commits and takes the last five that have check runs (a push's head), so pushes, not commits, are counted; the TIME test has a three-commit push.

12. Blocking: Not done: close can refuse before the failed run’s other jobs finish.
    Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:79); [checks.py](/src/forge/checks.py:331).
    Case: normal use - One job fails while another still runs. The current wait refuses as soon as it sees the failure, so it cannot print the promised time from the first start through the last completion. The planned failure case has only one test group.
    Gain 3, Work 2, Harm 3
    Disposition: cut - on a red refusal the line covers the jobs that ended and says how many were still running; What changes says so and the TIME test has a two-group case.

13. Blocking: Plan gap: the required live starter test demands the old browser behavior.
    Raise: Plan gap — [plan](/plans/FORGE-CITIME-1.md:105); [test_starter_tree.py](/tests/test_starter_tree.py:343).
    Case: normal use - Its live web-change check requires `web:e2e`, Playwright and the Docker stack. A starter that implements the new web-only behavior fails this required test.
    Gain 4, Work 1, Harm 2
    Disposition: cut - STARTER updates the live web-change listing in `tests/test_starter_tree.py` to expect no `web:e2e` and no Playwright.

14. Blocking: Unproven: item 3: the named test can pass without running API files in parallel.
    Raise: Test — [plan](/plans/FORGE-CITIME-1.md:103); [test_starter_tree.py](/tests/test_starter_tree.py:585).
    Case: normal use - The live part runs only with `FORGE_STARTER_LIVE=1`, and the named test does not establish that files ran concurrently. Three ordinary passing invocations can therefore leave the current serial setting in place.
    Gain 3, Work 2, Harm 3
    Disposition: cut - STARTER adds a static assertion that the API config no longer sets `fileParallelism: false`, and the builder runs the live test three times with `FORGE_STARTER_LIVE=1` and puts the times in the pull request.

15. Blocking: Unproven: item 3: shared configuration changes can still run browser tests.
    Raise: Test — [plan](/plans/FORGE-CITIME-1.md:104); [affected.mjs](/src/forge/templates/starter-python/scripts/affected.mjs:15).
    Case: normal use - Changing `package.json` selects all parts, and the Python starter’s full command includes browser tests. The proposed no-browser assertion covers a web-file change, so it can pass while this pull-request path still runs them.
    Gain 3, Work 2, Harm 3
    Disposition: cut - any run with a base skips browser tests and the browser install, also when everything is selected; the starter tests add a root `package.json` case.

16. Blocking: Unproven: item 3: a clean Python web-only run can lose its installation steps.
    Raise: Test — [plan](/plans/FORGE-CITIME-1.md:85); [test.mjs](/src/forge/templates/starter-python/scripts/test.mjs:47).
    Case: normal use - The current `stack` condition controls dependency installation as well as Docker. Setting it to API-only leaves a fresh web run without the packages needed by `api-types` and the web checks. The proposed `--list` test does not execute those commands.
    Gain 3, Work 2, Harm 3
    Disposition: cut - the Docker-only-for-API change is dropped; `stack` stays as it is, and the Python test checks that a web-only listing keeps the installs.

17. Blocking: Plan gap: MERGE omits its train regression from the Tests cell.
    Raise: Plan gap — [task table](/plans/FORGE-CITIME-1.md:122); [test_train_land_all.py](/tests/test_train_land_all.py:317).
    Case: normal use - The plan asks for an extended train test, but the Tests cell names only the two new merge tests. Existing train tests also expect three disjoint changes to form a train, contrary to the new rule.
    Gain 4, Work 2, Harm 2
    Disposition: cut - MERGE no longer changes the merge train, so `tests/test_train_land_all.py` stays as it is and is named as staying green in the Tests cell.

18. Advisory: Plan gap: the five-item train limit conflicts with “every” overlapping item.
    Raise: Plan gap — [plan](/plans/FORGE-CITIME-1.md:88); [land.py](/src/forge/land.py:37).
    Case: normal use - Six ready changes edit different lines of the same file. The stated five-item limit leaves one outside the single shared run promised for every overlapping item.
    Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)

19. Advisory: Plan gap: an even-sized sample has no single median pull request.
    Raise: Plan gap — [plan](/plans/FORGE-CITIME-1.md:80); [doctor.py](/src/forge/doctor.py:313).
    Case: normal use - With 20 measured pull requests, the median can fall between the tenth and eleventh times. The plan does not say which pull request supplies “the slowest job of the median one.”
    Gain 3, Work 1, Harm 2
   Disposition: keep - below the bar (follow-up)
