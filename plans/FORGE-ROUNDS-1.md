# Reads and reviews end after two rounds

3 parts · Risks: none one-way · New moving parts: none

## What changes for you

- A code review runs at most two rounds. A cold read of a plan runs at most two rounds. Forge
  never starts a third round by itself.
- After round two, open findings that are not P0 go to Known issues as follow-ups. The change goes
  on to merge, and the plan goes on to approval. You are not asked about them.
- Forge stops and asks you only when a P0 is still open after round two. A P0 is a security hole,
  data loss or a broken main path. You choose one more round, a split, or accept.
- The 30-minute default answer to a stop goes away, because the only stop left is an open P0, and
  a P0 always waits for you. Its setting in `forge.toml` still loads but does nothing.
- Round two checks that round one's findings are fixed. It raises only new P0s that happen in
  normal use, so a reviewer must say everything else in round one. A round-one fix that breaks the
  main path counts as a P0.
- A finding blocks only when it names a case that happens in normal use. A rare case becomes a
  follow-up. A worker can decline a finding as "not worth the code" with a reason, and later
  rounds do not raise it again.
- A question that a review rule of the repo or a recorded owner decision already settles is not
  raised again.
- On a change that people use directly, the worker runs the real flow once before review round two
  and notes what it ran and what it saw. Forge asks for this but refuses no work without it.
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
4. **Round two checks that round one's findings are fixed and raises only new P0s that happen in normal use.**
5. **A finding blocks only when it names a case that happens in normal use; a worker can decline a finding with a reason, and later rounds do not raise it again.**
6. **On a user-facing change, the worker brief asks for one live run of the real flow before review round two, and the worker's report records what was run and what was seen; Forge refuses no work without it.**

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
stays visible in Known issues.

Trade-off: a real but uncommon bug can now merge as a follow-up where today a third round could
catch it. Each one stays listed in Known issues.

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
(`tests/test_land.py`), the Claude worker (`install_claude` and `calls` in `tests/test_worker.py`)
and the reader (`claude_payload` and `say` from `tests/test_readloop_gates.py`).

**Words this story pins.**
- A review finding is a P0 when `score.holds(finding, "P0")` is true: its bar is `block` (Harm 4 or
  5, or Gain 5), or, with no scores, its priority is P0. A read note is a P0 when its bar is
  `block`. A read note with no score line is never a P0. A finding or note with a `Case: rare` line
  never holds, so it is never a P0 (item 5).
- The round of a review is the item's count of `review` steps, as close counts it today. The round
  of a read is the notes' `round`. "After round two" means a round whose number is 2 or more. No new
  counter is stored.
- REVIEW adds two reasons to `src/forge/score.py` as fixed strings:
  - `ROUND_TWO = "Left open after round two"`;
  - `DECLINED = "Declined as not worth the code: "`, followed by the worker's reason.

  A finding marked with either reason is a follow-up: its `follow_up` field holds the reason.
  `score.remember` stores that text as the known entry's `reason` when no dismissal gives one.
  Then the Known issues row shows it.

### Done-when details

1. Review (REVIEW). In `review._bound_findings`, from round 2 (the review has a `previous` commit),
   every finding that holds the work but is not a P0 gets `follow_up = score.ROUND_TWO`. This
   replaces the function's unchanged-lines check (the per-file `git diff` hunks). It also replaces
   the `FLOORS[:2]` exemption. Both go. The `Not done` rule stays. The serious findings left are
   P0s only. Close lists the rest under "Follow-ups" in the pull request and records them in the
   item's `known` list. It goes on to the checks and to Ready as for a clean review. Normal-use
   cases: a round-one finding not fixed in round two; a new finding at the bar in round two, on a
   changed or an unchanged line; an unscored P1 from a saved review; a review that was clean in
   round one and finds a P1 in round two after more commits. All of these become follow-ups. An
   item already past round two on upgrade gets the rule at its next close. Test:
   `test_1_a_review_ends_after_round_two_and_leftovers_become_known_issues`. Round 1 returns a P1
   at the bar (Gain 4, Work 1, Harm 2) and close refuses. The worker commit changes its line.
   Round 2 returns that finding again, plus a new P1 at the bar. Close exits 0 with "Ready".
   Autoreview ran exactly twice. The pull request body lists both findings under "Follow-ups:".
   `forge board --json` lists both in `known_issues` with the reason "Left open after round two".
2. Read (READ). This item holds the read side of items 3 and 4: the P0 read stop and round two's
   read prompt. READ builds them and `test_2` proves them. Items 3 and 4 below are the review side.
   - In `story.read_result`, a round of 2 or more can fail with no P0 note in it. Then Forge writes
     `Disposition: keep - Left open after round two` under each held note of that round that has no
     disposition. It records `loop_choice: accept` and
     `loop_reason: Round two left no P0; its notes are follow-ups`, so `story.passed` holds. It
     commits the round as a passing round. It prints
     `Round <n> of the cold read of <doc> passed with follow-ups.` and `Next: forge next`, which
     moves to approval (a story) or confirmation (a spec).
   - A round of 2 or more with a P0 refuses with `read_loop`. The refusal says the round number and
     that a P0 note is still open. It asks `review.question` as STOP words it.
   - `forge read --resolve` takes `accept|more|split`. `more` records `loop_choice: more` and
     prints `Next: forge read <target>`. The next round is round 3, and the same rule applies to
     it.
   - One rule replaces the streak: `story.stopped(record, findings)` is true when the latest round
     is 2 or more, did not pass, has no `loop_choice`, and holds a P0 note. `read`'s start refusal,
     `--resolve` and `forge next` use it, in place of `_blocked_reads`.
   - Round two's prompt: the `round` part of `cold-read.md` asks only whether each earlier finding
     is closed. It blocks on anything new only for a P0 that happens in normal use. Round two always
     uses it, for stories and specs alike. The `look` and `cap` parts go, and so does the
     "from round 3 on" sentence in `edit`.
   - Normal-use cases: a story and a spec; a note that the coordinator disposed as cut in round 1
     and that comes back changed in round 2; a doc that passed round 1, gets an edit above
     `## For the builders` and has a held note in round 2.
   - Test: `test_2_a_cold_read_ends_after_round_two`, for a story and a spec on both repos. Round 1
     has a held note, which gets a cut disposition. Round 2 has a new held note (Gain 4, Work 1,
     Harm 2). The read exits 0. The notes show the keep line. `forge next` names approval (or
     confirmation). The round 2 prompt has the P0-only sentence and no `look` text. In a second
     walk, round 2 has a Harm 5 note. The read exits 1 with the question, and a third `forge read`
     refuses until `--resolve more` is recorded. Then it runs.
3. Stop (STOP).
   - In close, a review of round 2 or more that still has a serious finding (a P0, by item 1)
     records the stop that the deleted three-round code recorded: `stop = {"file", "at", "wait_id"}`,
     `status = "hotspot"`, an owner wait start with reason `review loop`, and the `hotspot` refusal
     with `review.stop_question`. The refusal's text names the P0 and says Forge stopped. Its next
     step is `forge close <item> --resolve <more|split|accept> --reason "<human's choice>"`.
   - `review.question` asks "One more round, split or accept?", with one bullet each. For "one more
     round", the worker fixes them, the review runs once more, and Forge asks again only if a P0 is
     still open.
   - `--resolve` gains `more` for a review-loop stop. It records the choice like `same` does and
     prints `Next: forge work <item>`. That round's close is round 3, and the same rule applies to
     it.
   - `forge land` runs at most one fix round, the one between review rounds one and two. That count
     carries across session handbacks through `state["land"]["rounds"]`, as today
     (`land.py:59`, `worker.py:236`). A second refusal that would need a worker (findings, failing
     tests, failing checks) stops land with `Stopped after one fix round: <item> still has <what>.`
   - A stop question still exits with status 3. `forge next` repeats the question, as it does today.
   - The 30-minute default answer goes: `close._answer_by_default`, its call in
     `close.check_stop`, `nextstep.default_due` and its line in `nextstep._item`, and the
     default-narrow note in `worker.py`. With every review-loop stop now holding a P0, the default
     answer has nothing left to answer. A stop recorded by an earlier release waits for the owner,
     as it does today when the setting is off. `stop_default` stays in `repo.KEYS` and `CHOICES`
     with a `ponytail:` comment, only so that an existing `forge.toml` that sets it still loads.
     The guide and README stop naming it.
   - Normal-use cases: land from start to the stop; tests still failing after the one fix round;
     land run from a Claude Code session, where each round is handed to a subagent; a choice of
     `more` followed by a clean round 3; a P0 stop left unanswered for over 30 minutes.
   - Test: `test_3_an_open_p0_after_round_two_asks_the_owner_and_land_starts_no_third_round`, with
     the parameter `case` in ("p0", "tests", "session").
     - p0: `forge land` runs round 1 (a P1 at the bar), one worker round and round 2 (a Harm 5
       finding). It exits 3 with the question and the `--resolve <more|split|accept>` step.
       Autoreview ran twice and the worker once. With the event clock moved 31 minutes on,
       `forge close` still refuses with the question and records no choice. Then `--resolve more`,
       a worker commit and `forge land` give a clean round 3 and "Ready".
     - tests: the tests fail in round 1 and in round 2, and land stops with the "one fix round"
       line. Autoreview ran twice.
     - session: the same as tests, run through `Session` from `tests/test_tools_session_hold.py`,
       as `_session_rounds_count_across_reruns` in `tests/test_land.py` does today. The first land
       hands out the one fix round and exits 0. After the handback, the next land closes round 2
       and stops with the "one fix round" line, with no worker run.
4. Round two's scope (REVIEW). The `repair-review` block of `review.md` says that this round checks
   each previous finding, fixed or not fixed. It raises a new finding only when it is a P0 that
   happens in normal use, on any line. A round-one fix that breaks the main path is scored as a P0
   (Harm 4 or more). Item 1's marking enforces the rest: a below-P0 finding in round two is a
   follow-up. The review base stays the previous review's commit, as today. Normal-use cases: a P0
   on a line round one saw blocks; a P1 on a line round one saw is a follow-up; a fix that broke
   the main path, reported as a P0, blocks. Test:
   `test_4_round_two_reviews_only_round_one_findings_and_p0s_that_happen_in_normal_use`, with the
   parameter `case` in ("p0", "p1"). Round 1 returns a P1. The worker changes line 1. Round 2
   returns a finding on unchanged line 3. For p0 it has Harm 5, and close exits 1 and names it
   (this holds before and after STOP). For p1 it is a P1 at the bar, and close exits 0 with it
   under "Follow-ups:". Round 2's prompt names the round 1 finding, the P0-only sentence and the
   main-path sentence, and `--base` is the round 1 commit.
5. The bar and declines (REVIEW).
   - The reviewer and reader templates (`review.md` "What blocks the merge" and "How to report";
     `cold-read.md` first round and `round`) ask for one line in each finding or note that would
     block: `Case: normal use - <the scenario>` or `Case: rare - <the scenario>`. A security hole
     or data loss that any user can reach is normal use.
   - Both templates also say not to raise a finding that this repo's Review rules or a recorded
     owner decision (a decision in `docs/decisions/`, a `Decided:` line, a `Ruling:` line)
     already settles.
   - In `score.py`, a finding or note with a `Case: rare` line never holds: `holds` and
     `note_holds` return False for it, and `remember` gives it the outcome `follow-up`. A finding
     with no `Case:` line is judged as today, so saved reviews keep their outcome.
   - Decline: the worker brief (`brief.md` "Fix round") says what to do with a finding the worker
     judges not worth the code. The worker changes nothing for it and writes
     `Declined: <title> (<file>): not worth the code - <reason>` in a commit body, with the title
     and file exactly as the finding gives them. A commit with no file change is fine.
   - Every `forge close` applies declines, both to a new review and to a reused one. A decline with
     no code change makes close reuse the review (`close.py:263`; fingerprints omit commit
     messages, `review.py:146`). A new `review.declines(top, base, result) -> bool` marks each
     finding whose `score.identity(file, title)` matches a `Declined:` line in the branch's commits
     with `follow_up = score.DECLINED + reason`. A P0 stays open. Close calls it just before
     `serious = review.blocking(result)`. When it marks anything, close sets `refreshed`, so the
     marked result is saved, remembered and published.
   - `review._rulings` passes `Declined:` lines to the reviewer too. The decline line stays in the
     branch, so later rounds carry the finding as settled (through `_settled` and the carried
     dismissals that exist today) and never block on it again.
   - For reads, the coordinator's existing `Disposition: keep <reason>` is the decline. The notes
     header in `cold-read.md` now allows "not worth the change" as a keep reason.
   - Normal-use cases: a rare-case finding at Harm 4; a declined P1 with no code change; a declined
     P1 that a later round re-raises with the same title; a declined P0, which stays open; a
     rare-case read note.
   - Test: `test_5_rare_cases_and_declined_findings_do_not_block`, with the parameter `case` in
     ("rare finding", "declined", "declined p0", "rare note").
     - rare finding: a Harm 4 finding with `Case: rare` in round 1. Close exits 0 with it under
       "Follow-ups:". The review prompt has the Review-rules-and-decisions sentence.
     - declined: round 1 returns a P1 and close refuses. The worker adds an empty commit (`git
       commit --allow-empty`) with the `Declined:` line. The next `forge close` makes no new
       Autoreview call, exits 0 with "Ready", and the known row's reason starts with "Declined as
       not worth the code:". After a code commit, round 2 re-raises the same title. Close still
       exits 0, and the round 2 prompt shows the `Declined:` line.
     - declined p0: the same with a Harm 5 finding. Close still refuses.
     - rare note: `forge read` round 1 with a `Case: rare` note at Harm 4 passes, and the read
       prompt has the same sentence.
6. Live run (STOP).
   - `brief.md`'s `user-facing` block asks, before review round two, for one run of the real flow.
     The worker starts the app, page or command for real (not tests or stubs) and uses it as the
     user would. Then it adds a line `Live run: <what you ran> - <what you saw>` to its
     `Functional check:` paragraph. Close already copies that paragraph into the pull request and
     the review prompt (`review.functional_check`), so the record lives in git and the pull
     request. Forge checks nothing and refuses nothing for it.
   - `worker.py` turns the `user-facing` block on for a task whose row says User-facing yes, as
     today, and also for a fix whose kind is `ui`. That is one condition. The shortened brief for a
     continued worker (`worker.py` lines 536-561) adds the same live-run sentence under the same
     condition, so a worker that started before the upgrade gets it in its fix round.
   - Normal-use cases: a user-facing task's build round and fix round; a `ui` fix; a backend fix,
     whose brief has no live-run line; a close on a commit with no `Live run:` line.
   - Test: `test_6_a_user_facing_change_asks_for_one_live_run_and_refuses_nothing_without_it`.
     - On a new repo, the user-facing `BOARD/PAGE` task from `story` in `tests/test_worker.py`:
       `forge work`'s brief has the live-run sentence.
     - On the adopted fixture, a `ui` fix started after `client_item`'s setup: `forge work`'s brief
       has it. The last commit's `Functional check:` paragraph has no `Live run:` line, and
       `forge close` still runs the review (one Autoreview call) and exits 0.
     - On the adopted fixture, a `ui` fix whose first round ran before the upgrade: its continued
       fix round's brief has the live-run sentence.
     - A backend fix's brief has no live-run sentence.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| REVIEW | Review policy | Round-two leftovers become follow-ups. Round two raises only normal-use P0s, and a broken main path counts as one. `Case: rare` never blocks. Worker declines work on every close. Findings that a Review rule or owner decision settles are not raised. The unchanged-lines check, the security exemption and settled areas are deleted. The brief's review lines and the guide match. | 1, 4, 5 | `src/forge/close.py`, `src/forge/review.py`, `src/forge/score.py`, `src/forge/templates/review.md`, `src/forge/templates/cold-read.md`, `src/forge/templates/brief.md`, `src/forge/templates/skill.md`, `README.md`, `.claude/skills/forge/`, `.codex/skills/forge/` (the last two regenerated by `forge sync`) | `tests/test_two_round_limit.py` (`test_1`, `test_4`, `test_5`), plus REVIEW's changes in Notes | | no | |
| STOP | Owner stop and land budget | An open P0 after round two stops with "one more round, split or accept" (`--resolve more`). Land runs one fix round, also across session handbacks. The 30-minute default answer is deleted. So are the three-round, same-file and area stops, loop advice, `blocked_rounds` and the board's "looping" entry. The brief asks a user-facing change for one live run. The brief's stop lines, the guide and the README match. | 3, 6 | `src/forge/close.py`, `src/forge/review.py`, `src/forge/score.py`, `src/forge/land.py`, `src/forge/nextstep.py`, `src/forge/board_facts.py`, `src/forge/worker.py`, `src/forge/repo.py`, `src/forge/templates/brief.md`, `src/forge/templates/skill.md`, `README.md`, `docs/commands.md`, `.claude/skills/forge/`, `.codex/skills/forge/` | `tests/test_two_round_limit.py` (`test_3`, `test_6`), plus STOP's changes in Notes | REVIEW | no | |
| READ | Two read rounds | Round-two read leftovers are kept as follow-ups. A P0 read stop with more, split or accept. Round two's read prompt. The read streak, `read_stops` and the read loop advice are deleted. The guide and brief read lines match. | 2 | `src/forge/story.py`, `src/forge/score.py`, `src/forge/review.py`, `src/forge/nextstep.py`, `src/forge/worker.py`, `src/forge/templates/cold-read.md`, `src/forge/templates/brief.md`, `src/forge/templates/skill.md`, `README.md`, `docs/commands.md`, `.claude/skills/forge/`, `.codex/skills/forge/` | `tests/test_two_round_limit.py` (`test_2`), plus READ's changes in Notes | STOP | no | |

New moving parts: none

## Notes

- **Order.** The parts run one after another, REVIEW, then STOP, then READ. They share `close.py`,
  `score.py`, `review.py`, `nextstep.py`, `worker.py`'s `REVIEW_LOOP` text, `brief.md` and
  `skill.md`. Between REVIEW and STOP, a P0 at round two still refuses as a blocked review.
  Between STOP and READ, a read stop's question offers "one more round" while `forge read
  --resolve` still takes `narrow`. All three ship in one release.
- **Deleted, by part.**
  - REVIEW:
    - in `review._bound_findings`, the unchanged-lines hunk check and the `FLOORS[:2]`
      exemption;
    - nothing in close.py's settled areas: their last caller is the crowded branch, which STOP
      deletes.
  - STOP, in close.py:
    - the choice-round count and the stop before the review (lines 287-305);
    - the crowded, `loop_stops` and same-file branch, with `flagged` (lines 389-407), and with it
      the settled areas (lines 138-139, 335-341, `_settled_areas`), which only served that stop;
    - both `loop_advice` prints;
    - `_answer_by_default` and its call;
    - findings as a reason for `stuck_round`. The stuck stop keeps "close's tests failing". A
      findings key would stop the worker round that a `more` choice buys.
  - STOP, elsewhere:
    - in review.py, `blocked_rounds`, `loop_advice` and the area line in `stop_question`;
    - in score.py, `loop_stops`, `crowded` and `move`;
    - in land.py, `ROUNDS` and the block that recorded a review-loop stop after three fix rounds.
      `NEEDS_CHOICE` stays: exit status 3 is the documented "needs a choice" signal for land and
      land --all;
    - in nextstep.py, `default_due` and the loop-advice lines in `_item`;
    - in board_facts.py, the `looping` entry in `blocked`;
    - in worker.py, the default-narrow note and the `stop["area"]` note, and the review half of
      `REVIEW_LOOP`, rewritten shorter.
  - READ:
    - in story.py, `_blocked_reads` and `_streak`, `blocked_rounds` in the read result and in
      `RECORD`, the round-3 cap selection, `read_stops` at the end of `read_result`, and `narrow`
      from read's choices;
    - in score.py, `read_stops`;
    - in review.py, `owner_advice`;
    - in nextstep.py, `_read_advice` and the `_blocked_reads` checks;
    - in worker.py, the read half of `REVIEW_LOOP`;
    - in cold-read.md, the `look` and `cap` parts.
  - In skill.md, brief.md and README.md, each part removes its own share of this text:
    - the three-round and fourth-review text;
    - the same-area stop;
    - the 30-minute default and `stop_default`;
    - the "from the second blocked round, ask the owner" paragraph;
    - `looping`.

    Each is replaced by the two-round rule in a few lines.
- **Expected net lines.**
  - close.py about -70 (REVIEW -9, STOP -60). REVIEW must already leave it below the 1,200
    ceiling: it is at 1,200, and settled areas go in the same part as the decline call.
  - story.py about -15 (READ). It must also end below 1,200.
  - review.py about -50.
  - score.py about -40.
  - nextstep.py about -30.
  - land.py about -12.
  - worker.py about -10.
  - board_facts.py about -5.
  - The story removes far more process than it adds.
- **Existing tests.**
  - REVIEW:
    - Deletes test_1 of `tests/test_reviews_converge_on_changed_lines.py` (test_1 and test_4
      replace it), and keeps its test_2.
    - Changes any test that quotes the changed brief or review.md sentences (search the tests for
      "except security" and the old repair-review wording).
  - STOP:
    - Deletes test_1, test_2 and test_3 of `tests/test_close_holds_after_three_blocked_reviews.py`,
      and keeps its `client_item`, `PATHS` and `QUESTION_RULE`, which nine files import.
    - Deletes test_2 and test_3 of `tests/test_owner_question_after_blocked_rounds.py` and the
      review phases of its test_1.
    - Deletes test_3 of `tests/test_reviews_converge_on_changed_lines.py`.
    - Deletes test_4 of `tests/test_score_bar.py`.
    - Deletes `tests/test_stop_default_answer.py`: its rule (the 30-minute default) is deleted, and
      its third-round stop with P1s can no longer exist. Its helpers `follow_ups` and `later` go
      with it: `tests/test_score_bar.py` uses them only in its deleted test_4, so its import line
      goes; `tests/test_score_notes.py` uses them only in the `narrowed` case of its test, which
      needs the deleted timeout, so that case and the import line go.
    - Changes test_2 of `tests/test_land.py`. It drops `_findings_after_three_rounds_ask_a_question`
      and `_default_stop_shows_the_question_and_exits`. It moves `_session_rounds_count_across_reruns`
      into test_3's "session" case. Its other cases expect one fix round.
    - Changes test_1 of `tests/test_land.py`: it drops the crowded and missing-rule cases and gets
      the new round lines.
    - Changes test_2 of `tests/test_running_commands_follow_changed_forge_pin.py` to one fix round.
    - Changes test_4 of `tests/test_queue_land_all.py` to the `more` step.
    - Changes `tests/test_land_returns_the_owner_question.py`,
      `tests/test_land_records_review_loop_choice.py`,
      `tests/test_close_waits_for_review_loop_choice.py` and
      `tests/test_review_loop_records_each_stop_choice.py`. Each builds its stop the new way (a P0
      in round 2) and records `more` where it recorded `narrow`. Their `stop_default = "off"` setup
      can stay, since the key still loads.
    - Changes test_3 of `tests/test_board_blocked.py`: it drops the looping case.
    - Changes test_1 of `tests/test_stuck_worker_asks.py`: it drops the "finding" and "finding then
      test" cases.
    - Runs `tests/test_item_time_history.py` and `tests/test_owner_stops_survive_main_merges.py`,
      and adapts only how they build their stop.
  - READ:
    - Deletes test_1 and test_2 of `tests/test_reads_wait_for_a_loop_choice.py`, and keeps its test_4
      with the new brief text.
    - Deletes the rest of `tests/test_owner_question_after_blocked_rounds.py`.
    - Deletes test_3 of `tests/test_spec_reads_keep_full_scope.py`. Specs now get the round-two
      scope too.
    - Changes test_1 of `tests/test_fix_plan_reads_capped.py` to the round-two sentence.
    - Changes the walks in test_1 of `tests/test_readloop_rounds.py`. A held round of 2 or more is
      now kept as follow-ups, so `_starts_fresh` loses its held round and its `--resolve narrow`,
      and keeps its fresh, continued, failed and discarded checks.
- **Not to do.**
  - No new command, option or `forge.toml` setting beyond the `more` choice.
  - No stored round counter.
  - No `--dismiss` for declines: only the human dismisses.
  - No check or refusal for the live run.
  - Do not touch spotted hotspots ("keeps breaking" in `forge next`): they are not a round stop.
- **Cut from this story (owner, 20 October 2026).** Insights does not count follow-ups that became
  bugs. Once releases are recorded, a later fix may count follow-ups that a later fix names in its
  Why.
- No client repo is named anywhere in this story's code, tests, texts or commits.
