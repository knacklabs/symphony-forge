# Forge lives inside Claude Code

11 parts · Risks: code that runs inside every developer's Claude Code session · New moving parts: one Claude Code mod shipped with Forge

## What changes for you

- In Claude Code, a Forge pane shows every story and fix with its stage, what each worker is doing
  and for how long, the checks on each pull request, and open review findings. It stays current by
  itself, so nobody asks for status. Type `/forge` to open it; on a wide screen it opens by itself.
- The strip above the prompt is an always-on summary in at most three lines: how many agents and
  test runs are going and waiting, Forge's next step (press 1 on an empty prompt to run it), and
  up to two active items, each showing its stages from build through tests, review and CI to
  merge, with how long each finished stage took, a live timer on the current one, its round and
  its total time. More items show as "+N more". A narrow terminal gets one line.
- The pane answers "what's happening?" without anyone asking: for each running worker its tool,
  model, reasoning effort, round, elapsed time and what it is doing right now; for every item
  whether it is running, waiting in line (and where) or idle and since when, with items idle over a
  day marked stalled; each stage's time with a live timer on the current one, and test progress;
  for a red check, which job failed and whether it timed out; review findings with their severity
  and how many were dismissed.
- A Machine tab in the pane shows what runs on this machine across your repos on this Forge
  release: the agents building, reading or reviewing, with model and time; the one test run with
  its progress; who waits next in each lane; and the machine's load. While Claude works the
  spinner line says where your work is in line. Pressing `o` opens a run's live output; pressing
  `s` stops a run after you confirm.
- In the Code tab of the Claude Desktop app the same pane draws richer: each item's stages as a
  timeline you can hover for times, the Machine tab's agents as a drawn tree, lists as tables, and
  native buttons. Where Claude Code draws nothing for a mod (the VS Code chat panel, a phone or
  claude.ai through Remote Control), `/forge` replies with the full status as text. Desktop's WSL
  sessions load no plugins at all, so there Forge works through the `forge` command as today.
- When work needs the agent (a review found problems, checks failed, a pull request is ready to
  merge, a worker asked a question, or a run finished), Forge tells the session and the agent acts
  on it straight away. Progress such as a run starting or checks running only updates the pane.
- A story waiting for approval shows an Approve button in the pane. Pressing it opens Claude
  Code's own plan-approval prompt holding the story's "What changes for you" and "Done when"
  exactly as written in the file; you approve there, as today, so no text can be pasted wrong.
  If Claude Code turns out not to allow a plugin to open that prompt, the button is left out.
- Plan Mode approval keeps working everywhere, and is the only way in Codex, the VS Code chat
  panel and sessions without the mod.
- `forge sync` turns the mod on, from Forge's latest release. It works with every repo on the
  machine whatever Forge version each pins; where a repo's Forge is too old for the pane, the pane
  says in one line to upgrade Forge there. Codex works exactly as today.

## Why

Driving Forge today means babysitting it. The agent polls runs with watcher scripts, so a finished
run can sit unnoticed and every check costs a turn. People ask "what's the status?" and get long
lists back. Each next step is a command someone has to read and type. Approving a story means the
agent pastes the story's text into Plan Mode unchanged, and any slip records nothing. Claude Code
now lets a plugin draw panes and buttons and start a turn when something happens, which removes
all four.

## Done when

1. **In Claude Code, a Forge pane shows each story and fix with its stage, each running worker and how long it has run, each pull request's checks, and open findings, and it updates by itself; in the Desktop app it also draws each item's stages as a timeline and uses native buttons, and where nothing draws (VS Code chat panel, Remote Control) `/forge` replies with the full status as text.**
2. **The strip above the prompt always shows a summary of running and waiting agents and tests, Forge's next step, and up to two active items with each stage's time and the total, and pressing 1 on an empty prompt runs the next step.**
3. **When a review finds problems, checks fail, a pull request is ready to merge, a worker asks a question or a run finishes, the session starts a turn that names each such change and its next step; progress only updates the pane.**
4. **Pressing Approve on a waiting story opens Claude Code's own plan-approval prompt with the story's exact text from its file, and approving there records the same approval Plan Mode does; if Claude Code doesn't allow this, the button is left out and Plan Mode stays the way to approve.**
5. **`forge sync` turns the mod on from Forge's latest release, it works in every repo whatever Forge version that repo pins, and Codex and sessions without the mod work as today.**
6. **The Machine tab shows every agent and test run on the machine from repos on this release, with model, time, test progress and who waits next, plus the machine's load; a run's output opens with one key, a run stops only after a person confirms, in the Desktop app the agents show as a drawn tree, and where nothing can draw `/forge` prints the summary as text.**
7. **For every item the pane shows whether it is running, queued (with its place in line) or idle and since when (stalled after a day); for each running worker its tool, model, effort, round, elapsed time and current step; each stage's time and test progress; for a red check the failing job and whether it timed out; and findings with their severity and dismissed count.**

## New and existing repos

- **New repos**: `forge sync` at init or adoption turns the mod on; everything shows from the
  first session.
- **Existing repos**: the next `forge sync` after moving to this release turns the mod on. A repo
  still pinned to an older Forge shows one line saying to upgrade Forge there, and its runs don't
  appear in the Machine tab until it does. Nothing in their `forge.toml` changes. Tested by syncing
  a repo adopted on the previous release.

## Risks

- The mod is code that runs inside each developer's Claude Code session with their permissions.
  It only reads Forge's state and runs `forge` commands; it never edits files itself.
- Claude Code mods are new. If Claude Code changes how mods work, the pane can stop drawing;
  everything still works through the `forge` command as today.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

### Done-when details

1. Pane. Refresh (CORE owns it): one schedule, nothing else: at load, then every 10 seconds, run
   `forge board --json`, `forge next --json` and, when it exists, `forge lanes --json`; one refresh
   at a time (a due one is skipped while one runs); a failed refresh is simply tried again on the
   next tick. `forge board` fetches checks for the newest 25 open pull requests in one GitHub request and
   caches them for 60 seconds across invocations (VIEWS); older pull requests show `unknown`, so a check that fails with no local change shows within about a minute.
   `/forge` always returns the summary of detail 2 and the board rows as text (command.run
   `{ text }`) and also opens the pane; where nothing draws (VS Code chat panel, `claude -p`, a
   phone through Remote Control) the text is what the person sees. Plugin tests: initial load; a
   check turning red with no local change appears on the next board refresh after the cache
   expires; a failed refresh retries on the next tick; `/forge` returns text in a headless test
   session.
   Data: `forge board --json` (VIEWS). One row per story and fix: title, stage, running
   worker (kind, model, started at; elapsed computed by the mod from started at), pull request
   number and checks (pass/fail/running/unknown), open findings count with titles one level down.
   Opening: `/forge` (a mod command, `immediate: true`) opens and focuses it at any width; the mod
   also opens it unasked at session start, which Claude Code shows only at 144+ columns (110 after
   the user opened it once); otherwise the band ends with `/forge for the board`. A failed, slow (over 20 s) or malformed refresh keeps
   the last good rows and adds one dim line `Couldn't refresh: <first line of the error>`. Empty
   board: one line `Nothing in progress.` Pull requests past the 25 whose checks `board` fetches
   show checks `unknown`. Tests (plugin): rows from a fixture; elapsed time advances between refreshes;
   failed and malformed refresh keep rows and show the line; empty board; `/forge` opens at 80
   columns; a refresh over 20 s is abandoned with the line; an overlapping refresh is skipped; an item with missing state shows `unknown`; GitHub
   unreachable shows checks `unknown`. Command test: `forge board --json` on a repo with a story, a
   fix, a running worker and an open pull request, and with GitHub unreachable.
2. Band. Summary lines (AbovePrompt, `maxRows` 3): line 1 `Agents N/M (W waiting) · Tests: <running item
   or idle> (K waiting) · 1: <next command>`; without lane data (an older Forge) it is just
   `1: <next command>`; lines 2-3 one per active item of this session's repo (other repos show in the Machine tab):
   plain title, the stage chain Build → Tests → Review → CI → Merge with ✓ and the stage's time for
   finished stages, ● and a live timer on the current one, ✗ in red for a failed stage, then
   `round R · total T`; a third active item turns line 3 into `+N more · /forge for all`. Stage
   times come from `forge board --json`'s `stages` for the item (VIEWS), built from RUNS' records:
   each worker round, test run (close's and `forge test`'s), review and CI wait is recorded with
   the item's round number; Build is the worker round including the worker's own test runs; a
   stage not reached this round shows plain; a skipped test run (docs only) shows `Tests –`.
   Producer tests (RUNS): two worker rounds with a test run and a review each record round 1 and 2
   with real durations; a docs-only close records a skipped test run. VIEWS: `forge board --json`
   gives each item its current round's stages; the checks cache is reused by a second invocation
   within 60 s and refetched after, and a check that turns red on GitHub alone shows after expiry;
   with 30 open pull requests the newest 25 have checks and the rest `unknown`. Under 80 columns the band is one line: `N
   running, W+K waiting · <first item>: <stage> <time> (<total>) · 1: <next command>`. Every state has a symbol, so it reads
   without colour. Tests (plugin): two items and a third; failed stage; narrow width; without lane
   data (older Forge) line 1 is the next step and pressing 1 still runs it.
   Next step. Data: `forge next --json` (VIEWS) gives `next.command`: the first `Next:` command that
   is one runnable forge command with no placeholder and no alternative; otherwise null, with
   `next.line` the plain state. With a command and Claude idle: `1: <command>`, hotkey `1`
   (Claude Code fires a digit hotkey only into an empty prompt, so typing stays typing). Pressing
   it re-reads `forge next --json`; if the command changed it shows the new one and runs nothing;
   else `$.prompt.submit({ text: command, asUser: true })`. If the re-read fails, nothing is
   submitted and a toast says `Couldn't check the next step: <reason>`. Null command, or Claude
   working: the line without a hotkey. A failed submit shows a toast with the reason. Tests
   (plugin): press submits the exact command; null command has no hotkey; stale command runs
   nothing and redraws; busy shows no hotkey; failed re-read submits nothing and toasts; failed
   submit toasts. Command test: `forge next --json` for a ready task, a waiting item and a
   merge only a human may do (null).
3. Events. Every occurrence carries an id Forge writes (RUNS): each review result, run end and
   worker question record gets a fresh random `id` when written; a failed check uses the id
   GitHub gives it plus when it completed: a check run's database id and `completed_at` (a
   re-run may reuse the id, but completes again later), or a commit status's id (each new status
   gets its own); ready-to-merge uses the review id plus the head commit. Nothing
   else identifies an event. `forge board --json` lists, per item, its open occurrences and that
   item's own `next.command` (the same rule as detail 2, applied to that item's `Next:` line; null
   when it has none or it is not one runnable command), so each event line names its own item's
   step, or `forge next` when null. Seen ids live in `$.store` under the key repo root + session
   id, never repo alone, so each session consumes its own; at session start and after a reload the
   session records the current ids as seen without starting turns. Changes found while Claude is
   working, or several in one refresh, go into one turn after the current one ends, one line each:
   plain item title, what happened, that item's next command. A failed submit leaves them unseen
   for the next refresh. Only interactive sessions get turns (`$.session.surfaces()` includes
   terminal or desktop), and never a session Forge started: Forge sets `FORGE_WORKER=1` in every
   worker, reader and reviewer it starts, and the mod is inert there. A session acts only for its
   own repo (`$.session.repo()` matched to the board's repo root). Tests (plugin): two snapshots
   give one turn per change; progress gives none; the next refresh repeats none; the same question
   asked again in a later round (new id, same text) gives a second turn; a check re-run failing
   again under a new check run id, or under the same id with a later completion (failed, running,
   failed), and a new failed commit status each give a second turn; two changes while busy give one turn after; a run
   that started and ended between refreshes gives one turn; reload gives none; a failed submit
   gives the turn on the next refresh; two sessions sharing one store each get the turn; a
   `FORGE_WORKER=1` session and a `claude -p` session give none; another repo's change gives none.
   Command tests: (RUNS) every worker, reader and reviewer process gets `FORGE_WORKER=1`; Codex
   and Claude worker questions, run ends and review results are recorded with fresh ids; (VIEWS)
   two items in one board each carry their own `next.command`, and an item with none has null;
   a failed check run and a failed commit status each appear with GitHub's own id (and the check
   run's completion time), including one check run failing twice under one id, using
   recorded GitHub responses as fixtures.
4. Approval. First step of APPROVE: prove in a real Claude Code (v2.1.287+) that a mod can start
   `ExitPlanMode` with given plan text so that Claude Code shows its own plan-approval prompt and,
   on approval, runs Forge's existing approval hook. If it can't, APPROVE removes the button,
   records why in the story notes, and Done-when 4 is met by Plan Mode alone. When it can: the
   button reads the story doc from disk at press time (CRLF normalised to LF), takes the part
   `forge next` names for approval exactly as Plan Mode approval expects, and starts the prompt
   with it; all trust checks stay in `forge hook approval` unchanged (digest, completed call,
   replay, one waiting story). The doc is the one `forge board --json` names for the waiting story
   (`approval.doc`, an absolute path in that story's worktree). Request changes is Claude Code's
   own answer in that prompt; the mod adds no control of its own. A missing or unreadable doc
   shows a toast and opens nothing. Tests: plugin test that the plan text equals the doc's part
   with CRLF line ends turned into LF and nothing else changed; that the doc named for the story
   is read, not the session's checkout; a missing doc toasts and opens nothing; command tests that
   the hook records the approval from that payload and refuses after the doc changed between
   press and approval.
5. Delivery. Forge's repository is public and holds a marketplace `forge`
   (`.claude-plugin/marketplace.json`) listing plugin `forge` with `version` equal to the package
   version and source the `src/forge/mod` folder at tag `v<version>`; a test fails when they
   differ, so each version bump moves it, and the default branch always lists the latest release.
   When `claude` is on PATH, `forge sync` makes the mod current at user scope (one per machine):
   `claude plugin marketplace add knacklabs/symphony-forge` if missing, `claude plugin marketplace
   update forge`, then `claude plugin install forge@forge --scope user`, or `claude plugin update
   forge@forge` when installed. Sync writes no repo file for the mod. A failure (no network, old
   Claude Code) is one line and sync still succeeds. Version: the mod runs `forge` from PATH with
   argv and no shell, working directory the session's repo root, as the agent does. A Forge without
   machine views refuses `--json` as an unrecognized argument (exit status non-zero and the words
   `unrecognized arguments: --json`); that refusal, and only it, makes the pane and band show
   `This repo's Forge is too old for the pane: upgrade Forge here.`; any other failure is a normal
   refresh failure (detail 1). A running session picks the
   mod up after `/reload-plugins` or a restart. Doctor: Claude Code missing or older than v2.1.287
   is one warning line and keeps exit status 0. Tests: command tests of sync's plugin commands
   (fresh machine, already current, older install updated, no network, no `claude`) with a stub
   `claude`, of doctor's warning and exit status, that sync writes no repo file for the mod and
   Codex files are unchanged; plugin test that the real refusal text of a Forge without views gives the
   too-old line and another failure does not, and of a Windows path with spaces as working
   directory; one integration test with real Claude Code, an isolated home and a local marketplace
   fixture at a local tag (no network) that sync installs the plugin, a reload loads it, and two
   repos (one on a Forge without views) each show the right pane line; `claude plugin validate --strict` passes. CI installs a pinned Claude Code
   with npm to run `claude plugin test` and `validate`.

6. Machine tab. Drawn as an agent tree (owner chose 2026-10-04, after a Claude Code agent-tree
   design): this session at the top ("plans + decides"); under it
   one box per running entry of the agent lane (worker, plan reader, reviewer: item in plain words,
   tool, model, effort, round, elapsed) and the test lane's box (item, progress bar, elapsed); a
   gates column listing each active item's gates (plan read passed, review clean/blocked with its
   finding count, CI green/red/running with elapsed); no event log by default (owner: people want
   outcomes and status, and ask for detail when they need it): pressing `l` shows the last events,
   one line each with time, and `l` again hides them; a legend of colours per tool and lane, each also marked with a symbol so it reads without
   colour. Only facts Forge records: no probabilities, token counts or other figures Forge does not
   keep. In the Desktop app (`e.surface === 'desktop'`; `Svg` is Desktop-only) the tree is one `Svg` drawing (interactive,
   `<title>` tooltips with model, round and elapsed; colours plus symbols; `alt` text listing the
   same facts), the keys become native Buttons. In the terminal under 100 columns the tree becomes a
   list in the same order. Tests (plugin): tree from a fixture with a worker, a reviewer, a reader and a test run;
   gates for a blocked review and a red check; no log until `l` is pressed, then the last events newest last; list form at
   80 columns; the same fixture on `desktop` draws an Svg whose alt text names each run.
   MACHINE's After names FORGE-LANES-1's AGENTS and TESTS tasks. CORE creates pane.ts with `addTab(name, render)` (a
   stub PANE fills) and machine.ts with an empty `registerMachine(on, data, addTab)`; PANE owns the
   tabs and the whole strip. MACHINE adds only the tab, the spinner line and the keys. Data: `forge lanes
   --json` (FORGE-LANES-1), which lists only repos on this release. The tree's facts and their
   producers: for this repo's runs, tool, model, effort, round, step and the gates column come from
   `forge board --json` (LIVE, detail 7); for another repo's runs only the lane entry's own facts
   show (repo, item, kind, model, elapsed, place), with no gates and no round; a fixture field that
   no producer writes fails the contract test both views share. Rows per lane in queue order:
   repo name, item in plain words, kind, model and effort, elapsed; a running test shows
   `done/total` as a bar when the runner reports it, else elapsed only (no time-left estimate). Load
   line: the view's load average as a `Raster` sparkline of the last 30 samples, taken at each
   refresh (Text on Desktop; hidden where the OS gives none, as on Windows), amber above the core
   count. Spinner suffix while Claude works: this session's item place in its lane. `o` opens the
   run's output file in a pane (last 200 lines, re-read when it grows; "output not available" when
   it can't be read). `s` asks `$.ui.ask` to confirm, then runs `forge stop --id <entry id>` with the
   id of the lane entry the person saw (FORGE-LANES-1 AGENTS owns the command and gives every entry
   an id); a replacement run has a new id, so a run that ended or was replaced while the question
   was open is not stopped and the mod says so; a failed stop shows its reason. No toasts.
   States: empty lanes show "Nothing running"; a failed or malformed refresh keeps the last rows
   with the refresh line (detail 1). Tests (plugin): rows and bar from a fixture; null progress;
   empty lanes; load hidden when null; `o` on a growing and an unreadable file; `s` declined stops
   nothing; `s` confirmed stops the run; `s` on an ended or replaced run says so; a failed stop shows
   its reason; a failed or malformed refresh keeps the rows.

7. Live status (LIVE). This detail is the contract: LIVE owns these field names, their shapes and
   the shared fixture `tests/fixtures/board.json`; PANE and MACHINE read only fields named here and
   show nothing for an absent one. `forge board --json` and `forge next --json` gain, per item:
   `activity` (`running` with the run's action, `queued` with `lane` and `place`, or `idle`) and
   `idle_since`: the end time of the item's last run record (RUNS), or, with no run record, the
   item's branch's last commit time; a run starting clears it and the run's end sets it again;
   `stalled: true` when idle over 24 hours; `gates`: `plan_read` (`passed`, `blocked` or `none`, from
   the story's read record), `review` (`clean`, `blocked` with finding count, or `none`) and `ci`
   (`green`, `red`, `running` with elapsed, or `none`); per running worker `tool`, `model`, `effort`, `round`,
   `started_at` and `step` (the latest step the worker reported: Forge records it from the worker's
   turn events as one plain line, such as "running 109 related tests", "editing src/forge/close.py",
   "committing"; at most one record per 10 seconds); per test run `done`/`total` when the runner
   reports it; per red check `job` and `cause` (`timeout` when GitHub cancelled the job at its time
   limit, else `failed`); per finding `priority`, plus `dismissed` (count); and a top-level `events`: the last 20
   run records RUNS writes (run start and end, review result, worker question), each with time,
   item and one plain line, newest last; the Machine tab's `l` shows exactly these. Queue place comes from
   FORGE-LANES-1's lane entries when that story has merged; until then `queued` is absent and the
   item reads `idle`. The pane (PANE) and Machine tab (MACHINE) show these; the strip shows the
   running count and the first running item's step. Tests (command): a run that starts, ends (idle_since set) and
   starts again (idle_since cleared); a worker step recorded through each worker path, a stub Codex
   app-server emitting raw tool events and a stub Claude emitting its raw stream, each showing as
   the live step (the latest of two); an item idle for 25 hours (stalled), a red
   check whose job timed out and one that failed, and a review with a P1, a P2 and one dismissed
   finding; both views carry the same fields; new and earlier-adopted client repos both get them.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| RUNS | Run and question records | Records with ids for run start and end, review results and worker questions on both worker paths, the item's round number on every timing record and a timing record for each test run, written inside review.test_run so close's run and the lanes story's `forge test` both record it, and `FORGE_WORKER=1` for every process Forge starts | 2, 3 | src/forge/repo.py, src/forge/worker.py, src/forge/close.py, src/forge/codex.py, src/forge/review.py | tests/test_run_records.py | | no |
| VIEWS | Machine views and the guide | `--json` on `forge next` and `forge board` with the fields in details 1-4 and `version`, a contract test both views share with the mod's fixtures, and the guide's machine views section, the per-item `stages` and the 60-second GitHub checks cache | 1, 2, 3 | src/forge/nextstep.py, src/forge/board.py, src/forge/cli.py, src/forge/templates/skill.md, tests/fixtures/board.json | tests/test_machine_views.py | | no |
| CORE | Plugin core | The plugin skeleton, the `forge` calls and the one refresh schedule, the too-old line, the summary formatter in summary.ts that both `/forge`'s text and the strip use, and the seams: `data` is `{ board, next, lanes, error, refreshedAt }` with `onUpdate(fn)`; register.ts calls `registerPane(on, data)`, `registerEvents(on, data)`, `registerApproval(on, data)` and `registerMachine(on, data, addTab)`, and pane.ts exports `addTab`, all created here as stubs with one test crossing them | 1, 6 | src/forge/mod/.claude-plugin/**, src/forge/mod/hooks/hooks.json, src/forge/mod/hooks/register.ts, src/forge/mod/hooks/forge.ts, src/forge/mod/hooks/summary.ts, src/forge/mod/hooks/core.test.ts, src/forge/mod/hooks/pane.ts, src/forge/mod/hooks/events.ts, src/forge/mod/hooks/approval.ts, src/forge/mod/hooks/machine.ts, pyproject.toml | src/forge/mod/hooks/core.test.ts, tests/test_mod_plugin.py | VIEWS | no |
| PANE | Pane and summary strip | The pane and its `addTab`, the summary strip in every layout and its hotkey, filling `registerPane`, and the seam APPROVE fills: pane.ts exports `addItemAction(kind, render)`, drawn on that kind's rows, with one test that an action added there appears on a story row, the richer drawing in the Desktop app (the Surfaces note), and detail 7's fields once LIVE has merged (absent fields show nothing) | 1, 2, 7 | src/forge/mod/hooks/pane.ts, src/forge/mod/hooks/pane.test.ts | src/forge/mod/hooks/pane.test.ts | CORE | yes |
| EVENTS | Turns when work needs the agent | Seen store per repo and session, batching, session gating, filling `registerEvents` | 3 | src/forge/mod/hooks/events.ts, src/forge/mod/hooks/events.test.ts, src/forge/templates/brief.md | src/forge/mod/hooks/events.test.ts | CORE | yes |
| APPROVE | Approve from the pane | The proof step, then the button and the plan prompt filling `registerApproval`, or the recorded reason it was left out | 4 | src/forge/mod/hooks/approval.ts, src/forge/mod/hooks/approval.test.ts, src/forge/approval.py, plans/FORGE-MOD-1.md | src/forge/mod/hooks/approval.test.ts, tests/test_mod_approval.py | PANE | yes |
| SHIP | Sync turns the mod on | Marketplace file pinned to the package version, sync's install or update at user scope, doctor's warning, CI's plugin test job | 5 | .claude-plugin/marketplace.json, src/forge/sync.py, src/forge/doctor.py, .github/workflows/forge-next.yml, tests/fixtures/marketplace/** | tests/test_mod_sync.py, tests/test_mod_install.py | CORE | no |
| GUIDE | The guide for the pane and events | skill.md's sections for the plugin core, the pane and strip, and events, as they were built | 1, 2, 3 | src/forge/templates/skill.md | tests/test_mod_guide.py | CORE, PANE, EVENTS | no |
| GUIDE2 | The guide for approving and installing | skill.md's sections for approving from the pane and how the mod is installed, as they were built | 4, 5 | src/forge/templates/skill.md | tests/test_mod_guide.py | APPROVE, SHIP, GUIDE | no |
| LIVE | Live status in the machine views | Detail 7's fields in both views: activity, idle since and stalled, each running worker's tool, model, effort, round, start and current step, test progress, a red check's job and cause, findings' severity and dismissed count | 7 | src/forge/board.py, src/forge/nextstep.py, src/forge/worker.py, src/forge/codex.py, src/forge/close.py, src/forge/review.py, src/forge/repo.py, tests/fixtures/board.json | tests/test_live_status.py | | no |
| MACHINE | Machine tab | The Machine tab, the spinner line, output and stop keys, filling `registerMachine` | 6 | src/forge/mod/hooks/machine.ts, src/forge/mod/hooks/machine.test.ts, src/forge/templates/skill.md | src/forge/mod/hooks/machine.test.ts | PANE, LIVE, FORGE-LANES-1/AGENTS, FORGE-LANES-1/TESTS | yes |

New moving parts: one Claude Code plugin (mod) that Forge ships and sync turns on (Done-when 1-5)

## Notes

- APPROVE proof (2026-10-06): leave the Approve button out; Done-when 4 uses
  Plan Mode alone. In real interactive Claude Code 2.1.291, a temporary mod's
  immediate command called `$.tool.call({ tool: 'ExitPlanMode', plan: text })`
  in Plan Mode with a supplied story-shaped plan. Claude displayed only
  "Exit plan mode?" and "Claude wants to exit plan mode", without that text.
  Accepting its native prompt ran the PostToolUse hooks and returned
  `{ plan: null, isAgent: false, filePath: <session plan path> }`. The same
  generic prompt was seen on 2.1.290. The installed runtime strips the reserved
  `plan` and `planFilePath` inputs before injecting its own session plan from
  disk; the public ExitPlanMode input declares only deprecated `allowedPrompts`.
  A mod therefore cannot provide the story's exact text through this API.
  Writing Claude's session plan file or submitting an agent instruction is
  outside this button's contract. No button, document reader or custom approval
  prompt is shipped, and `forge hook approval` is unchanged. The existing pane
  remains keyboard accessible with its native controls and labels; there is
  no new control, colour or animation to audit. `approval.test.ts` checks the
  assembled pane on terminal and Desktop has no Approve button and `/forge`
  retains the Plan Mode next step. `tests/test_mod_approval.py` proves Plan Mode
  still records approval, rejects a changed doc and replay, and refuses the
  real probe's missing-plan result. New and previously adopted repos receive
  the same button-free mod; their approval hooks need no upgrade or change.
- Surfaces (owner, 2026-10-05: same pane, richer where the surface can draw; checked against
  code.claude.com/docs/en/plugins/mods/overview "Where mods run": only the terminal and the
  Desktop app's Code tab show a mod's drawing; the VS Code chat panel, `claude -p` and Remote
  Control from a phone or claude.ai draw nothing): read `e.surface`. Terminal draws text as in
  details 1-2. The Desktop app adds, per item, a stage timeline as one
  `Svg` (a segment per stage, coloured by outcome with a symbol, `<title>` hover with its time;
  `alt` lists the same), Markdown tables for the item lists, and native Buttons for every key
  action. Where nothing draws, `/forge`'s reply is the full status as text (detail 1's fields
  and detail 7's, one item per two lines), the same text the headless reply gives. The strip (AbovePrompt) stays text on every surface. Every pane and
  Machine tab test loops over `['terminal', 'desktop']`, and one test checks `/forge`'s text reply;
  on `desktop`, pane.test.ts also finds each item's timeline `Svg` whose alt text gives every
  stage's time, and presses a native Button by key and sees its action run (the plugin test kit's `mount`
  with `surface`), asserting facts, never paint.
- Mods docs: code.claude.com/docs/en/plugins/mods/overview, /reference, /interface (v2.1.287+).
  Render sites `Pane`, `AbovePrompt`; `$.clock.every`, `$.process.run`, `$.prompt.submit`,
  `$.store`, `$.session.surfaces`, `$.session.repo`, `$.session.id`.
- All Forge rules stay in the `forge` command; the mod only reads the machine views, runs `forge`
  commands and draws. It never writes repo files.
- Guide sections: VIEWS writes the machine views section; GUIDE writes the plugin core, the pane and band and events, and GUIDE2
  approving from the pane and how the mod is installed, after those parts merge; MACHINE writes its
  own. EVENTS still adds brief.md's line that workers never act on events. Owner, 2026-10-05:
  PANE, EVENTS, APPROVE and SHIP build side by side after CORE, and CORE doesn't wait for other stories' guide edits, so all five leave skill.md to GUIDE and GUIDE2;
  their reviews don't report the missing guide update (GUIDE is that update).
