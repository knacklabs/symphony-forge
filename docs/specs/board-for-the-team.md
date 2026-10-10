---
slug: board-for-the-team
title: The board tells a team what's happening, what needs them and when it goes live
status: draft
saved: 2026-10-10T07:41:25+00:00
---

# The board tells a team what's happening, what needs them and when it goes live

## Why

A project manager or team lead opening the forge board today can't use it. Two reviews of a real client board (October 2026) found:

- The first screen shows finished work and a narrow map; about half of a laptop screen is empty.
- 119 "Not started yet" story cards come before the four stories actually in progress; open fixes are last.
- Counts mix stories and fixes and contradict the cards ("Waiting for approval: 0" while a card says it waits).
- Nothing says what's blocked, who owns what, what needs a person, or what to look at first.
- There's no pace and no forecast. Counting by hand: 38 planned parts left, while parts finished per week fell from 13 to 4 to 2, and 132 stories have no plan at all.
- Most of an item's time is waiting (CI, the machine's queue, a person's answer), not work, and the board never shows waiting.

The people who open the board and what they need:

| Who | Needs |
|---|---|
| Owner or project manager | Are we on track, when can it go live and how sure, what needs me, what's at risk, what shipped, and how much of the team's work goes through Forge versus around it |
| Lead | What can start now, who is working on what, what blocks the most, which plans wait for approval |
| Developer | What's mine, what waits on me, what to pick up next |

## Behaviour

The board answers those questions in order on the team's own machines (each person's `forge board` after a fetch, and the Claude Code pane), from one shared derivation that also feeds `forge board --json`. The HTML board is the full view; the pane shows only the first-screen summary lines.

**Where the facts come from.** Facts in git and GitHub reach every teammate: stories, parts and fixes and their states, who started each item (the author of its start commit, pushed when it starts), who approved a story (the approval record), pull requests, merges, checks and review results. Each item's time breakdown and round history is written into its pull request's "How it went" section by every close and again when `forge merge` merges it, so every board reads it from GitHub; when a person merges on GitHub instead, the board ends that last wait at the pull request's merge time from GitHub. A story's plan reads are already in its committed read notes. A worker question asked before the item's pull request exists shows on the asking machine until the next close publishes it. Live facts (what is running on a machine right now and the machine's queue) stay on that machine and show only there. Anything not available from these sources shows as unknown, never guessed.

**Counting.** Each item has exactly one state, taken from the first rule that matches. A story is *done* when its last part has merged or the roadmap marks it done; else *building* once its plan is approved and at least one of its parts has started; else *approved, not started* once its plan is approved; else *waiting for approval* when its plan has passed its reads; else *planning* when a plan draft exists; else *no plan yet*. A part or fix is *done* when merged; else *ready to merge* when `forge next` calls it ready (the same shared rule: a clean review of its current commit and checks not failing); else *in progress* once started; else *to do*. *Finished* always means merged. Stories, parts and fixes are counted separately, never added together.

1. **First screen** (a 1440 by 900 laptop window, no scrolling; each list shows at most five rows, oldest or most urgent first, with "and N more" opening the full list below):
   - Number tiles: stories by state; parts of approved stories by state; open fixes by state; parts and fixes finished in the last 7 days.
   - **Needs you:** items waiting on a person: a plan waiting for approval, a problem `forge next` reports as blocking work (a malformed story doc, a published plan that conflicts with the local one), a review-loop choice, a pull request waiting for a human merge, an unanswered worker question, a merge conflict close stopped on. Each wait starts at the record that created it and ends at the record that cleared it, and the row shows how long it has waited.
   - **In progress:** one bar per building story ("5 of 8 parts done") and one row per open fix, each with who started it and its age since start.
   - **Blocked or slow:** started, unfinished parts and fixes with no recorded activity for 24 hours or more (stalled; items whose activity can't be seen from this machine or GitHub are left out rather than guessed); items whose review has been blocked three or more rounds; and the not-yet-done part with the most not-yet-done parts depending on it, directly or through others. Each row gives its reason and how long.
   - **Pace and go-live estimate:** parts and fixes merged per week for the last six full weeks, from merge dates in git. The estimate covers only parts of approved stories that are not done: remaining parts divided by the average weekly parts merged over the last three full weeks, and over the last six, giving the earlier and later end of a date range. With fewer than three weeks of merges, or none in the last three weeks, it says "Not enough history to estimate" instead; with nothing remaining it says the planned work is done; when both rates give the same date it shows that one date as "about" with "the two pace estimates agree". Stories with no plan yet are counted beside it as the unknown that decides go-live.
2. **Below the fold:** a full-width dependency graph of every roadmap story. Each story with a plan shows its parts in columns by when each can start: a part sits one column after the latest part it waits for, so parts in the same column can run in parallel; parts that wait on each other in a loop, within or across stories, share the earliest column they could otherwise take and are labelled as waiting on each other. Arrows show what waits on what, within a story and across stories; parts running now are marked as running; finished parts fold into one "N done" mark per story. Each story with no plan yet is its own small box, in roadmap order, after the planned stories. Open fixes sit in one Fixes row at the top, in the first column since they wait on nothing, marked running or waiting and, when a fix was started on a story part's branch, labelled "started on" that part, with no arrow since it waits on nothing; merged fixes are left out. Then story and fix cards sorted needs-you, blocked, in progress, planned, no plan yet, done, with done work folded away.
3. **Each item:** its time split into working (a worker, reviewer or reader running, or Forge's own tests) and waiting (for CI, for the machine's queue, or for a person), each interval counted once by its recorded start and end; time with no record either way shows as unknown rather than as waiting. One line per review round says what the round did and whether its findings were new or repeated from an earlier round (the same requirement named again). Who started it and who approved it are shown as recorded, or unknown.
4. **Getting around and telling items apart:** a bar pinned to the top jumps to Overview, Roadmap, Stories and Fixes, and every section folds open and shut, so the page never has to be scrolled end to end. The Roadmap graph and Stories section group stories by their roadmap epic, or by their source spec when they have no epic; stories with neither stay in an Ungrouped section. Groups follow the first story's roadmap order. The graph shows all planned stories before all stories with no plan, with groups in each set and stories within each group in roadmap order; dependency columns and arrows still span groups. The Stories section sorts stories within each group by state. Each story shows its key small and muted after its title, so near-identical titles can be told apart. A story's history lists its plan's cold-read rounds, what each found and how it was handled, as well as its approval and merged parts. Times read in rounded plain units, never raw seconds.
5. **Words a newcomer understands:** plain labels and a one-line key for the map's shapes and the words part, fix and plan.
6. **Team and per-person trends:** below the fold, merged pull requests per week for the last six full weeks, for the team and for each person (the pull request's author on GitHub), each week split into *through Forge* (from a story, part or fix branch) and *around Forge* (any other merged pull request). People are listed by name in alphabetical order with no totals ranking, scores or comparison between them; the trend shows each person's own weeks only. Beside it, a list of the pull requests merged around Forge in the last 7 days, each with its title, author and merge day.
7. **After an upgrade** the board reads who started, approved and merged each older item, and its review results, straight from git and GitHub, so items from earlier releases show those facts at once. As the upgrade's last step the agent runs Forge's backfill, which rebuilds the time story of every open item and every item merged in the last six weeks that has none: working and waiting intervals and review rounds, from the item's commits, its committed review results, its pull request's check runs and its merge time. It writes each into the item's pull request, marked as rebuilt from history, so every teammate's board shows it; an open item with no pull request yet is rebuilt the same way by its first close, on whichever teammate's machine that close runs, since the rebuild uses only git and GitHub; spans with no evidence stay unknown, never guessed. Older items, and anything when GitHub can't be reached, show as unknown. The agent then opens the board once and reports what is still missing.

Options weighed: **Don't build** (the board stays unusable for a team; rejected by the owner); **Smallest slice** (fix the wrong data only: counts and statuses become right, but nobody sees what needs them or can forecast; this is the first part, already in flight); **Rebuild the board around the questions above** (chosen by the owner, 2026-10-09: a project manager must see the total status and estimate go-live). On sharing time records across machines the owner chose the pull request over committing records to git or keeping them local. The owner also chose (2026-10-09) team and per-person weekly trends of merged work through Forge and around it, each person shown against their own weeks only, never ranked. The owner chose (2026-10-10) that the upgrade's agent backfills the time story of open items and items merged in the last six weeks, over leaving them unknown. After a client's issue on v1.2.9's board (one 32,000-pixel page, a cramped graph, an overcounted Building, missing blockers), the owner chose (2026-10-10) a pinned section bar with folding sections over separate pages or script filters, and story keys shown small beside titles as the one exception to the no-IDs rule. The amended fix requires grouping stories by roadmap epic, otherwise by source spec. The owner chose (2026-10-10) to show open fixes as one row in the graph so all parallel work is in one picture. The owner chose (2026-10-10) a dependency graph of every roadmap story, showing which parts can run in parallel, over a map of building stories only.

## Out of scope

- Showing the board to people outside the team's machines (a phone link or a client view); a narrow window still gets one column.
- Ranking, scoring or comparing people; per-person trends show each person's own weeks only.

## Acceptance criteria

1. In a 1440 by 900 window the board's first screen, without scrolling, shows the labelled totals and at most five rows each of Needs you, In progress (stories and fixes) and Blocked or slow, plus Pace with the go-live range or its "not enough history" note; longer lists continue below.
2. Every count, status and time agrees with `forge board --json` and `forge next`, and stories, parts and fixes are counted separately.
3. Needs you lists every item waiting on a person with its wait time; Blocked or slow lists stalled and looping items and the part that blocks the most, each with a reason.
4. The go-live estimate gives a date range from recent pace for planned parts (or "about" one date when the two pace estimates agree, "not enough history", or "planned work done") and names the stories with no plan as the unknown.
5. Each item shows where its time went (working versus waiting), one line per review round, and who started and approved it.
6. The page uses the full width of a laptop, reads in light and dark mode, and stacks to one column in a narrow window.
7. Below the fold, the dependency graph shows every roadmap story: planned stories' parts in columns by when each can start, so parts that can run in parallel share a column, with arrows for waits within and across stories, parts waiting on each other in a loop sharing one column labelled as such, running parts marked, finished parts folded into "N done", and every story with no plan as its own box, with open fixes in one Fixes row at the top marked running or waiting.
8. Below the fold, the team and each person show merged pull requests per week for the last six full weeks, split into through Forge and around Forge, with people in alphabetical order and no ranking, and the pull requests merged around Forge in the last 7 days are listed with title, author and merge day.
9. A pinned bar jumps to Overview, Roadmap, Stories and Fixes and every section folds; the Roadmap graph and Stories section group stories by roadmap epic, otherwise by source spec, with stories lacking both in Ungrouped; each story shows its key small beside its title; a story's history lists its cold-read rounds; times use rounded plain units; a story counts as building only once a part has started; and Needs you lists the blocking problems `forge next` reports.
10. Right after an upgrade, older items show who started, approved and merged them and their review results from git and GitHub, and every open item and every item merged in the last six weeks shows a time story rebuilt from history and marked as rebuilt (for an item with no pull request yet, once its first close publishes it); what can't be found is unknown, never invented.

## Roadmap

- FORGE-BOARD-2: The board tells a team what's happening, what needs them and when it goes live

## Success measure

- Metric: questions a first-time viewer answers correctly within one minute from a real client repo's board page (what is in progress, what needs a person, what is blocked and why, the go-live range for planned work)
- Baseline: 0 of 4 (first-time-viewer review of a real client board, 2026-10-09)
- Target: 4 of 4, each matching the repo's real state
- Check date: 2026-11-15
