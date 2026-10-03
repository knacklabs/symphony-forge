# Forge lives inside Claude Code

5 parts · Risks: code that runs inside every developer's Claude Code session · New moving parts: one Claude Code mod shipped with Forge

## What changes for you

- In Claude Code, a Forge pane shows every story and fix with its stage, what each worker is doing
  and for how long, the checks on each pull request, and open review findings. It stays current by
  itself, so nobody asks for status. Type `/forge` to open it; on a wide screen it opens by itself.
- The strip above the prompt always shows Forge's next step. Pressing 1 on an empty prompt runs
  it.
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
   columns. Command test: `forge board --json` on a repo with a story, a fix, a running worker and
   an open pull request.
2. Band. Data: `forge next --json` (VIEWS) gives `next.command`: the first `Next:` command that
   is one runnable forge command with no placeholder and no alternative; otherwise null, with
   `next.line` the plain state. With a command and Claude idle: `1: <command>`, hotkey `1`
   (Claude Code fires a digit hotkey only into an empty prompt, so typing stays typing). Pressing
   it re-reads `forge next --json`; if the command changed it shows the new one and runs nothing;
   else `$.prompt.submit({ text: command, asUser: true })`. Null command, or Claude working: the
   line without a hotkey. A failed submit shows a toast with the reason. Tests (plugin): press
   submits the exact command; null command has no hotkey; stale command runs nothing and redraws;
   busy shows no hotkey. Command test: `forge next --json` for a ready task, a waiting item and a
   merge only a human may do (null).
3. Events. Event identity: item + kind + a value that changes only on a new occurrence: the review
   commit for findings, the head commit and check suite for failed checks, the head commit for
   ready-to-merge, the question text for a worker question, and the run's end time for a finished
   run (from the run records VIEWS adds). Seen identities are kept per repo in `$.store`; at
   session start and after a reload the current state is recorded as seen without starting turns.
   Changes found while Claude is working, or several in one refresh, go into one turn after the
   current one ends, one line each: plain item title, what happened, the `forge next` command for
   it. A failed submit keeps them unseen for the next refresh. Only interactive sessions get turns
   (`$.session.surfaces()` includes terminal or desktop) and never a session Forge itself started:
   Forge sets `FORGE_WORKER=1` in every worker, reader and reviewer it starts, and the mod is inert
   there. Each session acts only for its own repo (`$.session.repo()` matched to the board's repo
   root); two sessions on one repo each get the turn. Tests (plugin): two snapshots give one turn
   per change; progress gives none; the next refresh repeats none; two changes while busy give one
   turn after; a run that started and ended between refreshes gives one turn; reload gives none;
   a `FORGE_WORKER=1` session and a `claude -p` session give none; another repo's change gives
   none. Command test: every worker, reader and reviewer process gets `FORGE_WORKER=1`.
4. Approval. First step of APPROVE: prove in a real Claude Code (v2.1.287+) that a mod can start
   `ExitPlanMode` with given plan text so that Claude Code shows its own plan-approval prompt and,
   on approval, runs Forge's existing approval hook. If it can't, APPROVE removes the button,
   records why in the story notes, and Done-when 4 is met by Plan Mode alone. When it can: the
   button reads the story doc from disk at press time (CRLF normalised to LF), takes the part
   `forge next` names for approval exactly as Plan Mode approval expects, and starts the prompt
   with it; all trust checks stay in `forge hook approval` unchanged (digest, completed call,
   replay, one waiting story). Request changes: an Input whose text is submitted as the user's
   words; it records nothing. Tests: plugin test that the plan text equals the doc's part byte
   for byte, including a CRLF doc; command tests that the hook records the approval from that
   payload, refuses after the doc changed between press and approval, and that Request changes
   records nothing.
5. Delivery. Marketplace `forge` at Forge's repository root (`.claude-plugin/marketplace.json`)
   lists plugin `forge` whose source is the `src/forge/mod` folder at tag `v<version>`, where
   version is pyproject's; a test fails when they differ, so each version bump moves it. `forge sync` adds, in `.claude/settings.json`,
   `extraKnownMarketplaces.forge` (GitHub source, Forge's repository) and
   `enabledPlugins["forge@forge"] = true`, leaving every other entry as it was; a malformed
   settings file is reported by sync and left unchanged. Version: the mod runs the repo's own
   Forge through the repo's launcher (`.forge/hooks.sh`, the same one the hooks use), with argv and
   no shell, working directory the session's repo root; when `forge --version` is below the
   version that added `--json`, the pane and band show one line: `This repo's Forge is too old
   for the pane: upgrade Forge here.` A running session picks the mod up after `/reload-plugins`
   or a restart. Doctor: Claude Code missing or older than v2.1.287 is one warning line and keeps
   exit status 0. Tests: command tests of sync's settings output (fresh, repeated, with unrelated
   entries, malformed), of doctor's warning and exit status, and that Codex files are unchanged;
   plugin test of the too-old line; `claude plugin validate --strict` passes. CI installs a pinned
   Claude Code with npm to run `claude plugin test` and `validate`.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| VIEWS | Machine views and run records | `--json` on `forge next` and `forge board` with the fields in details 1-3, run start and end records, `FORGE_WORKER=1` for every process Forge starts, the guide's "Machine views" section | 1, 2, 3 | src/forge/nextstep.py, src/forge/board.py, src/forge/cli.py, src/forge/repo.py, src/forge/worker.py, src/forge/close.py, src/forge/codex.py, src/forge/templates/skill.md | tests/test_machine_views.py, tests/test_run_records.py | | no |
| PANE | Pane and next-step band | The plugin skeleton, `/forge`, the pane, the band and its hotkey, the launcher call and too-old line, the guide's "The Forge pane" section | 1, 2 | src/forge/mod/.claude-plugin/**, src/forge/mod/hooks/hooks.json, src/forge/mod/hooks/register.ts, src/forge/mod/hooks/pane.ts, src/forge/mod/hooks/forge.ts, src/forge/mod/hooks/pane.test.ts, pyproject.toml, src/forge/templates/skill.md | src/forge/mod/hooks/pane.test.ts, tests/test_mod_plugin.py | VIEWS | yes |
| EVENTS | Turns when work needs the agent | Event identities, seen store, batching, session gating, the guide's "Forge events" section and the brief's line that workers never act on events | 3 | src/forge/mod/hooks/events.ts, src/forge/mod/hooks/events.test.ts, src/forge/templates/skill.md, src/forge/templates/brief.md | src/forge/mod/hooks/events.test.ts | PANE | yes |
| APPROVE | Approve from the pane | The proof step, then the button, the plan prompt and Request changes, or the recorded reason it was left out | 4 | src/forge/mod/hooks/approval.ts, src/forge/mod/hooks/approval.test.ts, src/forge/approval.py, src/forge/templates/skill.md | src/forge/mod/hooks/approval.test.ts, tests/test_mod_approval.py | PANE | yes |
| SHIP | Sync turns the mod on | Marketplace file pinned to the package version, sync's settings entries, doctor's warning, CI's plugin test job | 5 | .claude-plugin/marketplace.json, src/forge/sync.py, src/forge/doctor.py, src/forge/templates/skill.md, .github/workflows/forge-next.yml | tests/test_mod_sync.py | PANE | no |

New moving parts: one Claude Code plugin (mod) that Forge ships and sync turns on (Done-when 1-5)

## Notes

- Mods docs: code.claude.com/docs/en/plugins/mods/overview, /reference, /interface (v2.1.287+).
  Render sites `Pane`, `AbovePrompt`; `$.clock.every`, `$.process.run`, `$.prompt.submit`,
  `$.store`, `$.session.surfaces`, `$.session.repo`.
- All Forge rules stay in the `forge` command; the mod only reads the machine views, runs `forge`
  commands and draws. It never writes repo files.
- Guide sections: each task adds its own named section to skill.md so tasks don't edit the same
  lines.
