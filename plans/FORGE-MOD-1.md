# Forge lives inside Claude Code

7 parts · Risks: code that runs inside every developer's Claude Code session · New moving parts: one Claude Code mod shipped with Forge

## What changes for you

- In Claude Code, a Forge pane shows every story and fix with its stage, what each worker is doing
  and for how long, the checks on each pull request, and open review findings. It stays current by
  itself, so nobody asks for status. Type `/forge` to open it; on a wide screen it opens by itself.
- The strip above the prompt always shows Forge's next step. Pressing 1 on an empty prompt runs
  it.
- A Machine tab in the pane shows what runs on this machine across all your repos: the agents
  building, reading or reviewing, with model and time; the one test run with a progress bar and
  time left; who waits next in each lane; and the machine's load and memory. The strip shows how
  many agents and tests run, and while Claude works the spinner line says where your work is in
  line. Pressing `o` opens a run's live output; pressing `s` stops a run after you confirm.
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

1. **In Claude Code, a Forge pane shows each story and fix with its stage, each running worker and how long it has run, each pull request's checks, and open findings, and it updates by itself.**
2. **The strip above the prompt shows Forge's next step, and pressing 1 on an empty prompt runs it.**
3. **When a review finds problems, checks fail, a pull request is ready to merge, a worker asks a question or a run finishes, the session starts a turn that names each such change and its next step; progress only updates the pane.**
4. **Pressing Approve on a waiting story opens Claude Code's own plan-approval prompt with the story's exact text from its file, and approving there records the same approval Plan Mode does; if Claude Code doesn't allow this, the button is left out and Plan Mode stays the way to approve.**
5. **`forge sync` turns the mod on from Forge's latest release, it works in every repo whatever Forge version that repo pins, and Codex and sessions without the mod work as today.**
6. **The Machine tab shows every agent and test run on the machine across repos, with model, time, test progress and who waits next, plus load and memory; a run's output opens with one key and a run stops only after a person confirms.**

## New and existing repos

- **New repos**: `forge sync` at init or adoption turns the mod on; everything shows from the
  first session.
- **Existing repos**: the next `forge sync` after moving to this release turns the mod on. A repo
  still pinned to an older Forge shows one line in the pane saying to upgrade Forge there; the
  Machine tab still shows its runs once any repo on the machine runs the new release. Nothing in
  their `forge.toml` changes. Tested by syncing a repo adopted on the previous release.

## Risks

- The mod is code that runs inside each developer's Claude Code session with their permissions.
  It only reads Forge's state and runs `forge` commands; it never edits files itself.
- Claude Code mods are new. If Claude Code changes how mods work, the pane can stop drawing;
  everything still works through the `forge` command as today.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

### Done-when details

1. Pane. Data: `forge board --json` (VIEWS). One row per story and fix: title, stage, running
   worker (kind, model, started at; elapsed computed by the mod from started at), pull request
   number and checks (pass/fail/running/unknown), open findings count with titles one level down.
   Opening: `/forge` (a mod command, `immediate: true`) opens and focuses it at any width; the mod
   also opens it unasked at session start, which Claude Code shows only at 144+ columns (110 after
   the user opened it once); otherwise the band ends with `/forge for the board`. Refresh: every
   30 seconds, and after each tool call whose command starts with `forge`; one refresh at a time
   (a refresh due while one runs is skipped). A failed, slow (over 20 s) or malformed refresh keeps
   the last good rows and adds one dim line `Couldn't refresh: <first line of the error>`. Empty
   board: one line `Nothing in progress.` Pull requests past the 25 whose checks `board` fetches
   show checks `unknown`. Tests (plugin): rows from a fixture; timer refresh advances elapsed time;
   failed and malformed refresh keep rows and show the line; empty board; `/forge` opens at 80
   columns; refresh after a tool call running `forge`; a refresh over 20 s is abandoned with the
   line; an overlapping refresh is skipped; an item with missing state shows `unknown`; GitHub
   unreachable shows checks `unknown`. Command test: `forge board --json` on a repo with a story, a
   fix, a running worker and an open pull request, and with GitHub unreachable.
2. Band. Data: `forge next --json` (VIEWS) gives `next.command`: the first `Next:` command that
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

6. Machine tab. Start MACHINE only after FORGE-LANES-1 has merged. Data: `forge lanes --json`
   (FORGE-LANES-1). Rows per lane in queue order: repo
   name, item in plain words, kind, model and effort, elapsed; the test row draws a bar from
   `done`/`total` and time left from that repo's last full run time in Forge's timings, or no
   estimate without one. Load line: a `Raster` sparkline of the last 30 load samples (Text on
   Desktop), amber when load is above the core count. Strip: `Agents N/M · Tests: <state>`.
   Spinner suffix while Claude works: the session's item place in its lane. `o` opens the run's
   output file in a pane (last 200 lines, refreshing); `s` asks `$.ui.ask` to confirm, then runs
   `forge stop <item>` (FORGE-LANES-1 adds it if missing; stopping only from a person's press).
   Toasts when a run in either lane starts, passes, fails, or the machine passes 1.5x its cores.
   Tests (plugin): rows, bar and estimate from a fixture; amber load; `s` without confirm stops
   nothing; `o` shows the tail. Command test of `forge stop` stopping a fixture run.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| RUNS | Run and question records | Records with ids for run start and end, review results and worker questions on both worker paths, and `FORGE_WORKER=1` for every process Forge starts | 3 | src/forge/repo.py, src/forge/worker.py, src/forge/close.py, src/forge/codex.py | tests/test_run_records.py | | no |
| VIEWS | Machine views and the guide | `--json` on `forge next` and `forge board` with the fields in details 1-4 and `version`, a contract test both views share with the mod's fixtures, and the guide's machine views section | 1, 2, 3 | src/forge/nextstep.py, src/forge/board.py, src/forge/cli.py, src/forge/templates/skill.md, tests/fixtures/board.json | tests/test_machine_views.py | RUNS | no |
| PANE | Pane and next-step band | The plugin skeleton, `/forge`, the pane, the band and its hotkey, the `forge` call and too-old line, and the seam: register.ts calls `registerEvents(on)` from events.ts and `registerApproval(on)` from approval.ts, created here as empty functions | 1, 2 | src/forge/mod/.claude-plugin/**, src/forge/mod/hooks/hooks.json, src/forge/mod/hooks/register.ts, src/forge/mod/hooks/pane.ts, src/forge/mod/hooks/forge.ts, src/forge/mod/hooks/pane.test.ts, src/forge/mod/hooks/events.ts, src/forge/mod/hooks/approval.ts, pyproject.toml, src/forge/templates/skill.md | src/forge/mod/hooks/pane.test.ts, tests/test_mod_plugin.py | VIEWS | yes |
| EVENTS | Turns when work needs the agent | Seen store per repo and session, batching, session gating, filling `registerEvents` | 3 | src/forge/mod/hooks/events.ts, src/forge/mod/hooks/events.test.ts, src/forge/templates/skill.md, src/forge/templates/brief.md | src/forge/mod/hooks/events.test.ts | PANE | yes |
| APPROVE | Approve from the pane | The proof step, then the button and the plan prompt filling `registerApproval`, or the recorded reason it was left out | 4 | src/forge/mod/hooks/approval.ts, src/forge/mod/hooks/approval.test.ts, src/forge/approval.py, plans/FORGE-MOD-1.md, src/forge/templates/skill.md | src/forge/mod/hooks/approval.test.ts, tests/test_mod_approval.py | PANE | yes |
| SHIP | Sync turns the mod on | Marketplace file pinned to the package version, sync's install or update at user scope, doctor's warning, CI's plugin test job | 5 | .claude-plugin/marketplace.json, src/forge/sync.py, src/forge/doctor.py, .github/workflows/forge-next.yml, src/forge/templates/skill.md, tests/fixtures/marketplace/** | tests/test_mod_sync.py, tests/test_mod_install.py | PANE | no |

| MACHINE | Machine tab | The Machine tab, the strip's lane counts, the spinner line, output and stop keys, lane toasts | 6 | src/forge/mod/hooks/machine.ts, src/forge/mod/hooks/machine.test.ts, src/forge/templates/skill.md | src/forge/mod/hooks/machine.test.ts | PANE | yes |

New moving parts: one Claude Code plugin (mod) that Forge ships and sync turns on (Done-when 1-5)

## Notes

- Mods docs: code.claude.com/docs/en/plugins/mods/overview, /reference, /interface (v2.1.287+).
  Render sites `Pane`, `AbovePrompt`; `$.clock.every`, `$.process.run`, `$.prompt.submit`,
  `$.store`, `$.session.surfaces`, `$.session.repo`, `$.session.id`.
- All Forge rules stay in the `forge` command; the mod only reads the machine views, runs `forge`
  commands and draws. It never writes repo files.
- Each task updates the guide for what it adds, in its own section of skill.md (VIEWS: machine
  views; PANE: the pane and band; EVENTS: events, plus brief.md's line that workers never act on
  them; APPROVE: approving from the pane; SHIP: how the mod is installed). Tasks that run at the
  same time wait for each other on skill.md through task start's overlap rule.
