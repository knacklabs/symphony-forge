# Forge lives inside Claude Code

4 parts · Risks: code that runs inside every developer's Claude Code session · New moving parts: one Claude Code mod shipped with Forge

## What changes for you

- In Claude Code, a Forge pane beside the conversation shows every story and fix with its stage,
  what each worker is doing and for how long, the checks on each pull request, and open review
  findings. It stays current by itself, so nobody asks for status.
- The strip above the prompt always shows Forge's next step. Pressing 1 on an empty prompt runs
  it.
- When work needs the agent (a review found problems, checks failed, a pull request is ready to
  merge, a worker asked a question, or a run finished), Forge tells the session and the agent acts
  on it straight away. Progress such as a run starting or checks running only updates the pane.
- A story waiting for approval opens in the pane with its "What changes for you" and "Done when"
  exactly as written. Pressing Approve approves it; Request changes takes a note back to the
  agent. Only a person's key press or click counts.
- Plan Mode approval stays for Codex, the VS Code chat panel and any session without the Forge
  mod. Both record the same approval.
- `forge sync` turns the mod on for the repo, at the repo's Forge version. Codex works exactly as
  today.

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
3. **When a review finds problems, checks fail, a pull request is ready to merge, a worker asks a question or a run finishes, the session starts a turn that names it and the next step; progress only updates the pane.**
4. **A person can approve a waiting story from the pane, seeing its "What changes for you" and "Done when" exactly as written, and that records the same approval Plan Mode does; Plan Mode keeps working everywhere.**
5. **`forge sync` turns the mod on at the repo's Forge version, and Codex and sessions without the mod work as today.**

## Risks

- The mod is code that runs inside each developer's Claude Code session with their permissions.
  It only reads Forge's state and runs `forge` commands; it never edits files itself.
- Claude Code mods are one day old. If Claude Code changes how mods work, the pane can stop
  drawing; everything still works through the `forge` command as today.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

### Done-when details

1. Pane: rows for each story and fix from the board's machine view, each with its stage, running
   worker and elapsed time, pull request checks (pass, fail, running) and open findings count with
   their titles one level down. Refreshes on a timer (every 30 seconds) and after each Forge
   command the session runs. Narrow terminal: the pane sits above the prompt (Claude Code does
   this). Tests: `claude plugin test` cases that draw the pane from a fixture board and check the
   rows; a command test of the board's machine view on a repo with a story, a fix and an open
   pull request.
2. Band: one line, `1: <next command>` from `forge next`'s machine view, a digit-1 hotkey that
   runs it through the prompt as the user's own words, so it shows in the transcript. Nothing
   ready: the band shows the one-line state and no hotkey. Tests: plugin test pressing 1 submits
   the exact command; command test of `forge next`'s machine view.
3. Events: the mod compares each refresh with the last state it saw per item and starts one turn
   per change of these kinds only: review finished with blocking findings, checks failed, Ready
   to merge, a worker waiting for an answer, a worker or close run ended. The turn text names
   the item in plain words and gives `forge next`'s command for it. Runs starting and checks
   running only update the pane. A session gets events only for its own repo; two sessions on one
   repo each get them. While a turn is running, events wait and go in one turn after it. Tests:
   plugin tests feeding two board snapshots and checking exactly one submitted turn per change,
   none for progress, none repeated on the next refresh.
4. Approval keeps today's trust path: the person answers Forge's approval question
   (`forge hook approval`, AskUserQuestion), with all its checks. The pane's Approve button only
   starts that question (the coordinator asks it); the mod redraws the AskUserQuestion dialog for
   Forge approval questions with the story's top part above it, exactly as written, drawn from
   the story doc on disk, never from the model's text. Request changes sends the typed note to the
   agent as the user's words. Tests: plugin test that the dialog shows the doc's sections verbatim
   and the dialog reference once; command test that an approval answered this way records the same
   approval as Plan Mode.
5. Delivery: the plugin lives in the Forge package and in Forge's repository with a plugin
   marketplace file at the repository root. `forge sync` adds Forge's repository as a marketplace
   in `.claude/settings.json` pinned to forge.toml's version tag and turns the plugin on; it never
   touches other marketplaces or plugins. Doctor reports a Claude Code older than v2.1.287 in one
   plain line and treats it as a warning, never a failure. Codex files are unchanged. Tests:
   command test of sync's settings output and of doctor's line; `claude plugin validate --strict`
   passes on the plugin.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| VIEWS | Machine views | `forge next` and `forge board` print one JSON object each with a flag, holding what their text shows plus the run, checks and findings fields the pane needs | 1, 2 | src/forge/nextstep.py, src/forge/board.py, src/forge/cli.py, src/forge/templates/skill.md | tests/test_machine_views.py | | no |
| MOD | Forge pane, band and events | The Claude Code plugin with the pane, the next-step band and event turns, reading the machine views | 1, 2, 3 | src/forge/mod/**, pyproject.toml | src/forge/mod/hooks/*.test.ts, tests/test_mod_plugin.py | VIEWS | yes |
| APPROVE | Approve from the pane | The pane's Approve and Request changes buttons and the redrawn approval dialog showing the story's exact text | 4 | src/forge/mod/hooks/approval.ts, src/forge/approval.py, src/forge/templates/skill.md | src/forge/mod/hooks/approval.test.ts, tests/test_mod_approval.py | MOD | yes |
| SHIP | Sync turns the mod on | Marketplace file, sync's settings entries pinned to the repo's Forge version, doctor's version line | 5 | .claude-plugin/marketplace.json, src/forge/sync.py, src/forge/doctor.py, src/forge/templates/skill.md | tests/test_mod_sync.py | MOD | no |

New moving parts: one Claude Code plugin (mod) that Forge ships and sync turns on (Done-when 1-5)

## Notes

- Mods docs: code.claude.com/docs/en/plugins/mods/overview, /reference, /interface (v2.1.287+).
  Render sites `Pane`, `AbovePrompt`, `AskUserQuestion`; `$.clock.every`, `$.process.run`,
  `$.prompt.submit({ text, asUser: true })`, `$.store`.
- All Forge rules stay in the `forge` command; the mod only reads the machine views, runs `forge`
  commands and draws. It never writes repo files.
