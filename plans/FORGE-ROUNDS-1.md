# Reads and reviews end after two rounds

3 parts · Risks: none one-way · New moving parts: none

## What changes for you

- A code review runs at most two rounds. A cold read of a plan runs at most two rounds. Forge
  never starts a third round by itself.
- After round two, open findings that are not P0 go to Known issues as follow-ups. The change goes
  on to merge, and the plan goes on to approval. You are not asked about them.
- Forge stops and asks you only when a P0 is still open after round two. A P0 is a security hole,
  data loss or a broken main path. You choose one more round, a split, or accept.
- Round two checks only that round one's findings are fixed. On the new lines, it looks only for a
  P0. It raises no new finding on lines that round one saw, so a reviewer must say everything in
  round one.
- A finding blocks only when it names a case that happens in normal use. A rare case becomes a
  follow-up. A worker can decline a finding as "not worth the code" with a reason, and later
  rounds do not raise it again.
- Insights shows, per release, how many code review follow-ups later turned into real bugs. If few
  do, the reviewer is too strict. If many do, the worker or the tests need a fix.
- Forge's own code gets smaller: one round count replaces the three-round stop rules in close,
  land and the cold read.

## Why

On 20 October 2026 the owner set a limit of two rounds. Findings after round two are almost always
rare edge cases that do not happen in normal use. Workers fix each one with more guard code, so
Forge's code grows with each round and gets harder to change later. Today a review stops only
after three blocked rounds, and then only when several extra conditions hold, and a cold read
works the same way. Those conditions are themselves complex code.

## Done when

1. **A code review runs at most two rounds; after round two, open findings that are not P0 become follow-ups in Known issues and the change goes on to merge.**
2. **A cold read runs at most two rounds; after round two, open notes that are not P0 become follow-ups and the plan goes on to approval.**
3. **When a P0 is still open after round two, Forge stops and asks the owner to choose one more round, a split, or accept, and never starts a third round by itself.**
4. **Round two checks only that round one's findings are fixed and looks at new lines only for a P0; it raises no new finding on lines that round one saw.**
5. **A finding blocks only when it names a case that happens in normal use; a worker can decline a finding with a reason, and later rounds do not raise it again.**
6. **Insights shows, per release, how many code review follow-ups from round-two leftovers and declined findings later turned into real bugs.**

## New and existing repos

- **New repos** (init or adoption): the two-round limit, the round-two scope and the finding bar
  apply from their first read and review. The reviewer and reader instructions and the worker
  brief arrive with setup.
- **Existing repos** (on upgrade to this release): the same rules apply from the next read or
  review round, after `forge sync`. An item already past round two when the repo upgrades gets the
  new rule at its next round: non-P0 findings become follow-ups, and an open P0 asks the owner.
  Tested on the adopted earlier-release fixture moved to this release.

## Risks

Risks: none one-way. Each part reverts with its pull request. A real problem left as a follow-up
stays visible in Known issues, and Insights counts the ones that turned into bugs.

Trade-off: a real but uncommon bug can now merge as a follow-up where today a third round could
catch it. The Insights count shows how often that happens.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Every Done-when item has exactly one test function, `test_<n>_...`, in one new file,
`tests/test_two_round_limit.py`, which starts with `STORY = "FORGE-ROUNDS-1"`. Each test runs the
forge command and never imports forge. Each runs on a repo made by `forge init` and on
`tests/fixtures/adopted-v1.2.2` moved to this release: `client_item(env, tmp_path, previous)` in
`tests/test_close_holds_after_three_blocked_reviews.py` does both for close and land, and test_1 of
`tests/test_reads_wait_for_a_loop_choice.py` shows the same for a story and a spec read. Only the
existing stubs are faked: Autoreview and GitHub (`tests/test_close.py`), the Codex worker
(`tests/test_land.py`) and the reader (`claude_payload` and `say` from
`tests/test_readloop_gates.py`).

**Words this story pins.**
- A review finding is a P0 when `score.holds(finding, "P0")` is true: its bar is `block` (Harm 4 or
  5, or Gain 5), or, with no scores, its priority is P0. A read note is a P0 when its bar is
  `block`. A read note with no score line is never a P0.
- The round of a review is the item's count of `review` steps, as close counts it today. The round
  of a read is the notes' `round`. "After round two" means a round whose number is 2 or more. No new
  counter is stored.
- Two reasons are fixed strings in `src/forge/score.py`, because Insights matches them:
  `ROUND_TWO = "Left open after round two"` (REVIEW adds it) and
  `DECLINED = "Declined as not worth the code: "`, followed by the worker's reason (READ adds it).
  A finding marked with either reason is a follow-up: its `follow_up` field holds the reason.
  `score.remember` stores that text as the known entry's `reason` when no dismissal gives one.
  Then the Known issues row shows it.

### Done-when details

1. Review. In `review._bound_findings`, from round 2 (the review has a `previous` commit), every
   finding that holds the work but is not a P0 gets `follow_up = score.ROUND_TWO`. The serious
   findings left after that are P0s only. Close then lists the rest under "Follow-ups" in the pull
   request, and records them in the item's `known` list. It goes on to the checks and to Ready as
   for a clean review. Normal-use cases: a round-one finding not fixed in round two; a round-one
   finding fixed but a new finding at the bar on a changed line; an unscored P1 from a saved
   review; a review that was clean in round one and finds a P1 in round two after more commits. All
   of these become follow-ups. An item already past round two on upgrade gets the rule at its next
   close. Test: `test_1_a_review_ends_after_round_two_and_leftovers_become_known_issues`. Round 1
   returns a P1 at the bar (Gain 4, Work 1, Harm 2) and close refuses. The worker commit changes
   its line. Round 2 returns that finding again, plus a new P1 at the bar on the changed line.
   Close exits 0 with "Ready". Autoreview ran exactly twice. The pull request body lists both
   findings under "Follow-ups:". `forge board --json` lists both in `known_issues` with the reason
   "Left open after round two".
2. Read. This item holds the read side of items 3 and 4: the P0 read stop and round two's read
   prompt. READ builds them and `test_2` proves them. Items 3 and 4 below are the review side.
   In `story.read_result`, when a round of 2 or more does not pass and no note in it is a
   P0, Forge writes `Disposition: keep - Left open after round two` under each held note of that
   round that has no disposition. It records `loop_choice: accept` and
   `loop_reason: Round two left no P0; its notes are follow-ups`, so `story.passed` holds. It
   commits the round as a passing round. It prints
   `Round <n> of the cold read of <doc> passed with follow-ups.` and `Next: forge next`, which
   moves to approval (a story) or confirmation (a spec). A round of 2 or more with a P0 refuses with
   `read_loop`, as item 3 says. One rule replaces the streak: `story.stopped(record, findings)` is
   true when the latest round is 2 or more, did not pass, has no `loop_choice`, and holds a P0
   note. `read`'s start refusal, `--resolve` and `forge next` use it, in place of
   `_blocked_reads`. Round two's prompt: the `round` part of `cold-read.md` asks only whether each
   earlier finding is closed, and says to block on the diff only for a P0. Round two always uses
   it, for stories and specs alike. The `look` and `cap` parts go, and so does the
   "from round 3 on" sentence in `edit`. Normal-use cases: a story and a spec; a note that the
   coordinator disposed as cut in round 1 and that comes back changed in round 2; a doc that
   passed round 1, gets an edit above `## For the builders` and has a held note in round 2. Test:
   `test_2_a_cold_read_ends_after_round_two`, for a story and a spec on both repos. Round 1 has a
   held note, which gets a cut disposition. Round 2 has a new held note (Gain 4, Work 1, Harm 2).
   The read exits 0. The notes show the keep line. `forge next` names approval (or confirmation).
   The round 2 prompt has the P0-only sentence and no `look` text. In a second walk, round 2 has a
   Harm 5 note. The read exits 1 with the question, and a third `forge read` refuses until a
   choice is recorded.
3. Stop. In close, a review of round 2 or more that still has a serious finding (so a P0) records
   the stop that the deleted three-round code recorded: `stop = {"file", "at", "wait_id"}`,
   `status = "hotspot"`, an owner wait start with reason `review loop`, and the `hotspot` refusal
   with `review.stop_question`. The refusal's text names the P0 and says Forge stopped. Its next
   step is `forge close <item> --resolve <more|split|accept> --reason "<human's choice>"`.
   `review.question` asks "One more round, split or accept?", with one bullet each. For "one more
   round", the worker fixes them, the review runs once more, and Forge asks again only if a P0 is
   still open. `--resolve` gains `more` for a review-loop stop. It records the choice like `same`
   does and prints `Next: forge work <item>`. That round's close is round 3, and the same rule
   applies to it. `forge land` runs at most one fix round, the one between review rounds one and
   two. A second refusal that would need a worker (findings, failing tests, failing checks) stops
   land with `Stopped after one fix round: <item> still has <what>.` A stop question still exits
   with status 3. `forge next` repeats the question, as it does today. Normal-use cases: land from
   start to the stop; tests still failing after the one fix round; a choice of `more` followed by a
   clean round 3. The 30-minute default answer is left as it is: `nextstep.default_due` never fires
   while a finding has Harm 3 or more open, so it never answers a scored P0 stop. Test:
   `test_3_an_open_p0_after_round_two_asks_the_owner_and_land_starts_no_third_round`, with the
   parameter `case` in ("p0", "tests"). p0: `forge land` runs round 1 (a P1 at the bar), one worker
   round and round 2 (a Harm 5 finding on a changed line). It exits 3 with the question and the
   `--resolve <more|split|accept>` step. Autoreview ran twice and the worker once. Then
   `--resolve more`, a worker commit and `forge land` give a clean round 3 and "Ready". tests: the
   tests fail in round 1 and in round 2, and land stops with the "one fix round" line. Autoreview
   ran twice.
4. Round two's scope. The `repair-review` block of `review.md` says that this round checks each
   previous finding, fixed or not fixed. On the lines changed since that review, it raises only a
   P0. It raises nothing on lines that the previous review saw. `review._bound_findings` keeps its
   rule that a new finding on unchanged lines is a follow-up ("New finding on lines unchanged since
   the previous review."). The rule now covers Security and Data loss findings too, as Done when 4
   says, so the `FLOORS[:2]` exemption goes. A new non-P0 on a changed line is already a follow-up
   by item 1. The review base stays the previous review's commit, as today. Normal-use cases: a P0
   on a changed line still blocks; a P0 on a line round one saw becomes a follow-up; a merge of
   main between the rounds keeps the base rule that exists today. Test:
   `test_4_round_two_reviews_only_round_one_findings_and_p0s_on_new_lines`. Round 1 returns a P1.
   The worker changes line 1. Round 2 returns a Harm 5 finding on unchanged line 3 under
   `Raise: Security`. Close exits 0 and lists it under "Follow-ups:". Round 2's prompt names the
   round 1 finding and the P0-only sentence, and `--base` is the round 1 commit. A second
   parameter returns a Harm 5 finding on line 1, and close refuses with the stop question.
5. The bar and declines. The reviewer and reader templates (`review.md` "What blocks the merge" and
   "How to report", `cold-read.md` first round and `round`) ask for one line,
   `Case: normal use - <the scenario>` or `Case: rare - <the scenario>`, in each finding or note
   that would block. A security hole or data loss that any user can reach is normal use. In
   `score.py`, a finding or note with a `Case: rare` line never holds: `holds` and `note_holds`
   return False for it, and `remember` gives it the outcome `follow-up`. A finding without a
   `Case:` line is judged as today, so saved reviews keep their outcome. Decline: the worker brief
   (`brief.md` "Fix round") tells the worker that, for a finding it judges not worth the code, it
   changes nothing and writes `Declined: <title> (<file>): not worth the code - <reason>` in the
   commit body, with the title and file exactly as the finding gives them. `review._rulings` also
   passes `Declined:` lines to the reviewer. `review._bound_findings` marks each finding whose
   `score.identity(file, title)` matches a `Declined:` line in the branch's commits with
   `follow_up = score.DECLINED + reason`, unless the finding is a P0, which stays open. Later
   rounds then carry it as settled, through `_settled` and the carried dismissals that exist today,
   so they never block on it again. For reads, the coordinator's existing
   `Disposition: keep <reason>` is the decline. The notes header in `cold-read.md` now allows "not
   worth the change" as a keep reason. Normal-use cases: a rare-case finding at Harm 4; a declined
   P1 that round 2 re-raises with the same title; a declined P0, which stays open; a rare-case read
   note. Test: `test_5_rare_cases_and_declined_findings_do_not_block`, with the parameter `case` in
   ("rare finding", "declined", "declined p0", "rare note"). A rare finding at Harm 4 in round 1:
   close exits 0 with it under "Follow-ups:". declined: the round 1 P1, a commit with the
   `Declined:` line, and a round 2 re-raise: close exits 0, the known row's reason starts with
   "Declined as not worth the code:", and the round 2 prompt shows the `Declined:` line. declined
   p0: the same with Harm 5, and close stops. A rare note: `forge read` round 1 with a
   `Case: rare` note at Harm 4 passes.
6. Insights. `known_issues.collect` gives each follow-up row two more fields. `source` is
   `"round two"` when its reason is `score.ROUND_TWO`, `"declined"` when its reason starts with
   `score.DECLINED`, and null otherwise. `became_bug` is the id of the first later change that
   meets the rule in Notes, or null. The Insights page adds one panel, "Follow-ups that became
   bugs", which is a table with one row per release, newest first, and "Next release" first. The
   columns are: Release, From round two, Declined, Became bugs. A row's release is the
   `released_in` of the follow-up's item from FORGE-BOARD-3's release facts. Null is the next
   release. Rows count only follow-ups whose `source` is set. Normal-use cases: no follow-ups yet
   (one plain sentence that says what will show here); `known_issues` unknown (says unknown, as
   Releases does); a follow-up that a fix made on purpose for it (excluded). Test:
   `test_6_insights_counts_follow_ups_that_became_bugs_per_release`, in
   `tests/test_two_round_limit.py`. It imports `team`, `landed`, `browse` and the page prelude from
   `tests/test_board_releases_insights.py` (real Chrome, new and adopted clients). Fix A is
   released in `v1.0.0`, with a round-two follow-up in `total()` of `src/basket.py` and a declined
   follow-up in `src/page.py`. Fix B starts after A and has a `fixed in round 2` entry in `total()`
   of `src/basket.py`. Fix C's why names A's declined title and has a blocking entry in
   `src/page.py`. The page shows the row `v1.0.0 · 1 · 1 · 1`, and the JSON row for the
   `total()` follow-up has `became_bug` set to B. The existing keyboard and axe test,
   `test_17`, covers the new panel without change.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| REVIEW | Two review rounds | Round-two leftovers become follow-ups. A P0 after round two stops with "one more round, split or accept". Land runs one fix round. Round two raises only a P0 on new lines. The three-round, same-file and area stops, settled areas, loop advice and the board's "looping" entry are deleted. The guide, the brief's review lines and the README match. | 1, 3, 4 | `src/forge/close.py`, `src/forge/review.py`, `src/forge/score.py`, `src/forge/land.py`, `src/forge/nextstep.py`, `src/forge/board_facts.py`, `src/forge/worker.py`, `src/forge/templates/review.md`, `src/forge/templates/skill.md`, `src/forge/templates/brief.md`, `README.md`, `docs/commands.md`, `.claude/skills/forge/`, `.codex/skills/forge/` (the last three regenerated by `forge sync`) | `tests/test_two_round_limit.py` (`test_1`, `test_3`, `test_4`), plus the review-side changes listed in Notes | | no | |
| READ | Two read rounds and the bar | Round-two read leftovers kept as follow-ups. A P0 read stop with more, split or accept. Round two's read prompt. `Case: rare` never blocks. Worker declines. The read streak, `read_stops` and the read loop advice are deleted. The guide and brief read lines match. | 2, 5 | `src/forge/story.py`, `src/forge/score.py`, `src/forge/review.py`, `src/forge/nextstep.py`, `src/forge/worker.py`, `src/forge/templates/cold-read.md`, `src/forge/templates/review.md`, `src/forge/templates/brief.md`, `src/forge/templates/skill.md`, `README.md`, `docs/commands.md`, `.claude/skills/forge/`, `.codex/skills/forge/` | `tests/test_two_round_limit.py` (`test_2`, `test_5`), plus the read-side changes listed in Notes | REVIEW | no | |
| INSIGHTS | Follow-ups that became bugs | `source` and `became_bug` on Known issues rows. The Insights panel per release. One line in the guide's board JSON paragraph. | 6 | `src/forge/known_issues.py`, `src/forge/board_app/insights.js`, `src/forge/board_app/pages.css`, `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/` | `tests/test_two_round_limit.py` (`test_6`) | READ | yes | |

New moving parts: none

## Notes

- **The rule for "turned into a real bug".** A round-two or declined follow-up became a real bug
  when a later change on the default branch had a review finding in the same file and the same
  area (`review.area`: the Python function, else the file) that held its work. "Held its work"
  means its known entry's outcome is `fixed in round <n>` or `accepted`. A later change is an item
  whose first step comes after the follow-up's item's last step. A change whose why names the
  follow-up's title never counts. That covers a split, a default follow-up fix, and any fix made
  for it on purpose. Blind spots: a bug found outside a Forge review (a user report, CI alone, a
  change merged around Forge, a review that missed it) is not counted, so the count is a floor. A
  different bug in a busy function can count, so a busy area can over-count. Items without a
  `known` list on the default branch (before the known list existed) are never the later change.
  Read follow-ups are plan notes with no file, so Insights does not count them.
- **Deleted.**
  - close.py:
    - the choice-round count and the stop before the review (lines 287-305);
    - the crowded, `loop_stops` and same-file branch, with `flagged` (lines 389-407);
    - both `loop_advice` prints;
    - settled areas (lines 138-139, 335-341, `_settled_areas`);
    - findings as a reason for `stuck_round`. The stuck stop keeps "close's tests failing". Two
      rounds now end a finding loop, and a findings key would stop the worker round that a `more`
      choice buys.
  - review.py:
    - `blocked_rounds` and `loop_advice` (REVIEW);
    - `owner_advice` (READ, with `nextstep._read_advice`);
    - the area line in `stop_question`;
    - the `FLOORS[:2]` exemption.
  - score.py: `loop_stops`, `crowded` and `move` (REVIEW); `read_stops` (READ).
  - land.py: `ROUNDS` and the block that recorded a review-loop stop after three fix rounds.
    `NEEDS_CHOICE` stays: exit status 3 is the documented "needs a choice" signal for land and
    land --all.
  - nextstep.py: the loop-advice lines in `_item` (REVIEW); `_read_advice` and the
    `_blocked_reads` checks (READ).
  - board_facts.py: the `looping` entry in `blocked`.
  - story.py:
    - `_blocked_reads` and `_streak`;
    - `blocked_rounds` in the read result and the `RECORD` fields;
    - the round-3 cap selection;
    - `read_stops` at the end of `read_result`;
    - `narrow` from read's `--resolve` choices, which become `accept|more|split`.
  - worker.py: the `REVIEW_LOOP` text is rewritten shorter, the review half by REVIEW and the read
    half by READ. The `stop["area"]` note goes.
  - skill.md, brief.md and README.md: the three-round and fourth-review text, the same-area stop,
    the "from the second blocked round, ask the owner" paragraph and `looping`. Each is replaced
    by the two-round rule in a few lines.
- **Expected net lines.**
  - close.py about -45. It must end below its 1,200 ceiling, and it is at 1,200 now.
  - story.py about -15. It must also end below 1,200.
  - review.py about -40.
  - score.py about -35.
  - land.py about -12.
  - nextstep.py about -15.
  - board_facts.py about -5.
  - known_issues.py about +25.
  - insights.js about +25.
  - The whole story removes more process than it adds.
- **Existing tests.**
  - REVIEW:
    - Deletes test_1, test_2 and test_3 of `tests/test_close_holds_after_three_blocked_reviews.py`,
      and keeps its `client_item`, `PATHS` and `QUESTION_RULE`, which nine files import.
    - Deletes test_2 and test_3 of `tests/test_owner_question_after_blocked_rounds.py`, and the
      review phases of its test_1.
    - Deletes test_1 and test_3 of `tests/test_reviews_converge_on_changed_lines.py` (test_4
      replaces them).
    - Deletes test_4 of `tests/test_score_bar.py`.
    - Deletes test_2 of `tests/test_land.py` (test_3 replaces it).
    - Changes test_1 of `tests/test_land.py`: it drops the crowded and missing-rule cases and gets
      the new round lines.
    - Changes `tests/test_running_commands_follow_changed_forge_pin.py` test_2 to one fix round.
    - Changes test_4 of `tests/test_queue_land_all.py` to the `more` step.
    - Changes `tests/test_land_returns_the_owner_question.py`,
      `tests/test_land_records_review_loop_choice.py`,
      `tests/test_close_waits_for_review_loop_choice.py` and
      `tests/test_review_loop_records_each_stop_choice.py`. Each builds its stop the new way (a P0
      in round 2) and records `more` where it recorded `narrow`.
    - Changes test_3 of `tests/test_board_blocked.py`: it drops the looping case.
    - Changes test_1 of `tests/test_stuck_worker_asks.py`: it drops the "finding" and "finding then
      test" cases.
    - Runs `tests/test_item_time_history.py` and `tests/test_owner_stops_survive_main_merges.py`,
      and adapts only how they build their stop.
  - READ:
    - Deletes `tests/test_reads_wait_for_a_loop_choice.py` test_1 and test_2, keeps its test_4
      with the new brief text, and deletes the rest of
      `tests/test_owner_question_after_blocked_rounds.py`.
    - Deletes test_3 of `tests/test_spec_reads_keep_full_scope.py`. Specs now get the round-two
      scope too.
    - Changes test_1 of `tests/test_fix_plan_reads_capped.py` to the round-two sentence.
    - Changes the walks in test_1 of `tests/test_readloop_rounds.py`. A held round of 2 or more is
      now kept as follow-ups, so `_starts_fresh` loses its held round and its `--resolve narrow`,
      and keeps its fresh, continued, failed and discarded checks.
    - `tests/test_worker_and_reader_chats_survive_rounds.py` needs no change. Its test_5 already
      allows an empty `blocked_rounds` field.
  - `tests/test_stop_default_answer.py` stays as it is.
- **Choices this plan made.**
  - Done when 4 is followed as written. A new finding on a line round one saw is a follow-up even
    under Security or Data loss, which still block today.
  - `stop_default` and the 30-minute default stay. They never answer a scored P0 stop, and
    removing a `forge.toml` key needs its own migration.
  - REVIEW changes `review.question`'s wording, which the read stop shares. Until READ merges, a
    read stop's question offers "one more round" while `forge read --resolve` still takes
    `narrow`. Both parts ship in one release.
- **Not to do.**
  - No new command, option or `forge.toml` setting beyond the `more` choice.
  - No stored round counter.
  - No `--dismiss` for declines: only the human dismisses.
  - Do not touch spotted hotspots ("keeps breaking" in `forge next`), which are not a round stop.
- INSIGHTS starts once FORGE-BOARD-3's RELEASES part has merged: `released_in` on each row comes
  from it. Until then the board has no release facts, and Insights would only show "unknown".
- No client repo is named anywhere in this story's code, tests, texts or commits.
