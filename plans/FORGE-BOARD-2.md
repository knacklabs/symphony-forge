# The board tells a team what's happening, what needs them and when it goes live

10 parts · Risks: none · New moving parts: none

## What changes for you

- When you open the board, the first screen answers four questions without scrolling: what is in
  progress, what needs a person, what is stuck and why, and when the planned work can go live.
- One calm sentence at the top says where things stand. Below it, a quiet line of totals counts
  stories, parts and fixes separately, so the numbers never mix or contradict each other.
- "Needs you" sits at today's line and shows how long each item has waited: a plan waiting for
  approval, a review that needs your call, a pull request waiting for you to merge, a worker's
  unanswered question, or a merge conflict.
- Each story in progress is drawn along time: solid where work was happening, thin where it was
  waiting. Open any row to see where its time went, one line per review round, and who started
  and approved it.
- Go-live shows as a date range worked out from the team's recent pace, and the stories with no
  plan yet are named as the unknown. When there is too little history to estimate, it says so
  instead of guessing.
- Further down: a dependency graph of every story on the roadmap. Parts sit in columns by when
  they can start, so everything in one column can run in parallel; arrows show what waits on
  what, across stories too; running parts are marked; finished parts fold into "N done"; stories
  with no plan yet are small boxes of their own; open fixes sit in one row at the top, so all the
  work running in parallel is in one picture. Then weekly trends of merged pull requests for the
  team and for each person, split into work that went through Forge and work that went around it,
  with people in alphabetical order and never ranked. Next to them, a list of this week's pull
  requests that went around Forge.
- A bar pinned at the top jumps to Overview, Roadmap, Stories and Fixes, and every section folds,
  so you never scroll the whole page. Each story shows its short key in small grey text so
  look-alike titles can be told apart, and a story's history
  includes each review of its plan and how it was answered.
- A story counts as building only once work on one of its parts has started; approved but not
  started is counted on its own. Needs you also shows problems that block work, such as a broken
  plan, and times read as "15 seconds", never "15.001 seconds".
- Every teammate sees the same facts after fetching, because each item's time story travels in
  its pull request.
- The Claude Code pane opens with the same summary lines.
- Upgrading fills in the history: as its last step the upgrade rebuilds where time went for open
  work and for work finished in the last six weeks, from what git and GitHub recorded, marks it
  "rebuilt from history" and leaves anything it can't tell as unknown. Older work shows at once
  who started, approved and merged it, and the agent then opens the board and tells you what is
  still missing.

## Why

A project manager or team lead who opens the board today can't use it. Two reviews of a real
client board (October 2026) found half of a laptop screen empty, 119 "Not started yet" cards
before the four stories actually in progress, counts that mix stories and fixes and contradict
the cards, nothing saying what's blocked, who owns what or what needs a person, and no pace or
forecast even though parts finished per week fell from 13 to 4 to 2. Most of an item's time is
waiting, and the board never shows it. A first-time viewer answered 0 of 4 basic questions
correctly in a minute; the target is 4 of 4 by 2026-11-15.

## Done when

1. **Stories, parts and fixes each have exactly one state, are counted separately, and every count, status and time on the page and in the pane matches `forge board --json` and `forge next`.**
2. **Needs you lists every item waiting on a person, oldest first, each with how long it has waited: a plan waiting for approval, a review-loop choice, a pull request waiting for a human merge, an unanswered worker question, or a merge conflict that close stopped on.**
3. **Blocked or slow lists, each with its reason and how long: started, unfinished parts and fixes with no activity for 24 hours or more; items whose review has been blocked three or more rounds; and the unfinished part the most unfinished parts wait on.**
4. **Pace shows parts and fixes merged per week for the last six full weeks, and go-live gives a date range for the remaining parts of approved stories from the last three and six weeks' pace (or "about" one date when the two agree, "not enough history", or "planned work done"), naming the stories with no plan as the unknown.**
5. **Each item shows its time split into working, waiting and unknown, one line per review round saying what it did and whether its findings were new or repeated, and who started and approved it, the same on every teammate's machine because it is read from the item's pull request, with a merge on GitHub ending the last wait at its merge time.**
6. **Below the first screen, the team and each person show merged pull requests per week for the last six full weeks, split into through Forge and around Forge, with people in alphabetical order and no ranking, beside a list of the pull requests merged around Forge in the last 7 days with title, author and merge day.**
7. **In a 1440 by 900 window the first screen, without scrolling, shows a one-sentence summary, the labelled totals, at most five rows each of Needs you, In progress and Blocked or slow with "and N more" opening the rest, and Pace with go-live.**
8. **Below the first screen come a one-line key for the graph's shapes and the words part, fix and plan, and every story and fix sorted needs-you, blocked, in progress, planned, no plan yet, then done (folded away), on a page that uses the full laptop width, reads in light and dark mode, and stacks to one column in a narrow window.**
9. **The Claude Code pane opens with the same summary sentence, totals, Needs you, In progress, Blocked or slow and go-live lines as the board's first screen.**
10. **As the last step of an upgrade, Forge rebuilds the time story of every open item and every item merged in the last six weeks that has none, from its commits, review results, checks and merge time, marks it as rebuilt from history and leaves what it can't tell unknown, while older items show who started, approved and merged them and their review results from git and GitHub, and the agent then opens the board and reports what is still missing.**
11. **Below the first screen, a dependency graph of every roadmap story shows each planned story's parts in columns by when they can start, so parts that can run in parallel share a column, with arrows for waits within and across stories, running parts marked, finished parts folded into "N done", and each story with no plan as its own box, with open fixes in one row at the top marked running or waiting.**
12. **A bar pinned to the top jumps to Overview, Roadmap, Stories and Fixes and every section folds, each story shows its key small beside its title and its history lists its plan's cold-read rounds, a story counts as building only once a part has started, Needs you also lists the blocking problems `forge next` reports, and every time reads in rounded plain units.**

## New and existing repos

- **New repos** (init or adoption) get the new board from the first run. With no history it says
  "Not enough history to estimate", "Nothing needs a person" and "No pull requests merged around
  Forge this week". The first close writes each item's How it went section.
- **Existing repos** get the new board on moving to the new release (one upgrade fix) and sync.
  Who started, approved and merged each older item, and its review results, come straight from
  git and GitHub. As the upgrade's last step, Forge rebuilds the time story of every open item and
  every item merged in the last six weeks that has none, writes it into that item's pull request
  marked as rebuilt from history, and leaves spans with no evidence unknown; items merged earlier
  keep unknown times. Pace and trends count older merges at once from git merge dates and
  GitHub's pull request list. The synced guide tells the agent to open the board after the
  upgrade and report anything still missing. A repo still pinned to an
  older Forge runs that release's board. Tested by an upgrade test on a repo adopted on the
  previous release.

## Risks

Risks: none

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

This story builds on three in-flight fixes and must not repeat their work (see Notes):
fix/board-data-truth, fix/where-time-went and fix/queued-not-stop. Each task starts after all
three have merged. Each task stays at most about 400 changed lines. Every part may add its paragraph to src/forge/templates/skill.md; the guide is left out of the Scope column so parts that share only it run in parallel, and each part merges main and keeps every other part's paragraph. PAGE renders against the team schema COUNTS pins (later keys null) and fills in as WAITS and TRENDS land; BACKFILL is off the critical path.

**One derivation.** `board.machine_board` (src/forge/board.py) stays the single derivation feeding
`forge board --json`, `forge next --json`, the HTML page and the pane. The new team facts live in
a new module, src/forge/board_facts.py, which `machine_board` calls once. Every number, date and
sentence the page or pane shows comes from that output; neither surface computes its own.
`machine_board(top, …, trim=True)` keeps today's 7-day trim of finished `items` for the JSON;
the page calls it with `trim=False`, so done work older than 7 days is rendered from the same
derivation. Team facts are computed before any trim.

**JSON.** `machine_board` gains a top-level `team` object with keys `sentence`, `counts`,
`needs_you`, `in_progress`, `blocked`, `pace`, `go_live`, `trends`, `around_forge`. Each item row
gains `state` (the spec's state word), `merged_at`, `merged_by`, and `time`:
`{working_seconds, waiting_seconds, unknown_seconds, intervals: [{kind: working|waiting|unknown, category, from, to}], source: "this machine"|"pull request"|"both"|null}`.
`approved_by` becomes a plain name or null (on main it returns a sentence and is never null).
`stage_counts` and `kind_stage_counts` are removed; `team.counts` replaces them (no mod hook reads
them). Unknown is always `null`, never 0 or a guess.

**The shared record.** Close's `## How it went` section (where-time-went) gains one hidden line,
`<!-- forge:how-it-went {json} -->`, holding `intervals`, `rounds` (each round's review id,
commit, outcome and findings), `waits`
(`[{id, reason: merge|review loop|conflict|worker question, since, ended, question?}]`, `ended`
null while open; a wait id is never removed once written) and `clean_reviews` (`[{commit, at}]`:
every head commit a close reviewed clean and wrote a receipt for), plus `rebuilt: true` when
BACKFILL rebuilt any of it from history.
`time_records.from_body(body) -> dict | None` reads it, ignoring unknown fields, None when missing
or malformed. `time_records.merged(local, shared) -> dict` is the one merge every reader and
writer uses: the union of intervals deduplicated by `(category, from, to)`; rounds by their review
id (else round number); waits by id, never dropping an id, a wait being open only when no side has
an `ended` for it (the earliest `ended` wins); `clean_reviews` by union on `commit`; `rebuilt` true when either side has it, so a later close
or `forge merge` never drops the label. After merging, the time breakdown and each round's
new versus repeated findings are recomputed from the combined rounds in order, never carried over
from either side. Close and
`forge merge` merge the PR body's record with local logs before writing, so no machine overwrites
another; the board shows the same merge. `close.refresh_record(top, item, state, pr)` rewrites
only that section of an open pull request (merge.py's `refresh_history` moves into it) and is the
one way a command publishes the record outside a full close.

**GitHub.** Eight calls, one cache, at most once a minute: `board._prs(top)` runs
`gh pr list --state open --limit 1000 --json headRefName,state,title,body,mergedAt,mergedBy,author,number,url,isDraft`
and one date-bounded search per week,
`gh pr list --state merged --search "merged:<monday>..<sunday>" --limit 1000 --json <same fields>`,
for each of the six full weeks and the current partial week. All answers are cached together for
60 s in `.git/forge/prs-cache.json` following `_machine_prs`'s pattern (`fetched_at` stored with
the data, temp file swapped in with `os.replace`, a failed fetch never cached, a read-only Git dir
tolerated). The JSON path uses it instead of today's uncached `nextstep._prs(top, "open"|"merged", …)`
calls. A week whose search returns 1,000 rows is unknown (null) in the trends, because its rows
need not be complete; the around-Forge list comes from the current and last week's searches and
is unknown when either hit the cap. When the open list returns 1,000 rows,
`team.needs_you_complete` is false and the board says some waits may be missing. Pace reads git,
so the cap never affects it. Merged pull requests older than the window give no `merged_by` or
record (unknown). The code carries
`# ponytail: eight list calls a minute at most; a week over 1,000 merges shows unknown, search by day if a team needs it.`
The existing 25-PR details request for the success numbers stays as it is on the page and
`forge next` path.

**Weeks.** A full week runs Monday 00:00 UTC to the next Monday; the current partial week is
excluded. COUNTS adds `board_facts.full_weeks(now, 6)` for its weekly searches; TRENDS reuses it
for pace and trends.

**Guide.** Each task updates its own paragraph of src/forge/templates/skill.md in the same change
(the AGENTS.md review rule). The task graph never lets two tasks that list skill.md run at once.

### Done-when details

1. **Counts.** Each item's state comes from the first rule that matches, as the spec words them.
   Stories: done (last part merged per `story.completed`, or the roadmap marks it done); building
   (plan approved and at least one part started, that is has a state file; board-data-truth's
   "building" and "ready to merge" map here only then); approved, not started (plan approved, no
   part started); waiting for
   approval (`story.gate` passes on the plan and its read notes, the same check `forge next`
   uses, so a plan edited after a passing read is planning again); planning (a plan draft exists
   on any ref); no plan yet (roadmap only). Parts of approved stories and fixes: done (merged on
   the landed ref, or the PR is MERGED); ready to merge; in progress (a state file exists); to do.
   Every board and `forge next` read of an item's review history and readiness uses one ref,
   `nextstep.review_ref(top, branch)`: the PR's head (`origin/<branch>` after the fetch, else
   GitHub's `headRefOid`), unless the local branch contains it (is ahead of or equal to it), in
   which case the local branch. Ready to merge is one rule in `nextstep._item_readiness`, used by
   `forge next` and the board on every machine: that ref's commit is the commit of this
   machine's close receipt or appears in the shared record's `clean_reviews`, and checks are not
   failing. With neither a receipt nor a record (an older release's PR), the state file at that
   commit carries a clean `review` and status `waiting for checks` or `ready`, and checks pass.
   `forge merge` still requires a local receipt (a PR body is editable text, never a merge gate),
   and Forge has no take-over of another person's item. So an item ready on this machine only
   through the shared record still counts as ready, and its next step depends on the worktree:
   with no worktree for the item here, a plain line with no runnable command (`next.command`
   null). With `merge = "agent"` it reads "Ready to merge; <starter> merges it from their machine"
   ("the person who started it" when the starter is unknown); with `merge = "human"` it is the
   human-merge line `forge next` already gives for a ready pull request (merge it on GitHub). With the item's worktree here but no receipt, `forge close
   <item>`, which re-verifies and writes the receipt. The guide's readiness paragraph says so.
   `team.counts` is `{stories: {6 states}, parts: {4}, fixes: {4}, finished_last_7_days: {parts, fixes}}`,
   keyed by the plain labels the page and pane print. Parts of unapproved stories are not
   counted. "Finished" always means merged, dated by `history["dates"]`.
   Test, tests/test_board_counts.py: a new repo with one story per state, a story whose plan was
   edited above `## For the builders` after a passing read, a part per state, an open fix, a
   merged fix, and a ready part closed on machine A; machine B (a second clone, no receipt) gets
   the PR body close wrote from the gh stub. On both machines `forge board --json` gives the
   expected `team.counts`, the edited story counts as planning, and the ready part's `state`
   matches the item `forge next` names as ready; a story and its parts never share a count. On
   machine B, which has no worktree for the part, its next step is "Ready to merge; <A's name>
   merges it from their machine" with `next.command` null in an agent-merge repo, and the
   human-merge line in a `merge = "human"` repo. On machine A with its receipt removed,
   the next step is `forge close <item>`, and running it ends ready with a local receipt. Then
   another commit is pushed to the part's branch with plain git from a third clone: after a
   fetch, machine A (still holding its old receipt) and machine B both report it in progress, in
   `forge board --json` and `forge next`; A closes the newer commit clean, and after a fetch both
   machines report it ready.
   Second rule, cached GitHub calls, tests/test_board_github_once.py: two `forge board --json`
   runs within 60 s make exactly one open-list call and one merged search per week, eight in all
   (from the stub's gh-calls log); a week whose search returns 1,000 rows is null in the trends
   while the other weeks stay known, and an around-Forge list over a capped week is null; with gh
   failing, the JSON still prints and shows GitHub facts as unknown.
2. **Needs you.** `team.needs_you` entries are `{id, kind, title, reason, since, waited_seconds}`,
   oldest `since` first, an unknown `since` last. Each wait runs from the record that created it to
   the one that cleared it, merged from local logs and the shared record:
   - plan waiting for approval: from the passing round's `read_at` in `plans/<KEY>.read.md` on the
     story's plan ref, cleared by the `Approve the plan:` commit;
   - review-loop choice: from the commit that first saves an unchosen `stop`, cleared by the
     commit recording `stop.choice`; close pushes the branch and calls `close.refresh_record`
     both after saving the stop (before `check_stop` refuses) and after recording a `--resolve`
     choice (before it returns);
   - human merge: from where-time-went's `owner wait start` with reason `merge` (shared through
     the record), cleared at the PR's `mergedAt`; an open PR that is ready by item 1's rule in a
     `merge = "human"` repo with no such record still shows, with `since` null;
   - worker question: from the `worker question` event whose id equals
     `codex.record(top, item)["question_id"]`, cleared when an answer is given; when the item has
     an open PR, `forge work` calls `close.refresh_record` as it records the question and again
     as it records the answer, so the shared wait is
     `{id, reason: "worker question", since, ended, question}`; before any PR exists the question
     shows only on the asking machine, and the first publish carries it;
   - merge conflict: close writes `repo.record_event(top, item, "owner wait start", reason="conflict")`
     just before `repo.refuse(REFUSALS["conflict"], …)` and publishes it first: with an open PR
     it calls `close.refresh_record`; on a first close with no PR yet, it pushes the branch and
     opens the pull request as its normal publish would, carrying the open conflict wait in the
     record, then refuses; the next close writes `owner wait end` once its merge of the default
     branch succeeds. Only a worker question before any PR stays local.
   Test, tests/test_board_needs_you.py: on a new repo, produce each wait through the forge commands
   (a passing forge read, three blocked closes, a close ending ready with `merge = "human"`, a
   stubbed worker question on an item with a PR, a conflicting default branch). Machine A's and
   machine B's (second clone fed the stub's recorded PR bodies) `forge board --json` both list all
   five, oldest first, each with `waited_seconds`; after the approval, a `--resolve` choice, a
   merged PR stub, the answer given on machine B and a clean re-close, both lists are empty, and
   machine A's own log of the open question does not bring it back. A conflict on a fix's first
   close, with no PR yet, opens its pull request and shows in both machines' Needs you.
3. **Blocked or slow.** `team.blocked` rows are `{id, kind, title, reason: stalled|looping|blocks the most, detail, seconds}`,
   longest-standing first. Stalled: started, unfinished tasks and fixes with
   `idle_seconds >= 86400`, `seconds` from `idle_since`; items with `idle_since` null are left
   out. Looping: `review.blocked_rounds(top, item, ref) -> (count, since)`, close's
   `_three_blocked_reviews` moved to review.py with a `ref` parameter: the latest consecutive
   blocked results on distinct commits, and the commit date of the first of them; close keeps
   `count >= 3`, unchanged; the board passes `nextstep.review_ref(top, branch)` (item 1), and
   `seconds` runs from `since`. Blocks the most: over the `dependency_maps` parts of
   approved stories (building, or approved but not started), across stories, the unfinished part with the most unfinished parts depending on it, directly
   or indirectly; ties go to plan order; omitted when no part has a dependant; `seconds` from the
   part's start, or the story's approval when it hasn't started.
   Test, tests/test_board_blocked.py: a part idle 25 h (clock through the test shim), a fix
   blocked 4 rounds whose first blocked round was 30 h ago (after an earlier clean round), and the
   first part of an approved story with no part started, with 3 dependants in a chain that runs
   into another story, all show with their reasons (the last with `seconds` from the approval); the looping row's `seconds` is
   30 h; a merged fix idle for a month and an item with no visible activity do not show. Then
   machine A keeps one blocked round of another fix on its local branch while machine B pushes
   three more blocked rounds: after a fetch, machine A shows that fix as looping.
4. **Pace and go-live.** `team.pace` is
   `{weeks: [{week_start, parts, fixes}]×6, parts_per_week_3, parts_per_week_6}` from
   `history["dates"]` for task and fix state files, excluding `story-done` fixes. `team.go_live` is
   `{status: range|about|not enough history|done, earliest, latest, remaining_parts, no_plan: {count, titles}}`.
   `remaining_parts` counts parts of approved stories in to do, in progress and ready to merge.
   Each date is today (UTC) + ceil(remaining ÷ rate × 7) days, with rate3 = parts merged in the
   last 3 full weeks ÷ 3 and rate6 = the last 6 ÷ 6; the earlier date starts the range. Status, in
   this order: `not enough history` when the oldest merged part is less than three full weeks old
   or rate3 is 0 (so a new repo with nothing planned says this); else `done` when remaining is 0;
   else `about` when both dates fall on the same day, with "the two pace estimates agree"; else
   `range`. `team.sentence` gains the go-live clause.
   Test, tests/test_board_pace.py: stub merge dates (4, 2, 2, 1, 1, 0 parts per week, 6 remaining)
   give the expected range; equal rates give `about`; a 2-week-old repo gives `not enough history`;
   a fresh repo with nothing remaining gives `not enough history`; an older repo with nothing
   remaining gives `done`; every case names the roadmap stories with no plan.
5. **Where time went, on every machine.** where-time-went already computes `time_breakdown` and
   `rounds` from local logs and writes `## How it went` from close and `forge merge`. RECORD adds
   the shared record above; `time_records.item` also returns `intervals`, sorted into kinds
   (working: building, own_tests, reviewing, fixing_findings; waiting: waiting_for_ci,
   waiting_in_line, waiting_for_owner; unknown: nothing_running and any unrecorded span). The board
   reads `time_records.merged(local, from_body(pr body))`, with `source` naming what it had. A PR
   merged on GitHub ends the open owner wait and the item total at `mergedAt`. A story's runway is
   `time_records.story(parts, read_rounds)`: working where any of its parts, or a plan read round
   from its committed read notes (`read_at` minus the recorded read time, else unknown), is
   working; waiting where none is working and any is waiting; unknown otherwise; each instant
   counted once. Approval applies to stories and their parts; fixes show none. `merged_by` comes
   from the PR's `mergedBy`.
   Test, tests/test_board_how_it_went.py: machine A starts a fix and closes a blocked round with a
   CI wait and a finding; machine B (a second clone, fed the PR body the stub recorded) continues
   it, closes a blocked round naming the same finding, then a clean round; the stub now holds B's
   body. Both machines show B's first round with that finding counted as repeated, not new or
   unknown. Both machines'
   `forge board --json` show the same intervals, working, waiting and unknown seconds and round
   lines, A's local logs notwithstanding, and A's next close publishes a record still holding B's
   round. A story case: two parts with overlapping working intervals and a read round give one
   story runway with the overlap counted once. Once the PR stub turns MERGED with a `mergedAt`,
   the open wait ends there. The test checks only board output, never the record format
   (principle 5).
6. **Trends.** `team.trends` is
   `{weeks: [week_start]×6, team: [{through, around}], people: [{name, weeks: [{through, around}]}]}`.
   A PR is through Forge when its `headRefName` starts with `story/`, `task/` or `fix/`; otherwise
   around. Each person is the PR author's GitHub `name`, or `login` without one, sorted by name
   ignoring case, with no totals or ranking fields. `team.around_forge` is
   `[{title, author, merged_at, url}]` for PRs merged around Forge in the last 7 days, newest
   first. When GitHub can't be reached both are null and the page says so. The page draws, below
   the first screen, one row of six weekly marks for the team and one per person (through and
   around in two tones of ink, numbers written beside them), and the around-Forge list beside it.
   Tests: tests/test_board_trends.py (JSON): a stub PR list with three authors across 6 weeks,
   including an author with no name and an around-Forge PR this week, gives the expected per-week
   splits, people in alphabetical order, no field beyond the weekly counts, and the matching around
   list. tests/test_board_runway.py `trends`: the page from the same stub shows each person's six
   weekly through and around numbers in alphabetical order, no totals or rank, and each
   around-Forge pull request's title, author and merge day.
7. **First screen (Runway, binding below).** The page shows, in `<section id="first-screen">`, the
   sentence, the totals line, Needs you, In progress and Blocked or slow at most five rows each
   with "and N more" (a `<details>` opening the rest in place) when longer, and Pace with go-live.
   Each row's `<details>` opens in place to working and waiting time, round lines and who started,
   approved and merged it.
   Test, tests/test_board_runway.py `first_screen`: a repo with 7 waits, 6 items in progress and 2
   blocked rows; the first-screen section holds the sentence, the totals line equal to
   `team.counts`, 5 Needs you rows and "and 2 more", 5 In progress rows and "and 1 more", 2 Blocked
   rows with no "more", no list over five rows, and the go-live text; opening a row's detail shows
   its round lines. Browser proof (below) applies.
8. **Below the first screen, theme and width.** board_visuals.py renders the page from
   `machine_board(…, trim=False)` only. The old card page is deleted from board.py (`_page` and
   its cards, the "What happened" timeline, `_part`'s took and slow lines); `numbers_line` and
   `_numbers` stay in board.py with unchanged output, and `_gather`, `_story` and `_part` shrink
   to the start, green, touches and approved fields `_numbers` reads. The success numbers show as
   one quiet line below the first screen. The graph itself is GRAPH's (item 11). A one-line key explains the shapes and the words part,
   fix and plan. Rows sort needs-you, blocked, in progress, planned, no plan yet, done; done rows,
   including those finished more than 7 days ago, sit inside one closed `<details>`.
   Tests: tests/test_board_runway.py `below_the_fold` (order, collapse, key, a fix finished 10
   days ago present in the done fold); the existing theme contract in
   tests/test_board_dependency_timelines.py, updated: `prefers-color-scheme: dark` tokens, no
   fixed `max-width` narrower than the window, one column below 720px, still no `<script>`,
   `<img>`, `<link>` or external URL.
9. **Pane.** A new `teamLines(data)` in src/forge/mod/hooks/summary.ts returns, from `board.team`:
   the sentence, the totals, up to 5 rows each of Needs you, In progress and Blocked or slow with
   "and N more · forge board for all", and the go-live line. The pane's Board tab (`pane.ts`) and
   `/forge` text (`text()`) start with these lines, then today's live item rows, unchanged.
   `forge.ts` treats `team` as optional, so an older Forge shows no team lines. The strip is
   unchanged. The words follow PRODUCT.md.
   Test, tests/test_board_pane_lines.py: `forge board --json` on item 7's fixture, fed to
   `summary.ts` through node (the `node_run` pattern in tests/test_mod_plugin.py): the pane's lines
   hold the same sentence, totals, row titles and "and N more" counts as the page's first screen.
   COUNTS, the first task that changes tests/fixtures/board.json (the shared mod contract),
   first copies today's file unchanged to tests/fixtures/board-previous.json (an older release's
   board, no `team`); PANE only reads that snapshot. Second rule, same test file: from
   board-previous.json the pane draws its live item rows and no team lines.
10. **Upgrade and backfill.** No new command (the command ceiling is fixed). The backfill lives
    in a new module, src/forge/backfill.py, and runs as the last step of closing an upgrade fix
    (a fix whose change sets a new `version` in forge.toml): `forge upgrade` always runs the
    newly installed release's own `forge close` on its fix (upgrade.py step 7, through
    `repo.run_release`), so every upgrade route, the uvx one included and upgrades started from an
    older release, runs the new release's backfill after its fix closes. It is idempotent: it
    skips a PR whose body already carries a record, rebuilt or not, and it runs again when a rerun
    of upgrade reruns that close. With GitHub unreachable it prints one line ("Couldn't reach
    GitHub, so older items' time stories weren't rebuilt; the next forge close on this machine
    tries again.") and the upgrade still succeeds. It then leaves `.git/forge/backfill-pending`;
    every `forge close` on that machine (the upgrade itself merges and refuses a rerun at the same
    release, so the retry cannot be `forge upgrade`) runs the whole backfill first while that file
    exists, deletes it only when every in-scope item then has a record (each read and each PR
    body write succeeded; any failure keeps the file and prints the same line), and never fails
    the close over it.
    Scope: every open item, and every item merged at or after exactly 42 days (six weeks) before
    the run, whose PR has no record. Item 1's weekly searches reach further back (up to a week
    more on a Sunday) and are only where the merged PRs are read from; the 42-day cut decides. An open item with no PR yet is not stored anywhere at upgrade: close's
    first publish of any item whose PR has no record runs the same rebuild for that item (from git
    and GitHub only, so on whichever machine closes it) and merges it with local logs through
    `time_records.merged`. An item's own history survives a squash merge and a deleted branch:
    one `git fetch origin` of every in-scope PR's `refs/pull/<number>/head` (GitHub keeps it
    after the branch is gone; read from FETCH_HEAD, no ref written) gives its original commits,
    and the rebuild walks back from that head to the item's own start commit (the commit that
    first adds its state file), so a squash, an ordinary merge commit and a fast-forward all give
    the same commits; it never uses a merge base with the default branch, which after a merge
    commit or fast-forward is the head itself. Readiness survives the new record: for each pushed
    head whose state file carries a clean `review` and status `waiting for checks` or `ready`
    (item 1's older-release rule), the rebuilt record lists that commit in `clean_reviews`, so a
    teammate without the old receipt still sees the PR ready. The upgrade test adds an open part with a pushed start commit and no
    PR, closed first on a second clone that never ran the upgrade: its PR record carries the
    rebuilt rounds and times. Rebuild rules, from the item's own evidence only:
    - rounds: each `Review of <item>: blocked|clean` commit on the item's branch (or in the squash
      merge's history) and its committed review result's findings, with new versus repeated by
      RECORD's rule;
    - building, fixing and reviewing: unknown. Commits are moments, not spans, and nothing older
      records when a worker or reviewer ran, so an item started Friday and reviewed Monday gets
      no weekend of working time;
    - waiting for CI: for each pushed head, its check runs from GitHub, from the first
      `started_at` to the `completed_at` of the last required check;
    - waiting for the owner's merge: from the last clean review with green checks to `mergedAt`;
    - anything else: unknown.
    The record (RECORD's format, whose `merged` keeps `rebuilt` once set) carries `rebuilt: true`
    and is written through
    `close.refresh_record` for open PRs and the same section rewrite for merged ones. The board
    shows "rebuilt from history" in that item's time detail and never counts a rebuilt unknown
    span as waiting. GitHub use: the batched PR list plus at most one check-runs request per
    pushed head of the items in the window. The code carries
    `# ponytail: one check-runs request per pushed head in the six-week window; batch through GraphQL if a repo has hundreds.`
    The skill.md "Upgrade Forge" step says the agent runs the backfill as part of the upgrade
    (nothing extra to type), that a backfill which couldn't reach GitHub retries on the next
    close, then opens the board and reports what is still missing.
    Tests: tests/test_board_after_upgrade.py (following tests/test_lanes_upgrade.py): copy
    tests/fixtures/adopted-v1.2.2/client pinned to the previous release with `merge = "human"`;
    add a story whose approval commit is by one author, a merged part whose start commit is by
    another, a fix merged 3 weeks ago with two committed review results whose branch is then
    deleted locally and on origin (origin keeps `refs/pull/<number>/head`, as GitHub does), a fix
    with one blocked and one clean review merged 2 weeks ago through an ordinary merge commit and
    one fast-forwarded, fixes merged 41 and 43 days ago, and an open fix closed clean on the previous release (green checks,
    no record); the clock (test shim) is on a Sunday so all three merged fixes fall inside the
    weekly searches; stub PRs with `mergedAt`, `mergedBy`, `author`, check runs and bodies without
    a record; run `forge upgrade`. The open fix's, the 3-week-old and the 41-day-old fixes' PR
    stubs get rebuilt records (the 3-week-old one with both rounds read from its deleted branch's
    pull ref, a CI wait and a merge wait; the merge-commit and fast-forwarded fixes with both
    their rounds too), the 43-day-old fix's gets none; `forge board --json`
    shows `started_by`, `approved_by`, `merged_by`, `merged_at` and the review gate for the older
    items, "rebuilt from history" times with building and reviewing unknown (no working seconds
    between the start and review commits), the 43-day-old fix's `time` null, pace counting the
    older merges, and the open fix in Needs you as a human merge; on a second clone without the
    old receipt, `forge board --json` and `forge next` both report the open fix ready to merge; a later close of the open fix
    on the new release still shows "rebuilt from history"; a rerun of `forge upgrade` writes
    nothing new; with the gh stub failing, the upgrade succeeds and prints the one line, and once
    the stub answers, the next `forge close` of another fix writes the missing records and the
    close after it fetches nothing more; with the stub failing only one PR body edit, the marker
    stays and the next close writes that record; the board added no commit. tests/test_board_guide.py: after `forge sync` in a new repo and in
    the upgraded repo, the installed skill's Upgrade Forge section says the upgrade runs the
    backfill and the agent then opens the board and reports what is missing, and its board
    section names `team` in place of `stage_counts`. Both tests belong to BACKFILL.
11. **Dependency graph.** `dependency_maps` covers every roadmap story, and each planned part
    gains `column`: 0 for a part that waits on nothing unfinished, else one more than the largest
    column among the unfinished parts it waits for, across stories (`KEY/TASK` waits), computed
    once in board.py over all maps together; parts in a wait cycle (within or across stories)
    share the earliest column they could take ignoring the cycle's own waits, keep `waits_for`, and
    are labelled "waits on each other"; a missing reference counts as no wait, with the reason in
    the label. Finished parts take no column
    and count into the story's `done` number. Stories with no plan get one entry with
    `planned: false` and no parts. Open fixes get one entry with `kind: "fixes"` whose parts are
    the open fixes, each in column 0, with `running`, and `started_on` naming the story part when
    the fix was started on that part's branch (a stacked fix; no wait, no arrow); merged fixes are
    left out. board_visuals.py draws one full-width inline SVG (no script):
    a row per planned story in roadmap order, its parts placed by `column` on a shared column
    grid, arrows from each part to the parts waiting on it (across rows too), running parts in
    solid ink with a "running" label, waiting ones thin, the "N done" mark at the row's start;
    the Fixes row drawn first, above the stories, a stacked fix labelled
    "started on <part>"; then the no-plan stories as a wrapping grid of small boxes with shortened titles, in roadmap
    order. Every shape has a text equivalent (title and desc), and the key line names the shapes.
    `# ponytail: longest-path columns over one graph; a smarter layout only if rows get crowded.`
    Test, tests/test_board_graph.py: two planned stories where B/T1 waits on A/T2, A/T1 and A/T3
    have no waits, A/T2 waits on A/T1, and A/T3 is running; one finished part in A; three
    no-plan stories. `forge board --json` gives columns A/T1 0, A/T3 0, A/T2 1, B/T1 2, A's done
    count 1, three `planned: false` entries; the page's graph has A/T1 and A/T3 in the same
    column, an arrow from A/T2 to B/T1, A/T3 labelled running, and three no-plan boxes; with an open running fix and a fix stacked on A/T2, the Fixes row
    shows both in column 0, the first labelled running, the stacked fix labelled "started on" A/T2 with no arrow,
    and a merged fix absent. A cross-story
    cycle case puts both parts in one shared column labelled "waits on each other". skill.md's board paragraph describes
    the graph and `column`.

12. **Getting around and telling items apart** (spec behaviour 4, from issue 702).
    - *Building only once a part started* (COUNTS): item 1's rule. Test, tests/test_board_counts.py
      `approved_not_started`: an approved story with no part started counts under "approved, not
      started" and not under building, on the page's totals line too; a fix merged on GitHub whose
      local state still says working shows done, never in progress.
    - *Blocking problems in Needs you* (WAITS): `nextstep.blockers(top, history) -> [{id, title,
      problem, next}]`, the one source `forge next` and the board both use for a malformed story
      doc (`story.parse`'s ValueError, such as an After naming a task missing from another story's
      plan) and a published-versus-local plan conflict (`story.plan_behind` and the reconciliation
      line). Each becomes a `team.needs_you` entry with `reason: "blocked plan"`, the problem in
      `forge next`'s words, and `since` the commit date of the plan's last change on the ref read
      (null when unknown); it clears when `forge next` no longer reports it. Test,
      tests/test_board_needs_you.py `blocking_problems`: a story whose After names `OTHER/MISSING`
      and a story whose local plan conflicts with its published one both show in Needs you with
      the text `forge next` prints, and leave once fixed.
    - *Plain times* (RECORD): one helper, `time_records.plain(seconds) -> str`, rounds to the
      largest sensible units ("15 seconds", "4 minutes", "2 hours 10 minutes", "3 days"), and every
      time a person reads uses it: round lines, How it went, the page and the pane (PANE makes
      summary.ts's `seconds()` follow the same rounding). JSON keeps raw seconds. Test,
      tests/test_board_how_it_went.py `plain_times`: a 15.001-second review stage reads "15
      seconds" in the round line and the PR body, and no rendered text matches `\d+\.\d+ ?s`.
    - *Section bar, folds, keys and history* (NAV): a `<nav>` with `position: sticky; top: 0`
      links to `#overview`, `#roadmap`, `#stories` and `#fixes`; each section is a `<details>`
      (Overview open by default, the others open too unless the page is long: Stories and Fixes
      start folded when they hold more than 20 rows), no script, no separate pages. There is no
      grouping: the graph shows planned stories in roadmap order, then no-plan stories in roadmap
      order, and the Stories section sorts them by
      state (item 8's order). Each story's key follows its
      title in `<span class="key">` (small, muted ink); this is the one exception to the no-IDs
      rule, so NAV also changes the shipped line in src/forge/templates/adapters/AGENTS.md to
      "no IDs, hashes or jargon …, except story keys shown small beside titles on the board".
      A story's history lists, in order, each cold-read round from `plans/<KEY>.read.md` (round
      number, its findings' titles or "No findings", and each disposition: cut, defer or keep with
      its reason; the latest round dated by `read_at`, earlier ones undated), then its approval and
      merged parts. Tests: tests/test_board_sections.py, on a fixture of 25 stories: the nav's four
      links resolve to four folding sections, stories appear sorted by state with no group
      headings, every story title is followed by its key in the muted span, and Stories starts
      folded; tests/test_board_story_history.py:
      a story with three read rounds (one with a cut and a keep) shows all three with their
      dispositions before its approval line; tests/test_board_keys_rule.py: after `forge sync` in a
      new repo and in a repo adopted on the previous release, AGENTS.md carries the new line.

### The Runway (binding for PAGE, RUNWAY, NAV, GRAPH and PANE)

The builders use the **impeccable** and **emil-design-eng** skills. PAGE's first commit runs
impeccable's init to write PRODUCT.md at the repo root for the board surface (the repo has none);
RUNWAY, NAV and PANE start after it and read it.

- **Personality:** calm, precise, trustworthy. Anti-goal: a generic SaaS dashboard.
- **Time axis:** one shared axis across the first screen with a vertical "today" line. Needs you
  rows end at today with an amber wait bar reaching left for the length of the wait, the wait
  written in words (an unknown wait has no bar and says "waiting, since unknown"). Building
  stories are runways from their start to today: solid ink where working, thin where waiting, a
  gap with a dotted hairline where unknown, labelled "5 of 8 parts done · started by …". Open
  fixes are thinner runways. Blocked rows carry their reason in words. Go-live is a soft range
  band on the future side, or one tick for "about", with the no-plan count beside it. The past
  side reaches back to the oldest visible start, clipped at six weeks with "started N weeks ago"
  at the edge.
- **Summary:** one calm sentence on top (`team.sentence`). The spec's "number tiles" become a quiet
  line of labelled totals, not tiles.
- **Palette:** near-white paper, ink text, hairline rules. A single amber accent means "waiting"
  and nothing else. Through and around Forge in the trends are two tones of ink, never amber. No
  cards, shadows, gradients, rounded boxes or tile grids.
- **Type:** one precise system sans-serif stack, `font-variant-numeric: tabular-nums` wherever
  numbers appear. No web fonts; the page stays self-contained.
- **Themes:** light first; dark designed too, with its own tokens under
  `prefers-color-scheme: dark`, keeping AA contrast. Colour never carries meaning alone.
- **Layout:** full width at 1440×900 with the first screen fitting 900px. Below 720px one column;
  each runway becomes a text row with its bar underneath.
- **Interaction:** detail opens in place with native `<details>`. No script, no external asset,
  no motion beyond the browser's default.
- **Drawing:** bars are inline SVG via `board_visuals._svg` (role img, title, desc) or positioned
  spans, each with a text equivalent.
- **Pane:** the same words and order in plain text.

### Browser proof (binding for PAGE, RUNWAY, NAV and GRAPH)

The page must look finished, not merely correct: calm, aligned, with clear hierarchy and nothing
cramped, clipped or overlapping. Each of these parts proves in a real browser, before its close,
what it delivers, on the page as it stands at that point; a check on something a later part
builds waits for that part, and GRAPH, the last part to change the page, runs every check on the
finished page.

- Render `forge board` on two real repos (this repo, and a client-sized fixture shaped like issue
  702's: at least 40 stories, 120 parts, 10 open and 50 finished fixes and 6
  weeks of merges) and open each page in headless Chrome
  at 1440×900 light, 1440×900 dark (`prefers-color-scheme: dark`) and 390×844.
- Every part checks: no horizontal scroll at any width; no text overflowing or overlapping its
  box; text meets WCAG AA contrast in both themes; every `<details>` it adds opens in place and
  closes again.
- PAGE also checks: the full laptop width is used; one column at 390 wide; the done fold opens
  and closes.
- RUNWAY also checks: the first screen fits 900px with no scroll; "and N more" and each row's
  detail open in place; keyboard Tab reaches every row with a visible focus ring; the amber
  accent meets AA in both themes; the trends rows and around-Forge list stay aligned.
- NAV also checks: the section bar stays pinned at the top while scrolling and each link lands
  on its section; every section folds open and shut; with every section folded, the client-sized
  page is under three screens tall (2,700px at 1440×900, 2,532px at 390×844).
- GRAPH also checks: the graph stays readable at the fixture's size (labels not colliding,
  arrows not crossing labels), and at 390 wide no graph line crosses a story or part title; then
  every check above again, the folded height included.
- Run impeccable's critique and audit on the rendered page and fix every issue they raise
  about hierarchy, spacing, alignment, contrast or anti-patterns before closing.
- Commit the screenshots under `docs/board-screens/` (in each of these parts' Scope; PNG is the
  only binary allowed there), named by part and window, e.g. `runway-1440-dark.png`, link them in
  the proof list, and list each browser check with its result.
- The coordinator then has an Opus subagent review those screenshots as a project manager
  opening the board cold (what is happening, what needs me, what is stuck, when do we go live)
  and as a designer; its blocking findings go back to the worker before merge, and the owner
  sees the screenshots before the part merges.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| RECORD | How it went travels with the pull request | The shared record (intervals, rounds, waits with their ends, clean reviews, the rebuilt label kept by every merge), `from_body`, `merged` with recomputed round classes, `refresh_record`, close and merge publishing the merged record, story runways, the board reading the merged record, the GitHub-merge end, `merged_by`, `time_records.plain` for every time a person reads, the guide's How it went paragraph | 5, 12 | src/forge/time_records.py, src/forge/close.py, src/forge/merge.py, src/forge/board.py | tests/test_board_how_it_went.py | | no | |
| COUNTS | Shared counts | board_facts.py pinning the full `team` schema (later keys null), `full_weeks`, counts with `story.gate` and "approved, not started", `review_ref`, readiness against it from the receipt or the shared clean reviews, the next step when only the shared record makes an item ready (a plain line naming the starter without the worktree, `forge close` with it), the older-board fixture snapshot, `_prs` as cached weekly searches with the cap rule, `approved_by` as a name, `stage_counts` removed, the guide's JSON contract and readiness paragraphs | 1, 12 | src/forge/board_facts.py, src/forge/board.py, src/forge/nextstep.py, tests/test_board_status_and_times.py, tests/test_machine_views.py, tests/test_machine_views_recent_finished_items.py, tests/fixtures/board.json, tests/fixtures/board-previous.json | tests/test_board_counts.py, tests/test_board_github_once.py | RECORD | no | |
| WAITS | Needs you and Blocked or slow | Needs you from every wait record, Blocked or slow, `review.blocked_rounds` with its start, close publishing the stop, the choice and the conflict wait (opening the pull request on a first close), forge work publishing a question and its answer, `nextstep.blockers` in Needs you, the sentence without go-live, the guide's Needs you and Blocked paragraph | 2, 3, 12 | src/forge/board_facts.py, src/forge/review.py, src/forge/close.py, src/forge/worker.py, src/forge/nextstep.py | tests/test_board_needs_you.py, tests/test_board_blocked.py | COUNTS | no | |
| BACKFILL | The upgrade rebuilds older time stories | backfill.py with the rebuild rules (unknown where only commits exist, original commits from each PR's pull ref, the exact 42-day cut), run as the last step of closing an upgrade fix, idempotent and quiet without GitHub with the next close retrying, "rebuilt from history" on the board, the guide's Upgrade Forge step, the upgrade and guide tests | 10 | src/forge/backfill.py, src/forge/close.py, src/forge/board_facts.py | tests/test_board_after_upgrade.py, tests/test_board_guide.py | TRENDS | no | |
| TRENDS | Pace, go-live and trends | Pace, go-live in its order and the sentence's go-live clause, team and per-person trends, the around-Forge list, the guide's pace and trends paragraph | 4, 6 | src/forge/board_facts.py | tests/test_board_pace.py, tests/test_board_trends.py | WAITS | no | |
| PAGE | The page's new frame and lower half | PRODUCT.md through impeccable init (first commit), rendering from the untrimmed derivation, the old card page removed, the new board.html frame with light and dark tokens and one column when narrow, the key and sorted rows with done folded, its browser proof | 8 | PRODUCT.md, src/forge/board.html, src/forge/board_visuals.py, src/forge/board.py, tests/test_board.py, tests/test_board_dependency_timelines.py, docs/board-screens/ | tests/test_board_runway.py, tests/test_board_dependency_timelines.py | COUNTS | yes | |
| RUNWAY | The Runway first screen and trends | The time axis with wait bars, runways and the go-live band, the totals line, the five-row lists with "and N more", in-place detail, the trends rows and the around-Forge list, the guide's board page paragraph, its browser proof | 6, 7 | src/forge/board_visuals.py, src/forge/board.html, docs/board-screens/ | tests/test_board_runway.py | PAGE, TRENDS | yes | |
| NAV | Getting around the page and story histories | The pinned section bar and folding sections, story keys beside titles and the shipped AGENTS.md line, story histories with cold-read rounds and their dispositions, its browser proof | 12 | src/forge/board.html, src/forge/board_visuals.py, src/forge/board.py, src/forge/templates/adapters/AGENTS.md, docs/board-screens/ | tests/test_board_sections.py, tests/test_board_story_history.py, tests/test_board_keys_rule.py | RUNWAY | yes | |
| GRAPH | The dependency graph of every story | `column` and `planned` in `dependency_maps` across every roadmap story, the full-width graph SVG with cross-story arrows, running marks, done folds and no-plan boxes, skill.md's graph paragraph, the full-page browser proof | 11 | src/forge/board.py, src/forge/board_visuals.py, tests/fixtures/board.json, docs/board-screens/ | tests/test_board_graph.py | NAV, PANE | yes | |
| PANE | The pane's first-screen lines | `teamLines` in summary.ts, the Board tab and `/forge` text starting with them, `team` optional in forge.ts, `seconds()` rounding like `time_records.plain`, the guide's pane paragraph | 9 | src/forge/mod/hooks/summary.ts, src/forge/mod/hooks/pane.ts, src/forge/mod/hooks/forge.ts | tests/test_board_pane_lines.py | TRENDS | yes | |
New moving parts: none

## Notes

- Client issue 702 (2026-10-10, filed on v1.2.9): one 32,000-pixel page, a cramped 340-pixel
  graph with lines through titles, no navigation, Building overcounted by approved stories with no
  part started, a merged fix still "In progress", raw "15.001 seconds", blockers that `forge next`
  reports missing from the board, and story histories without cold-read rounds. Owner decisions
  (2026-10-10): no patch now, this story covers it (Done when 1, 2, 11 and 12); a pinned section
  bar with folding sections over separate pages or script filters; story keys shown small and muted beside titles as the one
  exception to the no-IDs rule (the spec fix changes this repo's principle 11; NAV changes the
  shipped AGENTS.md line). Correction (2026-10-10): no epics and no grouping at all; the graph
  shows stories in roadmap order and the Stories section sorts them by state.

- Owner direction (2026-10-10): make the board visually appealing and test it properly in a real browser; see Browser proof.
- Owner decision (2026-10-10): the upgrade's last step rebuilds the time story of every open item
  and every item merged in the last six weeks that has none, from its commits, committed review
  results, its PR's check runs and merge time, writes it into the item's PR record marked as
  rebuilt from history, and leaves spans with no evidence unknown; the agent then opens the board
  and reports what is still missing (this replaces "the upgrade writes nothing"). No new command:
  it runs inside the upgrade.
- Owner decision (2026-10-10): the dependency graph shows every roadmap story, with parts in columns by when they can start so parallel work is visible, and each no-plan story as its own box (over building stories only).
- Owner decisions (2026-10-09): rebuild the board around the questions a project manager, lead and
  developer ask (over "don't build" and "fix the wrong data only"); share each item's time story
  through its pull request, not committed records or local only; team
  and per-person trends with no ranking (the spec amendment); the "Runway" visual design, binding
  for the user-facing parts; frontend parts build on Claude Opus (workers = split).
- Coordinator rulings on the first read (2026-10-10): waiting for approval uses `story.gate`;
  readiness travels in the shared record; close and the board merge the PR record with local logs;
  story runways are pinned; conflict, loop-choice and question waits are published to the PR;
  older ready PRs show with an unknown wait; GitHub reads are two date-windowed cached calls with a
  cap rule; the page renders untrimmed; go-live checks "not enough history" first; the looping
  duration starts at the first consecutive blocked round. Second read: waits carry an end and are
  never dropped; readiness compares with the PR's head; merged pull requests are read one week per search; rounds are reclassified after a
  merge; each task updates its own guide paragraph; an older board without `team` is tested.
  Third read: clean reviews are a merged list; readiness and review history read the PR's head
  unless the local branch is ahead; a first-close conflict opens its pull request (only a pre-PR
  worker question stays local); `forge merge` still needs a local receipt; COUNTS snapshots the
  older board fixture. Fourth read: an item ready only through the shared record shows, on a
  machine without its worktree, a plain line naming the starter who merges it (no command), and
  `forge close` where the worktree exists. Taking over another person's item stays out of scope:
  starting is the claim, and task start refuses an item someone else started. Ninth read: the backfill leaves commit-to-commit spans unknown, reads
  squash-merged items from their pull refs, cuts at exactly 42 days and retries on the next close;
  the record keeps the rebuilt label; blocks the most includes approved stories not yet started;
  the page work splits into PAGE and NAV, each proving its own share in the browser. Tenth read: the rebuild walks
  back to the item's start commit (any merge type), carries older clean reviews into the record
  so readiness survives, and keeps the retry until every record is written.
- Depends on these landing first:
  - fix/board-data-truth: one shared derivation for statuses; roadmap-done stories done; finished
    items never stalled and `idle_since`/`idle_seconds`/`stalled` for unfinished ones; running
    workers and reviews shown running; ready, plan-read and waiting-for-approval stages matching
    `forge next`; merge dates from GitHub; stories and fixes counted apart (`kind_stage_counts`,
    replaced here by `team.counts`); one display name per person; titles shortened at a word.
  - fix/where-time-went: review findings, CI-wait outcomes and lane joins and leaves in the logs;
    `time_records.item` with an 8-category `time_breakdown` and round lines counting new versus
    repeated findings; owner-wait events for review-loop choices and human merges; the total
    ending at GitHub's `mergedAt`; How it went written by close and refreshed by `forge merge`.
  - fix/queued-not-stop: no board fact; a CI wait on a busy runner pool keeps waiting instead of
    stopping, so "waiting for CI" intervals are whole. This story touches none of its files.
  - fix/spec-trends: the amended spec (trends) lands and is confirmed before approval.
- Builder readings pinned here: weeks are Monday-to-Monday UTC; "fewer than three weeks of merges"
  means the oldest merged part is less than three full weeks old; migrate's one-off adoption pull
  request counts as around Forge (the spec names only story, part and fix branches); approval
  applies to stories and their parts, not fixes; the pane keeps its live rows below the new
  summary lines; "nothing running" time counts as unknown, not waiting.
- Forge shrinks: this story removes the old card page and its second derivation of statuses and
  times, `stage_counts` and `kind_stage_counts`, merge.py's own body rewrite, and the uncached
  GitHub calls on every `forge board --json`. It adds two modules (board_facts.py, and
  backfill.py, which runs only inside an upgrade) and one cache file following the existing
  checks-cache pattern, plus a local marker while a backfill waits to retry. board.py drops below 900 lines;
  board_facts.py, board_visuals.py and time_records.py each stay under 600. No new commands.
- Human touches: one, the story approval (this repo merges with `merge = "agent"`).
- Guides: each task updates its own skill.md paragraph in the same change; brief.md is unchanged
  (workers neither read nor change the board; forge work publishes questions itself).
