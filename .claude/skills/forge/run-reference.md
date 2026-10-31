# Run reference

Open this file for machine queues, board JSON fields and the Claude Code pane.

## Machine views

Forge gives agents half the available cores (at least one place), across all repos. Work rounds
share a line. Plan reads and close reviews take no place in that line. Every run, including
tests, reviews and plan reads, waits while the machine's
one-minute load per core is 1.5 or more, even when no other Forge run is active; where the OS reports no load
(Windows) the memory and core budgets still apply. Waiting items that other planned work waits on go
first, first-come within each group; each waiting run says its place and why. The test
lane makes all test runs share one process budget: the cores left after the agent share and busy
local CI jobs, with at least one process. Small selections count too. Each run takes its allocation
from the remaining budget. A worker's test runs use at most two processes. Nested pytest pickers
keep the parent run's allocation. Older-release entries without an allocation count as the old
default share, half the machine's cores. `forge doctor` names these older runs and shows both lane
budgets, free memory and its floor, test processes in use, and busy runners.
Every run waits when free memory is below 1.5 GB or ten percent of RAM, whichever is larger.
An unreadable memory source does not block work. Each busy local `Runner.Worker` reserves one core
from Forge's half-core budget, with at least one core left for Forge. Waiting runs check memory
and runner use again on each pass and start when capacity returns. On Mac and Linux, doctor warns when a GitHub Actions self-hosted runner
runs on this machine: its CPUs count against Forge's load limit.

`forge board --json` includes both machine-wide lanes, their sizes and entries in queue order,
alongside OS load and memory. Each entry has an `id`, `kind`, `repo_root`, `repo_name`, `item`,
`model`, `effort`, `joined_at`, `started_at`, `process`, `output_path` and `progress`.
Waiting entries have no start time. Test output and progress are null until the test runner sets
them. The process includes its pid and start identity; a reused pid cannot hold an old place, but
the run keeps it while its own Forge process runs.

Only a person runs `forge stop <item>` (optionally `--repo <root>`) to stop that item's entries in
both lanes, or `forge stop --id <id>` to stop one entry. The host asks for confirmation first.
Workers never run it. A waiting run leaves the line; a running run's verified process tree ends
before its place is freed. An unverifiable identity refuses without terminating anything.
Stopping an item also clears its abandoned item lock when no live run holds it, so the next
round can start even when the coordinating session stays open.
This applies to runs Forge launched. A handed-out native run has no process tree, so
`forge stop` frees its hold and the coordinator stops the subagent in its session.

In Claude Code's Forge pane, the Machine tab shows this release's agents and test lane across
repos, who waits next, local item gates, and machine load when the OS provides it. Desktop draws
an agent tree; narrow terminals use a list. Select a run, press `o` for its last 200 output lines
or `s` to ask the person whether to stop that exact run. A run that ends or is replaced during
confirmation is not stopped. Press `l` to show or hide recent events. The spinner names this
session's place in line. `/forge` includes the machine summary where panes cannot draw.
Lanes record each item's title when it joins, so other repos' stories and tasks keep their
plain names in rows, selectors and stop confirmation. Only this repo's board adds tool,
round, current step and gates.
`forge lanes --json` supplies the Machine tab; other releases still count towards admission but
are left out of its rows. New repos receive the mod on setup; existing repos receive it on
upgrade and `forge sync`. An unreadable output or a failed refresh is explained in the pane;
failed refreshes keep the last rows. The mod adds no background work or dependencies.

`forge board` opens the board as a live page on this computer: a server on 127.0.0.1 at a free
port, with a per-run token in the page address that every request must carry, so no other computer
and no old link can open it. The page refreshes by itself when the work changes, and the server
stops when the command ends (Ctrl-C). It rebuilds only the rows whose inputs changed and fetches
from GitHub at most once a minute. `--out <path>` writes every item's facts as JSON instead,
finished ones included.

`forge board --json` and `forge next --json` print JSON for the Claude Code mod and
other readers. The usual commands still print text. Both views
include `version` (the running Forge release) and `repo_root` (the resolved main
worktree path, shared by the repo's worktrees).
`forge next --json` uses the same 60-second GitHub cache as `forge board --json`, while text
`forge next` reads GitHub live.
Pull request creates, edits and draft changes keep this shared cache. They show within a minute.
Merges clear it at once. Each command fetches the default branch's settings at most once.
After close, a matching receipt still shows "ready to merge" while the cached list lacks the pull request's link.

Both views' `items` has one row per story and fix, with tasks in the story's `children`.
Finished stories, tasks and fixes older than seven days are left out of `--json`;
`--out` keeps them. The live page reads the same rows, so each state and time on it matches the
JSON. Each story shows its key small beside its title, the one ID on the board. Story rows carry
`read_rounds`: each cold-read round of the plan with its number, its findings' first lines and
their dispositions (`cut`, `defer` or `keep` with its `reason`), and `read_at` on the latest round
only. Each call reads current state without a history cache.
Assigned merged parts stay omitted rather than appearing as unstarted. Backticks around
task IDs in the plan are ignored by the board.
`forge board --json` supplies `dependency_maps`: one entry per roadmap story
with `planned` (false for a story with no plan yet, which has no parts), `done` (its finished
parts) and its full planned parts, plain titles, labelled states and `waits_for` item references,
including old merged dependencies omitted from active rows. Each unfinished part has `column`:
0 when it waits on nothing unfinished, else one more than the largest column it waits on, across
stories, so parts in one column can run at the same time; parts that wait on each other share a
column and say so in `note`. Finished parts have a null `column`. When fixes are open, an entry
with `kind: "fixes"` lists them in column 0 with `running` and `started_on` (the story part a
stacked fix was started on). Startability and scope
blockers come from the same rules as `forge next`, including approval and required rereads.
Both views add `team`: `sentence`, `counts`, `needs_you`, `in_progress`, `blocked`, `pace`,
`go_live`, `trends` and `around_forge`; a key not worked out yet is null. Every story, part and
fix row has one `state`, and `team.counts` counts each kind apart, finished ones included:
`stories` (done, building, approved but not started, waiting for approval, planning, no plan yet),
`parts` of approved stories and `fixes` (done, ready to merge, in progress, to do), and
`finished_last_7_days`. A story is building only once one of its parts has started. Rows also
carry `merged_at`, and `approved_by` is a name or null.
GitHub's pull request lists are read at most once a minute: the open ones and one search per
week for the last six full weeks and this one.
`team.pace` counts parts and fixes merged on the default branch per full week (Monday to Monday
UTC) for six weeks. `team.go_live` gives a date range for the parts of approved stories still to
merge, from the last three and six weeks' pace: `range`, `about` when the two agree, `not enough
history` when the oldest merged part is under three weeks old or the last three weeks merged none,
or `done`; it counts the stories with no plan yet as the unknown, and `team.sentence` says the
same in a count, not names. `team.in_progress` lists the stories and fixes in
progress (`id`, `title`, `kind`, `state`). `team.trends` counts merged pull requests per week for the team and each person
(alphabetical, no totals or ranking), split into through Forge (a `story/`, `task/` or `fix/`
branch) and around it; `team.around_forge` lists the ones merged around Forge in the last 7 days.
Both are null without GitHub, and a week capped at 1,000 results is null.
`team.needs_you` lists every item that waits on a person, oldest first, each with its `reason`,
`since` and `waited_seconds`: `approval` (a plan waiting for approval), `review loop` (a review
loop or stuck-worker choice), `worker question`, `conflict` (a merge conflict close stopped on),
`merge` (a ready pull request a human merges) and `blocked plan`, with the question or the
problem `forge next` reports in `detail`. Close and `forge work` publish
these waits to the pull request, so every machine lists the same ones; answer a worker question
with `forge work <item> --note` on any machine. `team.blocked` lists started parts and fixes
idle 24 hours or more (`stalled`) and the unfinished part the most unfinished parts wait on
(`blocks the most`), longest first, each
with `detail` and `seconds`. `team.sentence` counts both. Ask the human about each Needs you
item as `forge next` words it.
Active parts and fixes show recorded
Build, Tests, Review, CI and Merge times for their current round, with the current stage
marked. Missing times remain unknown. New clients get this at init; earlier adopted clients
get it after upgrading Forge and syncing. Cards and JSON use the same `status` and `took`
derivation; running stages include their elapsed time. Roadmap completion marks the story
and its parts finished. Finished items never stall; idle items past one day expose
`stalled`, `idle_seconds`, and `waits_on`. A story's idle clock includes its parts' activity;
a running part keeps the story active and a finished part resets its idle clock, including
a merge reported by GitHub before its commit is fetched. An older
worker round or a worker whose recorded lock is demonstrably dead is not a live run.
Live readers, workers and reviews take precedence
over a saved status, including in `forge next`. Approval history uses one display name per
Git email, honoring mailmap, and fix titles shorten at a word boundary.
Each row has `id`, `kind`, plain `title`, `stage`, `worker` (kind, model and
`started_at`, or null), `pr` (number, url and checks: pass, fail, running or unknown),
`findings` (count and titles), `round`, `stages`, `total_seconds`, `occurrences`,
`approval`, `needs_person`, and its own `next`. `needs_person` is true while the item waits on
a person, by the same decision as `team.needs_you`.
A story awaiting approval has `approval.doc`, the
absolute path to its document in its own worktree; other rows have null approval.
Task and fix rows add `time_breakdown` and `rounds`; story rows add `outcome` (null until done).
An empty board has an empty items list. Missing state shows unknown. No run start,
end, round or occurrence id is invented when its producer has not recorded one.
The last task's merged outcome marks its story done, even when the saved story
state still says approved. New clients get these views and this guide at init;
existing clients get them after upgrading Forge and running sync.
Tasks and fixes are ready only while close's clean review matches the pull request's head
(the local branch when it already holds that head) and the checks are not failing. The clean
review is this machine's receipt or the readiness close published in the pull request, so every
machine agrees. On a machine with no worktree for a ready item, its next step names the person
who started it to merge it from their machine (or, in a human-merge repo, the pull request to
merge); with the worktree here but no receipt, it is `forge close <item>`, which checks it again
and writes the receipt that `forge merge` needs. A failed
rerun shows `checks failed` with `forge work` as its next step, even after a successful
close. A running rerun or unavailable checks retain a matching receipt's readiness;
green checks alone cannot grant it. The item's next step uses the same evidence.
If the next step cannot be checked,
the row stays visible with no runnable command; check the connection and run `forge next` again.

Stages are Build, Tests, Review, CI and Merge, in that order. Each carries status,
started_at, ended_at and seconds for the current round from Forge's timing records;
unrecorded values are null. For tasks and fixes, total_seconds is elapsed time from the item's recorded start
(or first recorded activity) to now, including idle time; a finished item needs a recorded end.
Their snapshot already includes live time, so do not add a running stage's timer to it.
Worker-owned tests are separated from building in the breakdown, while close's tests and
`forge test` still appear in the Tests stage. A skipped test has status skipped. Run starts and ends
provide live worker and reader metadata; completed timing durations supply stage end
times. Values remain null where the producer has not recorded them.

`time_breakdown` separates building, own tests, reviewing, fixing findings, waiting for CI,
waiting in line, waiting for the owner and nothing running. Overlapping steps count once:
tests and recorded waits come out of the enclosing worker's time. `rounds` retains each round's
plain `line`, its finding titles, priorities and files, and its new and repeated finding counts.
Round lines number review attempts; the row's current `round` still identifies its worker turn.
Repeated means the same title and file appeared in an earlier recorded review. A missing
earlier review makes unseen findings' new-versus-repeat counts unknown. Repeats observed in the
retained history remain known even beside unseen findings whose classification is unknown.
CI lines distinguish passed, failed and gave up while queued or
running; losing contact with GitHub without a known result stays unknown.
An earlier release's failed CI timing without an explicit result also stays unknown.
Old records are not filled in with guessed findings, durations or zeroes. A known original start
can give an elapsed total even when some earlier activity is unknown; that unknown time is not
called idle and the known breakdown need not add up to the elapsed total. Gaps between legacy
timings stay unknown until complete activity recording begins. Earlier run and question events
do not establish completeness; historical questions without a recorded end stay unknown.

Quote the item's round lines when explaining a long run, then quote the relevant breakdown
categories rather than adding overlapping stage timers. The board page shows these same
details. The pull request's short **How it went** section comes from the same logs and keeps
earlier findings after later reviews. Forge keeps the pull request body in an agent squash
merge; when the human merges, keep this section in the squash commit body too. New repos get
this guide and the recording behaviour at init; previously adopted repos get them on upgrade
and sync. Their earlier unrecorded history remains unknown. If a fresh clone or missing local
logs cannot reconstruct already published measurements, How it went retains them and shows
the current checkout's observations separately. Quote each snapshot separately; do not add
their totals, because their intervals may overlap.

Quote the item's round lines when explaining a long run, then quote the relevant breakdown
categories rather than adding overlapping stage timers. The board page shows these same
details. The pull request's **How it went** section carries intervals, review rounds (including
clean reviews), and waits with their ends. The shared record has a fixed size: while it is over, the oldest
detail of any kind (round lines, intervals, then raw events such as repeated CI waits) folds into
one "Rounds 1–N" line of totals and finding counts, oldest first; the newest round keeps its own numbered line,
and its folded retries add to it. Free text in each entry is cut to 300 characters, and a round
too big on its own, such as a huge review, folds whole into its line. Live progress stays local. So a
long item stays inside GitHub's body limit, and folding never changes its total time. Close and merge retain observations from other
checkouts and recompute repeated findings and overlapping time. The board reads this shared
record alongside local observations; `source` says which it had. A GitHub merge ends the last
wait at its merge time and names its merger. Story time counts each instant once: working when
any part or recorded plan read is working, waiting when none is working and any is waiting,
otherwise unknown. Inside a part's folded time range, the story's split between working and
waiting is approximate; the totals stay exact. Human times use rounded plain units; JSON keeps raw seconds. Rebuilt history
keeps its label and missing evidence remains unknown. New repos get this at init; existing
repos, including earlier adoptions, get it on upgrade and sync.
Worker questions and their answers refresh an existing pull request's record; a question before
its first pull request stays local. A first-close merge conflict opens the pull request so its
owner wait travels too, and resolving it records the wait's end.
Resuming work ends a published merge wait even when another checkout started it. History
refreshes retain the pull request's readiness; close publishes readiness for a newly checked head.
Board and next reads use the current pull request history and head; cached checks apply only
to the head they describe.
Questions on older pull requests without local publication evidence stay local.
Every pull request body stays within GitHub's size limit. Forge leaves tool-command prose out
of the shared time record, shortens duplicated and advisory detail before the contract, and
says plainly when it shortened anything. Exceptionally large time histories retain recent
evidence and current readiness; omitted time stays unknown. Full contracts and proof stay in git.
Items report working, waiting and unknown seconds alongside their detailed categories. An
unfinished story's runway continues through now, including unknown time after its last read
or recorded part activity; a read without a duration establishes a date, never guessed work.

Live rows add `activity` (status and a running action), `idle_since` and `stalled`
after 24 idle hours. A recorded worker adds tool, model, effort, round, start,
elapsed seconds and its latest tool step; close's live `tests` adds elapsed and
done/total where the runner reports progress. `gates` has plan_read, review and ci,
each with status; blocked reviews add count and running CI adds elapsed seconds.
PR failures list job and cause (timeout or failed); findings add items with title
and priority and a dismissed count. Both views' `events` list the last 20 run,
review and question records as time, item and one plain line, newest last.
Queue places stay absent until the shared lane entries ship.

The newest 25 open pull requests get checks in one GitHub request, cached for 60
seconds in the shared Git directory. Older pull requests and unreachable GitHub
show unknown checks. Required checks, including matrix variants, must succeed;
skipped or neutral required checks show fail, while optional ones count as passed.
A failed check occurrence keeps GitHub's own identity:
`check-run:<databaseId>:<completedAt>` or `status:<id>`. A rerun with a later
completion is a new occurrence. Each occurrence has id, kind and plain title;
run completions, undismissed review findings (including advisory findings) and unanswered
worker questions retain the ids in Forge's event records. Advisory occurrences do not
change the merge gate. Readiness uses the clean review's id plus the current head
commit. Runs that start and finish between board refreshes still appear as completions.

Both views' `next` contains `command`, `line` and `step`. Command is the first Next line
only when it is one runnable Forge command without a placeholder or alternative;
otherwise it is null. Line carries the plain current state from the text report. Step is
the first Next line's text even when it is not one runnable command, or null without one.
Release notices appear in the text output and never replace the machine view's state line.
Use each board row's next step for that item, never another
item's step. Machine views do not grant approval or permission to merge.

The shared mod contract fixture is `tests/fixtures/board.json`; command coverage
in `tests/test_machine_views.py` checks both views against it.

## Claude Code plugin core

The Claude Code mod reads Forge's machine views, runs `forge` commands and draws;
it never edits repo files or replaces the commands' approval and merge rules.
All its consumers share one snapshot. On load, then every 10 seconds, one refresh
runs `forge next --json` and `forge lanes --json` together. The next output also
supplies the board rows, so the pane reads them once per refresh.
If that Forge has no lanes command, lane data is absent. A due refresh is skipped
while the previous one runs, rather than queued. There is no extra fetch on `/forge`.
Drawing ticks advance live timers every second without fetching state.

A failed or malformed refresh, or a command taking over 60 seconds, keeps the
last good rows and adds a dim `Couldn't refresh: <first line of the error>`.
It retries on the next tick. Only a non-zero command result containing
`unrecognized arguments: --json` shows
`This repo's Forge is too old for the pane: upgrade Forge here.`
Other failures use the normal refresh error. The board command owns the
60-second GitHub checks cache described above; a check changing without a local
edit appears on the next refresh after that cache expires. Unknown checks stay
unknown, including when GitHub is unreachable.

## Installing the mod

`forge sync` installs or updates the mod from Forge's latest release at user scope,
one per machine, independently of each repo's pinned Forge version. It needs
Claude Code v2.1.287 or newer on PATH. When the marketplace is missing, sync runs
`claude plugin marketplace add knacklabs/symphony-forge`, then always runs
`claude plugin marketplace update forge`. It runs
`claude plugin install forge@forge --scope user` for a new user install, or
`claude plugin update forge@forge --scope user` for an existing one.
Sync writes no repo files for the mod; Codex's setup and workflow are unchanged.

Without `claude`, sync skips the mod. A failed install or update (including no
network or old Claude Code) prints one warning line and sync still succeeds;
run `forge sync` to retry. `forge doctor` warns when Claude Code is missing or
older than v2.1.287 and keeps exit status 0. In a running session, use
`/reload-plugins` or restart to load the updated mod. Desktop's WSL sessions load
no plugins; use the `forge` command there.

The mod runs `forge` from PATH with argv and no shell, in the session's repo root.
It does not change the repo's pin. If the pane or strip says that repo's Forge is
too old, upgrade Forge in that repo; other refresh errors follow the core's retry
behaviour above. Sessions without the mod keep using the commands as today.

## Approving with the pane

The pane has no Approve button: Claude Code's mod API cannot supply the story's exact text
to its native plan-approval prompt. Use Plan Mode and the story doc `forge next`
names, following Planning a story in [the guide](SKILL.md#planning-a-story). The existing approval hook and its trust
checks are unchanged. Plan Mode remains the approval path in Claude Code, Codex,
the VS Code chat panel and sessions without the mod; installing the mod changes
no approval rule.

## The pane and strip

Type `/forge` at any width, including 80 columns, to open and focus the pane.
The mod requests it at interactive session start too; Claude Code places it
automatically at 144 columns, or 110 after the person has opened it once.
The strip below that wide-screen threshold ends with `/forge for the board`.
The pane's Board tab, on the terminal and the Desktop app's Code tab alike, opens
with one summary line, such as `3 in progress · 1 needs you · 2 stuck · go-live Oct 20`.
Each part shows only when the board's `team` fact behind it is known and not zero; when
none of them applies, the line counts the rows the tab shows in its own group words instead,
such as `1 moving · 2 ready to merge · 3 waiting`; an empty board says only `Nothing in progress.`. An older Forge with no `team` shows no summary line. Below it come the board's
own sentence (`team.sentence`) and its labelled totals, one line per kind, such as
`Fixes — Done: 0; Ready to merge: 0; In progress: 1; To do: 0`, words built from
`team.counts`. Groups follow in this order, each only when it has items, and each in the board's own
order: NEEDS YOU (one row per `team.needs_you` entry, oldest first, with how long it has waited,
such as `waiting 3h`), STUCK (one row per `team.blocked` entry with its reason in words and its
age, such as `1 unfinished part waits on it · 2d`, and the longest stall in days), MOVING (the board's In progress, `team.in_progress`, except what is ready to merge;
a running item shows its current stage and how long, such as `Review running · 12 min`),
READY TO MERGE (the rest of `team.in_progress`, each saying Ready to merge, with the checks in words when known, and its merge
step; an item merged from another machine shows `forge next`'s line naming who merges it), then a
folded count of the work waiting or not started (planned stories and fixes not started), opened with a native button to the same rows. Each item shows its plain title, the story key small
beside it, one line of state in words and, where there is something to do, its next step
(`next.step`) after `→`. At most five rows show per group, then `and N more · forge board for all`.
An older Forge without the `team` lists draws the same groups from each row's `needs_person`,
stalled, running and ready flags, and shows no sentence or totals.
Outside those totals, the pane never shows zero counts, unknown times, raw timestamps, priority codes or
dismissed counts; findings read `Review found 3 problems`. Dates are short (`Oct 5`) or
relative (`12 min`, `8 days`), and every time rounds as the board's do (`2m`, never `1m 30s`). Stage chains, round lines and the time breakdown stay on
the board page. An empty board says `Nothing in progress.` `/forge` always returns the
same lines as text, as well as opening the pane. Where mods draw nothing (the VS Code
chat panel, `claude -p` and Remote Control from a phone or claude.ai), that text is the
status reply. It uses the last completed snapshot, including any refresh error. Until a
first refresh succeeds, the pane, the strip and `/forge` say `Loading Forge…`, or
`Couldn't refresh: <first line of the error>` once that refresh failed.

The strip above the prompt uses at most three lines. Its first line shows
`Agents N/M (W waiting) · Tests N/M (K waiting) · <running item or idle> · 1: <next command>`.
It also shows a recorded current worker step. The other lines show up to two active items
from this repo, each with Build → Tests → Review → CI → Merge, its round and total
time. A third active item replaces the last line with `+N more · /forge for all`.
Finished stages show ✓ and their duration, the current stage ● and a live timer,
and failed stages ✗ in red. Unreached stages have only their name; skipped tests
show `Tests –`. Symbols carry the meaning without colour. The total uses the elapsed-time
snapshot, which includes live and idle time without counting concurrent stages
twice. At widths under 80 columns it is one line: running and waiting counts, the first
active item's current stage and time, its total and the next step; without lane data,
the first line is only the next step; the narrow strip has no item or lane summary.

Press `1` on an empty prompt when Claude is idle to run the displayed next command
as the user. Before submitting, the mod re-reads `forge next --json`: if the command
changed it redraws and runs nothing. A failed re-read submits nothing and toasts
`Couldn't check the next step: <reason>`; a failed submit toasts
`Couldn't run the next step: <reason>`. A null command or busy Claude has no hotkey
and shows the plain next-step line instead. Typing into a nonempty prompt stays typing.

