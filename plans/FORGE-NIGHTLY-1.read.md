---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-12T16:06:56.154987+00:00
seconds: 501.813
read_hash: eaa557b536e1651aabf9b724dd902e1d767aa288
round: 1
passed: no
doc_seen: eaa557b536e1651aabf9b724dd902e1d767aa288
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1d07b-7a0a-7023-acde-70599b29afa0
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

1. Blocking: Not done: Retrying a failed run can remove its row before a pass.
   Raise: Not done  
   Case: normal use - A person reruns a failed nightly run, and the retry is running or cancelled.  
   A rerun keeps the same run ID, as [the existing rerun test](/tests/test_busy_repo_views_finish_quickly.py:116) records. The proposed rule in [the plan](/plans/FORGE-NIGHTLY-1.md:121) skips that run’s new conclusion, but the run list does not contain a separate entry for its earlier failed attempt. After the cache refreshes, the row and alert can disappear without a pass.  
   Gain 4, Work 2, Harm 3
   Disposition: cut - Settled 4: an unfinished or cancelled rerun of the full run reads its earlier attempts (actions/runs/<id>/attempts/<n>) until one is finished, so the row stays; test_3 covers a rerun in progress and cancelled; owner part says a rerun does not remove the row.

2. Blocking: Not done: An unrelated job’s expired logs can hide the full-test failure.
   Raise: Not done  
   Case: normal use - An infrequent scheduled job last failed and its logs expired; a full test run then fails.  
   [failed_schedules](/src/forge/board_facts.py:433) returns no failures if it cannot read the logs for *any* failed scheduled workflow. GitHub can still supply the full-test result and its logs, but the board and `forge next` lose it because of the unrelated job. The repository already covers expired logs as a real response in [test_land_checks.py](/tests/test_land_checks.py:115).  
   Gain 3, Work 2, Harm 3
   Disposition: cut - Settled 5: an unreadable log keeps that failure with no job names instead of dropping the whole list; test_2 adds a backup.yml failure whose log read fails beside the failed full run.

3. Blocking: Not done: Changing the full-test setting can reuse the wrong classification.
   Raise: Not done  
   Case: normal use - A team switches from CI tests to local tests, or names a different full-test workflow, within ten minutes of viewing a failure.  
   The plan caches each failure’s `full_run` value in [the renamed cache](/plans/FORGE-NIGHTLY-1.md:125). [The cache](/src/forge/board_facts.py:178) is shared across worktrees and does not include the setting in its key. `forge next` can therefore mark the old workflow as Needs you, or miss the newly named one. The planned setting changes all advance past the cache, so the test misses this case.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - Settled 6: full_run is set on every call from the current forge.toml, outside the cache, and the cache name holds the requested workflow; test_2 switches to local tests and to a named nightly.yml inside the ten-minute cache.

4. Blocking: Unproven: item 1: A busy repository can still miss its full-test failure.
   Raise: Test  
   Case: normal use - Frequent scheduled jobs push the nightly full run out of the shared list of 100 runs.  
   The plan adds a separate scheduled-runs request for this case, but [the page test](/plans/FORGE-NIGHTLY-1.md:168) supplies the failure in the shared list and makes the separate list empty. The named tests can all pass if the new request is omitted or returns no scheduled runs.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - test_1's fake now puts the failure only in the full run's own event=schedule request and 100 runs of another workflow in the shared list (Settled 2 fixes the argument order so the stub tells the two requests apart).

5. Blocking: Unproven: item 3: The page may never show “Fix in progress.”
   Raise: Test  
   Case: normal use - An agent starts the suggested fix while the full-test failure remains.  
   [The planned browser test](/plans/FORGE-NIGHTLY-1.md:177) checks only the row before a fix starts. The later test checks the JSON `fixing` value, but does not check the page. Both can pass if [the row renderer](/src/forge/board_app/now.js:127) ignores that value and never displays the promised words.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - test_1's browser script now starts the suggested fix and checks that the live page shows Fix in progress with the same title; listed in the Tests cell for item 3.

6. Blocking: Unproven: item 2: Retention for other scheduled jobs has no test.
   Raise: Plan gap  
   Case: normal use - A backup job fails, then its next scheduled run is running or cancelled.  
   [The plan](/plans/FORGE-NIGHTLY-1.md:12) promises to keep that failure in `forge next`, but its backup case tests only an ordinary failure; the running and cancelled cases use the full-test workflow. The tests would pass if the new selection rule applied only to full tests.  
   Adds work: test retention for another scheduled job; F 2 x H 2 = 4; 2 x C = 2  
   Gain 3, Work 2, Harm 3
   Disposition: cut - the planner's choice that changed the rule for every other scheduled job is removed from the story (Settled 3 applies only to the full run; Notes say so), so no retention promise remains for other jobs.

7. Advisory: Plan gap: The outage promise conflicts with the ten-minute cache.
   Raise: Plan gap  
   Case: normal use - GitHub becomes unreachable just after Forge cached a failed run.  
   [The plan](/plans/FORGE-NIGHTLY-1.md:13) says no row appears while GitHub is unreachable, but [the cache](/src/forge/board_facts.py:178) returns a fresh saved result before trying GitHub. The old row can remain visible during the outage.  
   Adds work: check GitHub while the cached result is fresh; F 1 x H 1 = 1; 2 x C = 2  
   Gain 2, Work 2, Harm 2
   Disposition: cut - the owner sentence now says the row goes away only when GitHub cannot be read for more than ten minutes, which matches the ten-minute cache.
