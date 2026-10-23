# Owner decides before open findings drop at the round limit

2 parts · Risks: none one-way · New moving parts: none

## What changes for you

- The round limits stay. A code review of a story part runs two rounds, and a review of a fix
  runs one round. A cold read of a plan, spec or decision runs two rounds.
- At the round limit, an open finding or note that is not P0 stops the item. Forge asks you to
  choose one more round, a split, or accept. Accept puts the findings in Known issues as
  follow-ups. Nothing becomes a follow-up without your answer.
- A P0 is a security hole, data loss or a broken main path. An open P0 never stops the item at
  the limit. The worker keeps fixing it until the review or read is clean.
- When the same P0 is still open after two worker rounds in a row, Forge stops the item and asks
  you. This is the same stop that Forge uses today when the tests fail two rounds in a row. A cold
  read stops when it has P0 notes in two rounds in a row.
- `forge work` refuses an item that waits for your answer. It shows the same question and the
  same next command that close shows.
- The guide, the worker brief and the reviewer and reader instructions state the new rule. The
  next release's notes state it too. New repos get it at init. Existing repos get it on upgrade
  and sync.

## Why

On 21 October 2026 the owner changed what happens at the round limit. Findings that are not P0
can still matter, and the owner wants to decide on them. Today Forge moves them to follow-ups by
itself after the last review round and after round two of a cold read. Today an open P0 at the
limit stops and waits for the owner, but a P0 is serious and the worker must fix it. When a P0
has no limit, a worker that cannot fix it can use tokens without end, so Forge must stop it after
two rounds. Today `forge work` checks only for a stuck worker, so a worker round can start while
a review stop waits for the owner.

## Done when

1. **At the round limit, a review with an open finding that is not P0 stops and asks the owner: one more round, split or accept. Accept puts the findings in Known issues as follow-ups. Until the owner answers, `forge close`, `forge land` and `forge work` show the same question.**
2. **An open P0 in a review never stops for the owner, and the worker keeps fixing it. When the same P0 is still open two rounds in a row, Forge stops with the stuck question, and `forge work` refuses until the owner answers.**
3. **From round two, a cold read with an open note that is not P0 stops and asks the owner: one more round, split or accept. An open P0 note does not stop the read, unless P0 notes are open in two rounds in a row.**
4. **The guide, the worker brief and the reviewer and reader instructions state the new rule. New repos get it at init, and existing repos get it on upgrade and sync.**

## New and existing repos

- **New repos** (init or adoption): the rule applies from their first review and cold read. The
  guide arrives with setup. The worker brief and the reviewer and reader instructions come with
  the release.
- **Existing repos** (on upgrade to this release): the rule applies from the next close or read,
  after `forge sync`. Findings and notes that an earlier release already moved to follow-ups stay
  follow-ups. They keep their reason "Left open after round two" or "Left open after round one",
  and plan notes keep their keep line. A review stop that an earlier release recorded for a P0
  still waits for the owner's choice. A cold read that an earlier release stopped for its first
  P0 round does not wait: the coordinator fixes the P0 and reads again, as the new rule says.
  Tested on the adopted earlier-release fixture moved to this release.

## Risks

Risks: none one-way. Each part reverts with its pull request.

Trade-off: the owner answers more stops. A fix with an open P1 at the bar now stops after its one
review round, where today it goes on to merge with a follow-up.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

This story changes FORGE-ROUNDS-1 (`plans/FORGE-ROUNDS-1.md`). Its round limits, round-two
scope, `Case: rare` rule, worker declines and live run stay as they are.

Every Done-when item has exactly one test function, `test_<n>_...`, in one new file,
`tests/test_owner_decides_at_the_round_limit.py`, which starts with `STORY = "FORGE-ROUNDS-2"`.
Each test runs the forge command and never imports forge. Each runs on a new repo and on
`tests/fixtures/adopted-v1.2.2` moved to this release. Reuse the helpers of
`tests/test_two_round_limit.py`: `client(env, adopted)` (both repos), `note`, `published` and
`known`. Only the existing stubs are faked: Autoreview and GitHub (`blocked`, `finding`, `CLEAN`
and `env` in `tests/test_close.py`), the Claude worker (`install_claude` and `calls` in
`tests/test_worker.py`), the session host (`Session` in `tests/test_tools_session_hold.py`) and
the reader (`say` and `dispose_all` in `tests/test_readloop_gates.py`, `read_client` in
`tests/test_fix_plan_reads_capped.py`). Guide delivery reuses `unsynced_up`, `_fresh_client` and
`_repo_adopted_on_the_previous_release`, as test_4 of `tests/test_stuck_worker_asks.py` does.

**Words this story pins.**
- The round limit is unchanged: review round 2 for a story part, review round 1 for a fix, read
  round 2 for a story, spec or decision. "At the limit" means a round whose number is the limit or
  more. A review's round is the item's count of `review` steps, as close counts it today. A read's
  round is the notes' `round`. No new counter is stored.
- A review finding is a P0 when `score.holds(finding, "P0")` is true. A read note is a P0 when
  `score.note_holds(note)` is true and `score.bar(score.parse(note)) == "block"`, as
  `story.stopped` checks today. A `Case: rare` finding or note is never a P0.
- P0 first. While any open finding of a review is a P0, close refuses with `blocked` and records
  no owner stop, also at the limit. The worker fixes every finding listed in that round. The owner
  stop comes only when a review at the limit has open findings and none of them is a P0.
- The same P0 is the same `score.identity(file, title)`.

### Done-when details

1. Review stop (CLOSE).
   - `review._bound_findings` loses its round-limit branch (the `elif ("/" not in item or
     previous.get("commit")) and score.holds(finding) and not score.holds(finding, "P0")` branch
     that sets `score.ROUND_TWO` or "Left open after round one") and its now unused `previous`
     parameter. The `Case: rare` and `Not done` reasons stay.
   - `close.close` loses the reused-review call: `round_number = ...` and `if fresh and
     round_number >= (2 if "/" in item else 1): refreshed = review._bound_findings(...)` (lines
     287-289). With no round-limit marking, it has nothing left to add: `score.holds` already
     ignores `Case: rare`, and `Not done` was marked when that review ran.
   - The stop condition (`if serious and round_number >= (2 if "/" in item else 1) and (not fresh
     or not state.get("stop"))`) also needs `not any(score.holds(f, "P0") for _, f in serious)`.
     The stop record, the owner wait and `status = "hotspot"` stay. `stopped["review_limit"]` goes.
   - One refusal replaces two. `REFUSALS["fix_p0"]` goes. `REFUSALS["hotspot"]` becomes
     `"Review round {round} of {item} reached the round limit with open findings, so Forge
     stopped. {question}"`, with the same next step, `forge close {item} --resolve
     <more|split|accept> --reason "<human's choice>"`. Close's refusal, `close.check_stop` and
     `land.py` (`error.entry in (...)`) use only `hotspot`. In `nextstep.py`, the stop's reason
     line becomes `its review reached the round limit with open findings` for every review stop.
   - `review.stop_question`'s Accept line becomes `the {n} findings listed become follow-ups in
     Known issues with your reason; close then goes on to the checks, and merging is still a
     separate step.`
   - `score.remember`: a finding that the owner accepted (its dismissal has `accepted: True`)
     gets the outcome `follow-up`, with the dismissal's reason ("Human accepted the remaining
     finding: <reason>"). Then `known_issues` lists it. An evidence dismissal keeps the outcome
     `accepted`.
   - `close.stuck_round` starts with `check_stop(item, state, top)` in place of its own
     stuck-only check. `worker.py` calls `stuck_round` before each round on both routes (the
     Codex or Claude kit, and the native session subagent). So `forge work` refuses with
     `stuck` for a stuck question and with `hotspot` for a review stop. A recorded choice lets
     the round run.
   - The `repair-review` block of `review.md` replaces its last two sentences ("Every finding below
     P0 becomes a follow-up from round two..." and "Forge keeps its original scores...") with
     `Forge asks the owner about each finding below P0 that is still open at the round limit.`
   - Normal-use cases: a story part's round 2 with an open P1; a fix's round 1 with an open P1; the
     owner's accept; the owner's `more` followed by a clean round; `forge land` at the stop;
     `forge work` at the stop, from a terminal and from a Claude Code session.
   - Test: `test_1_at_the_round_limit_an_open_finding_below_p0_stops_for_the_owner`, with the
     parameter `case` in ("part", "fix", "adopted fix", "session").
     - part (new repo): Autoreview returns the same P1 at the bar (`note("P1", ...)`) in both
       rounds. Round 1's close exits 1 with "The review left serious findings open" and no
       "reached the round limit". After a worker commit, round 2's close exits 1. Its stderr has
       `Review round 2 of SHOP/T1 reached the round limit with open findings, so Forge stopped.`,
       "One more round, split or accept?", the title and the `--resolve <more|split|accept>`
       step. Round 2's review prompt has the new `review.md` sentence. `forge next` shows the
       question. With `install_claude`, `forge work` exits 1 with the same stop line and step,
       and the worker ran no round. `forge close --resolve accept --reason "<reason>"` exits 0
       with "Ready". `known(env, where)` shows the title with `kept` "follow-up" and a reason that
       starts with "Human accepted the remaining finding:". Autoreview ran twice.
     - fix (new repo): round 1 with a P1 stops the same way. `forge land` exits 3 with the
       question. Accept gives "Ready". Autoreview ran once.
     - adopted fix (`client(env, True)`): round 1 with a P1 stops. `--resolve more` prints
       `Next: forge work tidy-readme`. `forge work` exits 0, and its brief has "The owner chose
       more". After a commit, a clean round 2 gives "Ready".
     - session (new repo): the fix's round 1 stops. From a `Session` with `CLAUDECODE=1`,
       `forge work` exits 1 with the same stop line and step and prints no subagent
       instruction (no `--round`).
2. P0 rounds (CLOSE).
   - `close.stuck_round` counts each open P0 of the saved review as a key next to "close's
     tests failing": for each `(_, f)` in `review.blocking(state.get("review") or {})` with
     `score.holds(f, "P0")`, with `file, title = score.identity(f["file"], f["title"])`, the key
     is `f"the open P0 {title} in {file}"`. The count, the rule that a choice buys one more round,
     and `stuck_stop`'s question and choices (`switch|same|narrow|split`) stay as they are. Its
     line reads, for example, "Two rounds in a row left the open P0 saving deletes the basket in
     app.py." in the identity's lower case.
   - `worker.REVIEW_LOOP`'s review half becomes: `At the round limit (review round two for a story
     part, round one for a fix), close stops when findings below P0 are still open. Wait for the
     owner's recorded choice of one more round, split or accept. An open P0 never stops for the
     owner: fix it in this round. When the same P0 stays open two rounds in a row, Forge stops and
     asks the owner.`
   - Normal-use cases: a fix whose P0 stays after its limit; a story part whose P0 stays at round
     2; a different P0 in round 2, which is progress; the owner's `same` choice.
   - Test: `test_2_an_open_p0_goes_back_to_the_worker_until_it_is_stuck_two_rounds`, with the
     parameter `case` in ("fix", "part", "adopted fix", "other p0"). It uses `install_claude` for
     the worker.
     - Round 1 returns a P0 (`note("P0", "Saving deletes the basket")`). Close exits 1 with "The
       review left serious findings open". Its stderr has no "Forge stopped" and no
       `--resolve <more`. `forge work` exits 0. After a commit, round 2 returns the same P0 (for
       "other p0", a P0 with another title). Close exits 1 the same way, with no owner stop, and
       `forge next` has no "One more round, split or accept?". The round-2 worker brief has
       "An open P0 never stops for the owner: fix it in this round."
     - The next `forge work` exits 1. Its stderr has "The worker can't get past the same problem",
       "Two rounds in a row left the open P0 saving deletes the basket in app.py." and, as its
       last line, `Next: forge close <item> --resolve <switch|same|narrow|split> --reason
       "<human's choice>"`. The worker ran two rounds, and Autoreview ran twice.
     - fix: `--resolve same --reason "One more try"`, then `forge work` exits 0 with the owner's
       choice in the brief.
     - other p0: the third `forge work` exits 0.
3. Read stop (READ).
   - `story.read_result` loses the `follow_ups` block (it wrote `Disposition: keep - Left open
     after round two` and recorded `loop_choice: accept`) and the "passed with follow-ups"
     outcome. Its last `stopped(...)` check stays and refuses with `read_loop`. That check now
     gets the whole notes body that `_write` writes (`f"{kept}\n\n## Round {round_number}\n\n
     {said}\n"`), not only the new round, so `stopped` can see the round before.
   - `story.stopped(record, findings)` is true when the latest round is 2 or more, did not pass,
     has no `loop_choice`, and either holds no P0 note or the round before it also held a P0 note.
     `_latest` returns every note from a round's heading to the end, so the round before is
     `_latest` of the previous round number without the latest round's note numbers:
     `{n: b for n, b in _latest({"round": str(int(record["round"]) - 1)}, findings).items() if n
     not in latest}`. Note numbers go on across rounds, so this holds exactly that round's notes.
     `forge read`'s start refusal, `--resolve` and `forge next` already pass the whole notes body.
     A P0 note
     keeps counting after the coordinator gives it a disposition. Reads count P0 rounds and not
     the same note: a later round never repeats a disposed note's title (`read_result` drops it as
     settled), so the same note cannot come back. The reads' P0 rounds count as close's
     "tests failing" key does, which counts rounds and not which test fails.
   - `REFUSALS["read_loop"]` becomes `"Round {round} of the cold read of {target} stopped with
     open notes, so Forge asks the owner. {question}"`, with the same next step. `forge read
     --resolve accept|more|split` stays. Accept keeps the notes with the owner's reason, as today.
     Plan read notes are not in the board's Known issues today, and this story does not add them.
   - `score.ROUND_TWO` goes: this part removes its last user.
   - `cold-read.md`'s `round` part replaces "Every other open note becomes a follow-up after round
     two." with `Forge asks the owner about every other open note after round two.`
   - `worker.REVIEW_LOOP`'s read half becomes: `A cold read stops after round two when notes below
     P0 are still open, or when P0 notes are open in two rounds in a row. The coordinator records
     the owner's choice with forge read <target> --resolve <accept|more|split> --reason "<human's
     choice>".`
   - Normal-use cases: a story and a spec; a held note below P0 in round 2; a P0 note in round 2
     after a round 1 with none; P0 notes in rounds 1 and 2; `accept` and `more`.
   - Test: `test_3_from_round_two_a_cold_read_with_an_open_note_below_p0_stops_for_the_owner`,
     with the parameters `adopted`, `target` in ("SHOP", "invoices") and `case` in ("below p0",
     "p0 once", "p0 twice"). "below p0" and "p0 once" run on both repos; "p0 twice" runs on a new repo.
     - below p0: round 1 has a held note (Gain 4, Work 1, Harm 2), which gets a cut disposition.
       Round 2 has a new held note with the same scores. The read exits 1 with `Round 2 of the
       cold read of <target> stopped with open notes, so Forge asks the owner.`, "One more round,
       split or accept?" and the `--resolve <accept|more|split>` step. The notes have no "Left
       open after round two". The round-2 prompt has the new `cold-read.md` sentence. `forge
       next` repeats the question. A third `forge read` refuses, and the reader ran twice. Then
       `--resolve accept --reason "<reason>"` writes `Disposition: keep - <reason>`, and `forge
       next` names Plan Mode (a story) or `forge spec confirm invoices` (a spec).
     - p0 once: round 1 has a Harm 2 note and round 2 a Harm 5 note. The read exits 0 with "Wrote
       round 2", and its output has no question. `forge next` has no question either. After
       `dispose_all`, the next `forge read` runs the reader a third time.
     - p0 twice: rounds 1 and 2 each have a Harm 5 note with different titles. The read exits 1
       with the stop. `--resolve more` prints `Next: forge read <target>`. After `dispose_all`, a
       round 3 with "No findings." passes.
4. The shipped words (CLOSE and READ; READ adds the test).
   - The guide (`src/forge/templates/skill.md`) gets these sentences, in place of the old ones in
     "Planning a story", "Closing", the stop section, the stuck paragraph and the cold-read
     paragraph:
     - CLOSE: `At the round limit, open findings below P0 stop the item and ask the owner: one
       more round, split or accept.`;
     - CLOSE: `An open P0 never stops for the owner; the worker keeps fixing it.`;
     - CLOSE: ``When two rounds in a row leave close's tests failing or the same P0 open, `forge
       work` stops the item``, which replaces ``When two rounds in a row leave close's tests
       failing, `forge work` stops``;
     - CLOSE: `Accept makes the open findings follow-ups in Known issues with the owner's reason.`;
     - READ: `A cold read stops after round two when notes below P0 are still open, or when P0
       notes are open in two rounds in a row.`
   - Each part removes its share of the old text from the guide, `brief.md`, `README.md` and the
     `COMMANDS` listings: "Left open after round two", "Left open after round one", "become
     visible follow-ups", "Other open notes become follow-ups", and "An open P0 stops". In
     `brief.md`, CLOSE replaces "Every other open finding becomes a visible follow-up, whether
     its line changed or not." with `At the round limit, other open findings stop the item for
     the owner's choice.`
   - The listings: close.py's `forge close` row says that at the limit, open findings below P0
     wait for `--resolve more`, `split` or `accept`, and that an open P0 goes back to the worker
     (CLOSE). story.py's `forge read` row says that after round two, open notes below P0, or P0
     notes in two rounds in a row, wait for the same choices (READ). `forge sync` then rewrites
     `docs/commands.md`, `.claude/skills/forge/` and `.codex/skills/forge/`.
   - Test: `test_4_clients_get_the_owner_decides_at_the_round_limit_guide`, with the parameter
     `adoption` in ("new init", "previous release upgrade and sync"). For `.claude` and `.codex`,
     `skills/forge/SKILL.md` has the five guide sentences above (whitespace joined) and has no
     "Left open after round" and no "Other open notes become follow-ups".

## Tasks

<!-- One row per task. Covers: the Done-when numbers it delivers, at most three. Scope: the paths
it may change. Tests: the tests it adds or changes. After: the tasks it waits for. When two tasks
share a function, field, file format or command, the first task pins it: it commits the shared
names and stubs plus one test that crosses both sides, and the tasks that use it list it under
After. Split tasks so each owns its files; shared lines (command table, guide list, registry) go
to one task or a small last wiring task; After only when a task needs another task's code. The
Developer column is optional: the lead fills or changes a GitHub username here, below For the
builders, without another approval. Leave it blank for an unassigned part. Forge next uses
the caller's GitHub login; another developer may start it with a warning. Existing tables
without Developer still work. The moving-parts line stays last: "none", or each new dependency, service, datastore,
queue, background job or abstraction layer, with the Done-when item that needs it. -->

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| CLOSE | Review stop and P0 rounds | At the review limit, open findings below P0 stop for the owner, and accept makes them Known issues follow-ups. An open P0 goes back to the worker, and the same P0 two rounds in a row gives the stuck stop. `forge work` refuses at either stop on both routes. The automatic round-limit follow-ups, the reused-review call, `fix_p0` and `review_limit` are deleted. The guide, brief, reviewer page, close listing and README say the review rule. | 1, 2 | `src/forge/close.py`, `src/forge/review.py`, `src/forge/score.py`, `src/forge/land.py`, `src/forge/nextstep.py`, `src/forge/worker.py`, `src/forge/templates/review.md`, `src/forge/templates/brief.md`, `src/forge/templates/skill.md`, `README.md`, `docs/commands.md`, `.claude/skills/forge/`, `.codex/skills/forge/` (the last three rewritten by `forge sync`) | `tests/test_owner_decides_at_the_round_limit.py` (`test_1`, `test_2`), plus CLOSE's changes in Notes | | no | |
| READ | Read stop | From round two, a cold read with open notes below P0 stops for the owner, and an open P0 note stops only in two rounds in a row. The automatic read follow-ups and `score.ROUND_TWO` are deleted. The guide, reader page, brief text, read listing and README say the read rule, and the guide test covers both parts. | 3, 4 | `src/forge/story.py`, `src/forge/score.py`, `src/forge/worker.py`, `src/forge/templates/cold-read.md`, `src/forge/templates/skill.md`, `README.md`, `docs/commands.md`, `.claude/skills/forge/`, `.codex/skills/forge/` | `tests/test_owner_decides_at_the_round_limit.py` (`test_3`, `test_4`), plus READ's changes in Notes | CLOSE | no | |

New moving parts: none

## Notes

- **Order.** CLOSE, then READ. They share `score.py`, `worker.py`'s `REVIEW_LOOP`, `skill.md`,
  `README.md`, the generated guide copies and the new test file. Between them, a cold read still
  moves round-two notes to follow-ups. Both ship in one release.
- **Release notes.** The release notes are the GitHub release text that the coordinator writes at
  the release, as v1.2.18's "At most two rounds" section. The release that ships this story says
  the new rule there. No part builds it.
- **Deleted, by part.**
  - CLOSE: the round-limit branch and the `previous` parameter of `review._bound_findings`; the
    reused-review call in close (3 lines); `REFUSALS["fix_p0"]`, `stopped["review_limit"]` and
    their uses in close, land and next; the stuck-only check at the top of `stuck_round`.
  - READ: the `follow_ups` block and the "passed with follow-ups" outcome in
    `story.read_result`; `score.ROUND_TWO`.
- **Expected net lines.** close.py about -8, review.py about -4, story.py about -6, score.py
  about -1, land.py and nextstep.py about -1 each. story.py is at 1,193 lines and must not grow.
- **Existing tests.**
  - CLOSE:
    - Deletes `tests/test_fix_review_limit.py`: its rule (a fix's round-one P1 becomes a follow-up
      and a P0 waits for the owner) is reversed, and test_1's fix cases replace it.
    - In `tests/test_two_round_limit.py`: deletes test_1 (new test_1 replaces it). Drops the "p0"
      case of test_3 and renames it `test_3_land_runs_at_most_one_fix_round`; its "tests" and
      "session" cases stay. In test_4, the "p1" case now expects the stop (exit 1 with the stop
      line), not "Follow-ups:". test_5 and test_6 stay; test_5's comment about fix follow-ups in
      round one is updated.
    - Changes test_4 of `tests/test_stuck_worker_asks.py` to the new stuck sentence.
    - Each test that builds a review stop with a P0 at the limit builds it with a P1 at the bar
      (Gain 4, Work 1, Harm 2) and expects the new `hotspot` line. Known ones:
      `tests/test_close.py` (the round-2 stop near "still has an open P0 in app.py"),
      `tests/test_mainonce_clash.py`, `tests/test_queue_land_all.py`,
      `tests/test_upgrade_command.py`, `tests/test_pull_request_body_limit.py`,
      `tests/test_close_waits_for_review_loop_choice.py`. Run the stop tests too
      (`tests/test_land_returns_the_owner_question.py`,
      `tests/test_land_records_review_loop_choice.py`,
      `tests/test_review_loop_records_each_stop_choice.py`,
      `tests/test_owner_stops_survive_main_merges.py`, `tests/test_item_time_history.py`,
      `tests/test_accept_dismisses_the_latest_review_findings.py`,
      `tests/test_hotspot_stop.py`, `tests/test_split_keeps_review_findings.py`,
      `tests/test_board_needs_you.py`) and adapt only how they build their stop.
    - A test that expected a fix's round-one P1 to go on to Ready records `--resolve accept`, or
      returns that finding below the bar, whichever keeps what it tests.
  - READ:
    - In `tests/test_two_round_limit.py`, test_2 keeps one walk per target and its round-two
      prompt checks (the P0-only sentence, no `look` text, "Is each of those findings closed?").
      Its outcome walks go: new test_3 owns them.
    - Each walk that passed round two with follow-ups now gets the stop, records `forge read
      <target> --resolve accept --reason "<reason>"`, and expects `Disposition: keep - <reason>`
      where it expected "Left open after round two": `tests/test_fix_plan_reads_capped.py`,
      `tests/test_tools_native_reads.py`, `tests/test_readloop_rounds.py`,
      `tests/test_score_bar.py`, `tests/test_board_story_history.py` (its `read_rounds` reason)
      and `tests/test_settled_rounds.py`.
- **Not to do.**
  - No new command, option, choice or `forge.toml` setting.
  - No stored round counter and no new stop kind: the review stop and the stuck stop exist.
  - Do not reopen findings or notes that an earlier release already made follow-ups.
  - Do not change worker declines, the `Case: rare` rule, the round-two scope or the live run.
  - Do not touch spotted hotspots ("keeps breaking" in `forge next`).
- No client repo is named anywhere in this story's code, tests, texts or commits.
