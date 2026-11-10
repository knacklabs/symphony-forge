---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-10T17:53:21.502583+00:00
seconds: 691.627
read_hash: 09cbc0ef62bcc61105951e9764d656d55564639b
round: 2
passed: no
doc_seen: 09cbc0ef62bcc61105951e9764d656d55564639b
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 75594a0d4cb3898a15ba1b164794d7ee994fbed7
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1c67c-1a5c-7860-a9ac-8e6eb00519b7
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

1. Blocking: Not done: The list can read stale facts after a normal merge.  
   Raise: Not done  
   Case: normal use - a prototype fix merges from its worktree.  
   [Forge fetches the merged default branch](/src/forge/merge.py:292) without updating the main checkout. The plan reads the sample setting and labels from that checkout ([plan](/plans/FORGE-PRODGAP-1.md:63)), so merged gaps can be missing or remain visible after they are closed. The proposed fixtures commit in the checkout being read.  
   Gain 5, Work 3, Harm 3
   Disposition: cut - Settled 1 now reads the signed-off test, the sample-data setting and the "Demo only" search from the default branch as last fetched (`repo.is_prototype(top, cfg, (landed,))`, `repo.sample_data(top, ref=landed)`, `git grep` at that ref); the fixtures in `test_1`, `test_2` and `test_5` reach the remote default branch from a second clone while the main checkout keeps the old files, and Done-when 1 says so.

2. Blocking: Not done: The prescribed earlier-adopted client cannot show its gaps.  
   Raise: Not done  
   Case: normal use - a previously adopted client has an accepted sign-off and upgrades Forge.  
   The named [adopted fixture](/tests/fixtures/adopted-v1.2.2/client/forge.toml:4) has `stage = "live"`. The [plan](/plans/FORGE-PRODGAP-1.md:68) returns an empty list outside the prototype stage, and [sample-data mode](/src/forge/repo.py:660) also requires that stage. This contradicts both the promised immediate upgrade result and the proposed test that turns the setting on.  
   Gain 4, Work 2, Harm 3
   Disposition: cut - correct: the adopted fixture has `stage = "live"`. Evidence and the details now say a live repo shows no list (it never had sample mode or the prototype allowance), the earlier-adopted case writes `stage = "prototype"` as `tests/test_proto_next.py` does, and the owner-facing bullet now says "a repo that is still marked as a prototype and already has an accepted sign-off" (a forced change to What changes for you).

3. Blocking: Not done: The filter does not identify which fixes actually had a light review.  
   Raise: Not done  
   Case: normal use - a client upgrades after building its prototype on an earlier Forge release.  
   The [planned filter](/plans/FORGE-PRODGAP-1.md:64) requires `fix_kind`, but [the earlier release](/tests/fixtures/forge-v1.2.2/src/forge/task.py:238) recorded no such field for prototype fixes, even though [they received light reviews](/tests/fixtures/forge-v1.2.2/src/forge/review.py:182). Conversely, a fix can retain its allowance and receive a full review after sign-off, as [the current test shows](/tests/test_aha_review.py:92).  
   Gain 4, Work 2, Harm 3
   Disposition: cut - the filter no longer uses `fix_kind`. A part counts when its saved state has `allow_large == "Prototype before sign-off"` and `review.blocking_level == "P0"`; the earlier release saved the same `review.blocking_level` (`tests/fixtures/forge-v1.2.2/src/forge/review.py`), and a full review after sign-off saves `P1`, so `test_5` has an old-shape fix and a P1 case. The Notes give the owner the choice to drop the line instead, with keep as the recommendation.

4. Blocking: Not done: The next-step view hides the gap details while work is in progress.  
   Raise: Not done  
   Case: normal use - the agent starts the first of several gap changes.  
   The plan keeps the existing [next-step rendering](/src/forge/nextstep.py:366), which prints the rows only when nothing else is in progress. The heading remains, but the other gaps and their start phrases disappear. The [proposed test](/plans/FORGE-PRODGAP-1.md:75) checks the rows only when idle.  
   Gain 4, Work 2, Harm 3
   Disposition: cut - `gaps.listing` returns `always: True` and `_report` prints the rows when `quiet or shown.get("always")` (Settled 5, one edit in place); `test_3` starts the first change and checks that the heading and all rows remain. Done-when 3 and one bullet of What changes for you say so (forced).

5. Blocking: Unproven: items 1–3: The tests never show the gaps together.  
   Raise: Test  
   Case: normal use - a signed-off sample prototype also has labelled features and light-reviewed fixes.  
   Each [planned list test](/plans/FORGE-PRODGAP-1.md:73) exercises one gap at a time. An implementation that shows only the first matching gap would pass those tests while hiding the other open work.  
   Gain 4, Work 2, Harm 3
   Disposition: cut - new Done-when 3 and `test_3` show the three gaps together in a fixed order, then show the rest after the first clears. To stay within three Covers per task, the demo-only and light-review lines share Done-when 2 (forced change to Done when).

6. Blocking: Unproven: item 3: A follow-up story is not tested.  
   Raise: Test  
   Case: normal use - reviewing several parts needs a story rather than a small fix.  
   The [clearing rule](/plans/FORGE-PRODGAP-1.md:67) includes a landed story, but the test covers only a landed fix. Code that ignores stories would pass. A story’s [state can also reach the default branch with its first part](/src/forge/task.py:499), before [the whole story is complete](/src/forge/story.py:877).  
   Gain 3, Work 2, Harm 3
   Disposition: cut - a story counts as naming a part only when `story.completed` reports it done (read from `board._machine_history(top)["stories"]`), and a story whose first part has landed does not (Settled 7); `test_5` has the not-done and the done story cases.

7. Blocking: Plan gap: The first gap’s work order conflicts with sample mode.  
   Raise: Plan gap  
   Case: normal use - the agent starts the sample-data change before tests and CI exist.  
   The [plan](/plans/FORGE-PRODGAP-1.md:63) says to set up tests and CI before turning sample data off. While it remains on, [workers are told not to add or run either](/src/forge/worker.py:46), and [Forge does not generate the workflow](/src/forge/prcheck.py:225). The plan leaves those worker rules unchanged.  
   Gain 4, Work 2, Harm 3
   Disposition: cut - superseded by the owner's simpler form: the sample-data row starts no change, so no worker is told to set up tests while sample mode is on. It points to the existing coordinator-owned step in the guide.

8. Blocking: Plan gap: The first gap can start a change that cannot close its settings edit.  
   Raise: Plan gap  
   Case: normal use - the start step describes the result as tests and CI being enabled and sample data being off.  
   The [pinned start phrase](/plans/FORGE-PRODGAP-1.md:63) does not name `forge.toml`, and [intake uses the generated Done-when text](/src/forge/intake.py:113). If that text also omits the filename, [close refuses the settings change](/src/forge/task.py:184). No proposed test starts and closes this change.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - superseded by the owner's simpler form: the sample-data row starts no change and fixes no Done-when text, so there is no change whose settings edit close could refuse. It points to the existing step, whose close is covered by `tests/test_sample_setup.py::test_7`.

## Round 2

9. Blocking: Plan gap: The first fix cannot record a Personal data answer.  
   Raise: Plan gap  
   Case: normal use - the customer answers Personal data after prototype sign-off.  
   The [plan](/plans/FORGE-PRODGAP-1.md:60) restricts the fix to `forge.toml` and synced files. But [close](/src/forge/records.py:639) requires the answer in `docs/product/BRIEF.md`. The [existing close test](/tests/test_sample_setup.py:345) commits that brief, so it does not prove the prescribed settings-only fix can close.  
   Gain 5, Work 2, Harm 3
   Disposition: cut - correct for a settings-only fix. The sample-data row no longer prescribes a fix; it points to the existing coordinator-owned step, whose close needs the committed brief answer and is tested that way by `tests/test_sample_setup.py::test_7`.

10. Blocking: Not done: The first fix clears the sample-data gap while the app still uses sample data.  
    Raise: Not done  
    Case: normal use - a signed-off browser-only prototype has mock data and no tests.  
    The [first fix](/plans/FORGE-PRODGAP-1.md:60) changes only settings and generated Forge files. [Turning off the setting](/src/forge/repo.py:652) does not change the app or add tests, yet the [gap disappears](/plans/FORGE-PRODGAP-1.md:71). The list therefore stops reporting the main gap while the prototype still has it.  
    Gain 5, Work 3, Harm 3
   Disposition: cut - correct: turning the setting off changes no app file. The plan now says plainly (Evidence, Risks, Settled 6, Notes 5) that the row clears on the setting, the only fact the code uses and the only declaration there is; Forge cannot see made-up data or a missing back end, and the Personal data refusal on the turn-off is the guard. The owner-visible Risks say so.

11. Advisory: Plan gap: The first fix is assigned to a worker instructed not to edit it.  
    Raise: Plan gap  
    The [plan](/plans/FORGE-PRODGAP-1.md:60) says naming `forge.toml` in Done-when permits the worker to edit it and says workers build this change. The [worker instruction](/src/forge/worker.py:42) instead says never to edit it; the existing [coordinator guide](/src/forge/templates/skill.md:679) assigns this fix to the coordinator.  
    Gain 3, Work 1, Harm 3
   Disposition: cut - correct. The plan no longer says a worker builds the sample-data change; it is the coordinator-owned step, and the brief rule that workers never edit `forge.toml` stays.

12. Advisory: Functional: A merged stage change leaves the list using the old stage.  
    Raise: Functional  
    The amended [plan](/plans/FORGE-PRODGAP-1.md:65) reads `stage` from the checkout, although a [normal merge](/src/forge/merge.py:292) fetches the default branch without updating that checkout. After a settings fix changes the stage to `live`, the list can remain visible against the old `prototype` setting, contrary to the promised live-repo behavior.  
    Gain 3, Work 2, Harm 3
   Disposition: cut - Settled 1 now reads `repo` and `stage` from `forge.toml` at the landed ref, not from the checkout; `test_1` pushes `stage = "live"` from a second clone and checks that the list disappears.

13. Advisory: Plan gap: A documentation-only follow-up can clear a part after another light review.  
    Raise: Plan gap  
    The [clearing rule](/plans/FORGE-PRODGAP-1.md:74) excludes only fixes in the prototype light-review set. A later documentation fix can name the part without that allowance and still receive a [light review](/src/forge/review.py:178); it would clear the part, although the [planned test](/plans/FORGE-PRODGAP-1.md:91) says a light-reviewed fix does not clear it.  
    Gain 3, Work 2, Harm 3
   Disposition: cut - Settled 7 now excludes any fix whose saved `review.blocking_level` is `P0` from naming a part, with or without the allowance; `test_5` uses the docs-only `tune-search` fix as the case.

14. Advisory: Functional: A nested test can keep the Demo only gap open.  
    Raise: Functional  
    The [search](/plans/FORGE-PRODGAP-1.md:73) excludes only the root `tests/` directory. Forge also recognizes [nested test files](/src/forge/repo.py:31), including the starter’s [browser tests](/src/forge/templates/starter/apps/web/e2e/rules/sign-in.spec.ts:23). A test asserting that “Demo only” is absent would itself be listed after the app label was removed.  
    Adds work: exclude nested test files from the label search; F 2 x H 2 = 4; 2 x C = 4.  
    Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)

15. Advisory: Plan gap: The board’s proposed fast fallback cannot recognize completed stories.  
    Raise: Plan gap  
    For a large history, the [fallback](/plans/FORGE-PRODGAP-1.md:157) reads only fix records and claims they provide the same data. But the [clearing rule](/plans/FORGE-PRODGAP-1.md:74) also needs completed stories, whose [completion check](/src/forge/story.py:877) reads story and task history. If the fallback is used, the board cannot clear a part named by a completed story.  
    Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)
