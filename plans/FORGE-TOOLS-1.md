# Run Forge all in Claude, all in Codex, or both

8 parts · Risks: one new library from Anthropic · New moving parts: the Claude Agent SDK

## What changes for you

- One setting says which tools run Forge's work: Claude Code only, Codex only, or both (the
  default). Stories, plan reads, approval, tasks and fixes, close, review, CI, merge and the
  machine's line of agents and tests stay exactly the same whichever you choose.
- Work for the tool you are coordinating from runs inside your session, as its own background
  subagents: building, plan reads and questions. You see their progress, stop them and read their
  transcripts the way you do with any subagent. Forge starts no hidden programs for it.
- When a subagent finishes, your agent hands its result back to Forge with one command, and Forge
  records it and checks it as it does today, including the reminder to commit leftover changes.
- A subagent keeps its chat for the item from round to round while your session is open; in a new
  session the next round starts fresh with the whole brief. With one tool and no session open,
  nothing runs: the work waits for you.
- Work for the other tool runs through that tool's own kit: Codex as it runs today, and Claude
  through Anthropic's Agent SDK, resumable and cleanly stoppable, instead of a hidden `claude -p`.
- Questions about the code go to your session's explorer subagent; the separate `forge ask`
  command goes away.
- Reviews always run on Autoreview, on your repo's tool, with Autoreview's own default model and
  effort. A review model in your settings is no longer used, and `forge doctor` says so.
- If the chosen tool isn't installed, Forge stops and says so in one plain line and never quietly
  uses the other tool; `forge doctor` reports it and installs what it can.
- You can tell your agent "run everything in Claude", "run everything in Codex" or "use both", and
  it makes the change.

## Why

Developers use Claude Code, Codex or both. Today Forge decides for them: reviews run on Codex
whenever it is installed, and plan reads run on the tool that isn't coordinating. A team that wants
to stay on one tool can't. And when Forge runs Claude, it starts `claude -p` processes the person
can't see, follow or stop from their session; the same work done as the session's own subagents is
visible and native.

## Done when

1. **A repo can run Forge's work on Claude Code only, Codex only, or both, both is the default, and Forge's process is the same whichever is chosen.**
2. **Questions about the code are answered by the session's own explorer subagent, and the separate question command is gone.**
3. **Each build round for the tool the session coordinates from runs as that session's own background subagent, and one command hands its result back to Forge's usual records, checks and commit reminder.**
4. **A subagent keeps its item's chat across rounds while its session lasts and holds a place in the machine's agent line until it hands back, and in a repo on one tool nothing runs while no session is open.**
5. **Plan reads run the same way when the reader is the coordinating session's tool, and in a repo on one tool the reader is always that tool.**
6. **Work for the other tool runs through its own kit: Codex through its app server as today, and Claude through Anthropic's Agent SDK with one resumable session per item, live output and a clean stop, and Forge never runs `claude -p`.**
7. **Every review, light review and sign-off runs Autoreview on the repo's tool with Autoreview's own default model and effort, Forge never passes a review model, and `forge doctor` says when a review model in the settings goes unused.**
8. **When the chosen tool or what Forge needs to drive it isn't installed, Forge stops with one plain line and never quietly uses the other tool, and `forge doctor` reports it and installs what it can.**
9. **The coordinator's guide explains the setting and the subagent flow, and makes the right change when asked to run everything in Claude, everything in Codex, or both.**

## New and existing repos

- **New repos** (init or adoption): no `tools` line is written, so they run on both tools; work for
  the coordinating app's tool runs as session subagents from the first round. `forge sync` writes
  the new subagent roles (reader, fixer) for both hosts. `forge init` writes no review model. The
  Claude models new repos start with come from the Claude defaults fix, not this story.
- **Existing repos**: after moving to this release, nothing in `forge.toml` is rewritten; they run on
  both tools until their agent sets `tools` on request. What changes for them: work for the
  coordinating app's tool runs as session subagents; Claude work from Codex runs through the Agent
  SDK (`forge doctor --fix` installs it); `forge ask` is gone (the guide points to the explorer
  subagent); reviews stop using their review model, which stays in the file, and doctor says so in
  one line. Tested on a repo adopted on the previous release and upgraded.

## Risks

- A new library from Anthropic, the Claude Agent SDK, pinned to one release in an environment of
  its own, the way Forge already pins the Codex SDK. Reverting the change removes it.
- Removing `forge ask` is a one-way change for anyone who scripted it; the explorer subagent
  replaces it in both apps.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

The route of one run, decided in one place (`repo.route(cfg, tool)`, pinned by SETTING and used by
every later task), whatever `tools` says:

| The run's tool | Route |
|---|---|
| the coordinating app's | native: the session's own subagent (READS, HOLD, WORK) |
| the other app's | its kit: the Codex app server (today) or the Claude Agent SDK (SDK, SDKREAD) |
| any, with no coordinating app | `tools = "both"`: the kit, as today; one tool: refused (item 4) |

`tools` picks the run's tool: with one tool every run is on it; with `"both"`, `workers` picks the
builder and the reader is the other app when installed, as today. "The coordinating app" is today's
`story.COORDINATORS` lookup (`CLAUDECODE`, `CODEX_THREAD_ID`), moved to `repo.coordinator()`.

**How the existing tests switch.** `tests/conftest.py`'s `repo` fixture runs every test as if Codex
coordinates (`CODEX_THREAD_ID` set). Under the route above, every existing test with Codex workers
(about 70 files) would turn native. SWITCH moves those tests, before any route changes, to a
`claude_session` fixture (`CLAUDECODE=1`, no `CODEX_THREAD_ID`): under today's code the coordinator
doesn't change a worker's route, so they pass before and after, and after WORK they still drive the
Codex app-server stub. Tests whose read must stay on the Claude reader keep the Codex coordinator
and move to the stub Agent SDK in SDKREAD. Tests that drive a Claude worker from Claude Code become
native-flow tests in WORK, or move to a Codex coordinator and the stub SDK in SDK, whichever their
rule is about. SWITCH changes only tests and is split by file list if it passes about 400 lines.

Every new test file starts with `STORY = "FORGE-TOOLS-1"`; each Done-when item has exactly one
test function, `test_<n>_...`, and it runs the forge command (never imports forge), on a repo made
by `forge init` and, where the behaviour differs, on the newest adopted-release fixture moved to
this release.

### Done-when details

1. `forge.toml` gets `tools`: `repo.KEYS["tools"] = str`, `repo.DEFAULTS["tools"] = "both"`,
   `repo.CHOICES["tools"] = ("both", "claude", "codex")`. `repo.worker()` puts every item on `tools`
   when it names one (design work uses that tool's `design_models`, with no fallback to the other
   tool); with `"both"` it is today's `workers` rule. `workers` keeps its meaning and is ignored
   under one tool (owner, 2026-09-30), so `forge work`'s fallback from a failed Claude design run
   to Codex (`worker.work`, today gated only on `workers == "split"`) also requires `tools =
   "both"`. SETTING also pins `repo.route(cfg, tool) -> "native" |
   "kit"` and `repo.coordinator() -> "claude" | "codex" | None`, and adds no other caller yet.
   Test (one): no `tools` reads as both and `forge work` from Claude Code with `workers = "codex"`
   builds through the Codex app-server stub; `tools = "gemini"` refuses as `tools must be one of
   both, claude, codex`; `tools = "codex"` with `workers = "claude"` builds on Codex with the Codex
   build entry; `tools = "claude"` with `workers = "split"` and a user-facing part whose stub
   Claude run fails refuses and starts no Codex; the adopted-release repo upgraded keeps
   `forge.toml` byte for byte.
2. `forge ask` is removed: `src/forge/ask.py`, its `cli.ROUTES` entry, its listing in
   `docs/commands.md`, codex.py's `"Ask"` kind branches, and its tests. The command count stays at
   the ceiling of 23 because READS adds `forge handback` in the same change. The skill's intent row
   `"Ask Codex about this code"` becomes `"Ask about this code"` → hand the question to the
   `explorer` subagent role, which `forge sync` already writes for both hosts on the explore entry.
   Test (one): `forge ask "x"` fails as an unknown command; `forge --help` lists `handback` and not
   `ask`; the synced skill's row names the explorer role; both hosts' explorer role files exist with
   the explore entry's model.
3. Native build rounds (WORK). When `repo.route` is native, `forge work <item>` keeps today's order:
   the checks that refuse before anything is held, then the item's lock (`codex._item_file(...,
   ".lock", kind)`) and an agent-line place, both held by the coordinating session's process (item
   4), then the checks and status commit it runs today inside the lock, so a second `forge work`
   while a round is handed out refuses as busy before it commits anything. `forge next`, the board
   and a second `forge work` see the round as running, as they do today. Then, instead of starting
   a program:
   - writes the short brief and the whole brief beside the item's record
     (`<item>.brief.md`, `<item>.fresh.md` in the item's threads folder) and records the pending
     round in the item's record: kind, round, role, session identity, lane entry id, and HEAD at
     the handout;
   - prints, and exits 0:
     `Run this round as a background <role> subagent of this session, working in <checkout>.` then
     either `Continue subagent <id> with: Read <short brief path> and follow it.` followed by
     `If this session can't reach it, start a new <role> subagent with: Read <whole brief path>
     and follow it.` (item 4's rule) or `Start a new <role> subagent with: Read <whole brief path>
     and follow it.` with today's "because ..." reason, then
     `When it ends: forge handback <item> --round <n> --agent <its id>, with its last message on
     stdin.`

   The brief template's "the checkout you were started in" names the checkout's path for every
   run (`$checkout` in `brief.md`), so a subagent started from the coordinator's main checkout
   works in the item's worktree. A native round skips only the kit's own readiness check, the
   Codex SDK probe in `worker.ready`; the models entry and Codex's project-trust check stay, since
   the session's hooks need that trust too.

   Roles: `worker` (build) for a task, a new `fixer` role (lite) for a fix, `frontend` (now the
   design kind) for design work, so each round runs on that tool's entry for its kind. A native
   round's kind is always its role's: today's switch to the fix entry for later Codex rounds
   (`later` in `worker.work`) applies only to kit rounds, because a continued subagent keeps its
   model, and the printed "Building ... with" line names the role's model. Under `split`, a
   user-facing part coordinated from Claude Code runs as a `frontend` subagent; split's fallback
   to Codex applies only to a Claude run through the SDK, as today's does to `claude -p`.
   `forge handback <item> --round <n> --agent <id>` (READS adds the command; WORK adds the work
   half) runs on the release the item's checkout pinned at the handout's HEAD (`repo.check_pin`
   reads the pin there for `handback`), so a round that changed the pin can't forward its own
   hand-back to another release; it reads the last message from stdin and does what today's round does after the worker
   ends: restore uncommitted `forge.toml` (`_restore_settings`); since native subagents don't
   carry the commit hook's `FORGE_WORKER=1` guard, also restore a `forge.toml` the round committed
   (any change since the handout's HEAD that `task.settings_allowed` doesn't permit) in one commit,
   with today's restore line; record a trailing `Question:` block, record the round's timing and
   run end, and update the session record (agent id, session identity, HEAD, rounds). When the
   checkout has uncommitted changes and this round hasn't been nudged, it prints
   `Send this to subagent <id>, then hand back again:` and the commit nudge (`COMMIT_NUDGE`), keeps
   the place, and marks the round nudged; the second hand-back finishes as today, with today's
   leftover-changes warning. An empty stdin records the round failed. `forge land` stops after a
   native round is handed out with `Next: run the subagent, forge handback <item>, then forge land
   <item>`, and runs no close. Test (one): with `workers = "claude"` under a Claude Code session,
   `forge work` starts no program (the stub `claude` and Codex stubs record no call), prints the
   instruction with the `worker` role, the task's checkout path and the whole brief, and the
   whole brief names that path; `forge next` says the round runs as a subagent; a second `forge
   work` refuses as busy and HEAD is unchanged; a hand-back with an uncommitted file prints the
   nudge and keeps the place, a second hand-back after the commit frees it and records the timing;
   a hand-back ending in `Question:` is recorded and `forge next` shows it; an uncommitted edit to
   `forge.toml` is restored, and a committed one is restored in a new commit, also when it
   changed the version pin and the hand-back runs from the item's checkout; a fix uses the
   `fixer` role; a user-facing part under `split` from Claude Code uses `frontend`; `tools =
   "codex"` under a Codex session does the same on Codex with the stub Codex SDK not installed, and
   its second round, with distinct build, fix and lite models, continues the `worker` subagent and
   prints the build model; `forge land` after the handout stops with its Next line and runs no
   close, and after the hand-back proceeds to close; with one tool and no session `forge work`
   refuses with item 4's line and HEAD is unchanged.
4. The session holds the round (READS lands the hold; HOLD the rest). `native.session()` finds the
   coordinating session's process: the nearest ancestor of the forge process whose executable's
   base name starts with the coordinator's name, `claude` or `codex`, else the nearest `node`
   ancestor (an npm launch, where Windows' `codex.identity` gives only `node.exe`), read through
   the existing `codex.identity`; none found refuses with one line naming the app.
   Its identity owns the item lock and the lane entry (`machine.started(entry, session_pid)`, with
   `native: true` on the entry), so the place frees itself when the session ends, by the existing
   liveness rules. `forge handback` frees both; `machine.leave` removes a native entry whoever calls
   it. `forge stop` on a native entry frees the place and the lock, never signals the session, and
   prints `Stopped Forge's hold; stop the subagent in your session too.` Each handout carries its
   round number in the printed hand-back command; a hand-back whose `--round` isn't the item's
   pending round, because that round was stopped or a newer one was handed out, refuses with
   `That round was stopped or replaced, so Forge recorded nothing.` and leaves the pending round
   as it is. Continuing: when the recorded agent's session identity is the current session's, the
   instruction says continue with the short brief and, on the next line, start fresh with the
   whole brief if the session can't reach that subagent (a cleared conversation in the same
   process); otherwise it starts fresh with the whole brief, `because the session that ran its
   last round has ended`. A hand-back from another session than the round's refuses. In a repo
   on one tool, `forge work` and `forge read` with no coordinating app refuse before any commit,
   raised by `repo.route` so `forge work` gets it once WORK routes through it, with
   `repo.REFUSALS["no_session"]`: `Forge runs this repo's work inside a Claude Code or Codex session, and none is open here, so nothing ran.` →
   `open one in this repo and run forge <command> <item> there`. Test (one, on reads, the first
   native user): a read handed out holds one agent-line place (`forge lanes --json` shows it with
   kind read and `native: true`); a second read of another story waits in line when the shim's
   cores give one place; ending the session's process frees the place and the next read starts; a
   new read round in the same session continues the recorded subagent and prints the start-fresh
   line beneath, in a new session starts fresh with the reason; `forge stop` frees the place and
   leaves the session running, and after a new read is handed out the stopped round's hand-back
   refuses and the new round stays pending; with one tool and no session it refuses and HEAD and
   the item's state are unchanged; a session launched through `node` holds the place too. The
   test's session is a parent process named `claude` or `codex` (or `node`) that runs the forge
   command; the builder picks how the shim names it on each CI platform.
5. Native reads (READS). In `story.read`, with one tool the reader is that tool (no `wrong_app`
   refusal; a recorded reader of the other tool starts fresh with `forge.toml's tools is now
   <tool>`); with both it is today's choice, so the read is native only when the other app isn't
   installed. When the route is native, `forge read` does today's checks (less the Codex SDK
   probe, as in item 3), takes the item's lock and a place held by the session (item 4), takes the
   before-snapshot, builds today's prompt and whole prompt, and hands them out as in item 3 with the
   new `reader` role (grill kind, read-only instructions); everything the result step needs (read
   hash, round, spec and notes seen, the snapshot, the reader and why) goes in the read's pending
   record. `forge handback <target>` then runs today's result step, moved out of `read` into one
   function both paths call: discard on a changed file, the reader-failed refusal on an empty
   answer, findings numbering, the clean-read rule, the notes and the state commit. The record says
   `claude (<model>), a subagent of this Claude Code session because forge.toml's tools is claude`.
   Test (one): `tools = "codex"` under Codex (with the stub Codex SDK not installed) and `tools =
   "claude"` under Claude Code each hand out a read with the `reader` role and the story's
   checkout path, `forge lanes --json` shows its native entry until the hand-back frees it, and
   the hand-back records it with that tool's grill model; a file
   changed before the hand-back discards it; `No findings.` passes; numbered findings continue
   earlier rounds' numbers; `tools = "claude"` under Codex reads through the kit, not natively.
6. The Claude Agent SDK (SDK: the environment, the driver, the stub SDK, the boundary contract and
   workers; SDKREAD: reads, and the last `claude -p` gone). `src/forge/claude_sdk.py` mirrors codex.py's environment handling:
   one pinned `claude-agent-sdk` release in its own uv environment under Forge's data folder,
   `sdk_problem()`, `install()` (run by `forge doctor --fix`), never imported by Forge. A driver,
   `src/forge/claude_turn.py`, run by that environment's Python in its own process group, runs one
   turn: resume the item's recorded session id, or start one and report its id; the entry's model
   and effort; bypass permissions for workers and plan mode for reads, as today; `FORGE_WORKER=1`
   in its environment; each message streamed as one JSON line, which Forge writes to the log and
   passes through `repo.claude_output`. It runs inside `machine.agent_process`, so `forge stop`
   and an interrupt end it with its tree, as Codex turns end today. It replaces `worker._claude`
   and `worker._run` (SDK) and `story._claude_read` (SDKREAD); after SDKREAD no `"-p"` launch of
   `claude` remains. Boundary contract
   (principle 7): a test pins the SDK options and message fields Forge reads, against a stub SDK
   environment in `tests/conftest.py`, which replaces the stub `claude` for every existing test
   that runs a Claude worker (SDK) or read (SDKREAD) from Codex or with no app. Test (one, in
   `tests/test_tools_agent_sdk.py`; SDK writes it, SDKREAD adds its read cases to the same
   function): under Codex with `workers = "claude"` a first round starts a session through the
   stub SDK and records its id, the second resumes it with the short brief; the SDK saying the
   session is gone starts fresh with the whole brief and says why; `forge stop` ends the driver
   and its child (SDK); a read under Codex with `tools = "claude"` does the same in plan mode, and
   no test's stub `claude` sees `-p` (SDKREAD).
7. Reviews (SETTING). In `review.run` the engine is the repo's tool: the named one under one tool;
   with both, today's (Codex when installed, else Claude). Forge passes no `--model` and no
   `--thinking` for any review: normal, light (the Sol-at-medium pin goes) and sign-off (the
   `gpt-6.1-sol` high pin in `review.signoff` and its confirmation check go; it records the model
   Autoreview reports). `[models.review]` is never read for a review; `forge init` writes none;
   nothing rewrites an existing one. Doctor prints one note line when `forge.toml` has one:
   `- Note: reviews don't use forge.toml's review model; Autoreview runs on its own default model
   and effort.` A note isn't a problem row and doesn't change the exit code. Test (one): `forge
   close` with `tools = "claude"` and Codex installed passes `--engine claude` and no model, even
   with a Claude review entry; with `tools = "codex"` `--engine codex` and no model; with both and
   a review entry, today's engine and no model; the light review and sign-off pass no model, and
   sign-off accepts the model Autoreview reports; doctor on the adopted-release repo upgraded shows
   the note and exits 0, and `forge.toml` is unchanged; a new repo's doctor shows no note.
8. One refusal (CHECKS), in `repo.REFUSALS`:
   `"tool_missing": ("forge.toml's tools is {tool}, so this runs on {name}, which isn't installed. Forge won't use the other tool instead.", "forge doctor --fix")`.
   Raised before any state commit wherever a one-tool run would otherwise need a missing program:
   the review (the engine's program: `claude`, or `CODEX_BIN` or `codex`) and a kit run (the Codex
   SDK or the Claude Agent SDK not installed); the worker's check moves into `worker.ready`, before
   the status commit. `forge close` checks the review engine's program before `_merge_default`,
   so a missing engine refuses before close merges the default branch in. Doctor: with one tool,
   a row when that tool's program is missing (`INSTALL["codex"] = "npm install -g
   @openai/codex"`); a tool's SDK row (the Codex SDK for Codex, the Claude Agent SDK for Claude)
   whenever work could reach that tool's kit: the tool's program is installed and either `tools`
   is `"both"` (a run with no coordinating app, or from the other app, uses the kit) or `tools`
   names that tool and the other app is installed (it could coordinate); `--fix` installs either
   SDK. Test (one): each missing case refuses with the line, starts nothing on the other tool and
   leaves HEAD and the item's state unchanged, the review case on a branch whose default branch
   has new commits, so close hasn't merged them; doctor shows each row, including the Codex SDK
   row with `tools = "both"` and only Codex installed, and `--fix` installs the SDKs into the stub
   data folder; an adopted-release repo upgraded shows the Claude Agent SDK row until fixed.
9. The guide (SETTING writes it; each later task updates its own part, as the review rules
   require). `src/forge/templates/skill.md` gets `## Tools`, at most about 40 lines in the end:
   - **Who does what**: the coordinator is the app the developer opens; `tools` says which tools
     run Forge's work; the route table above in words; reviews on Autoreview's own defaults.
   - **Running a handed-out round** (READS, HOLD, WORK): run the printed instruction as a background
     subagent of the named role, continue the named subagent when told to, and run `forge handback`
     with its last message and id; send the nudge when asked; never edit the brief.
   - **Upgrade first**: an older Forge refuses the `tools` key, so follow Upgrade Forge before
     adding it.

   Intent rows: replace `"Switch to Codex workers" or "Change the test command"` with `"Change the
   test command"`, and add, each `Ask, then in a fix: ..., forge close <fix>`:
   `"Run everything in Claude"` → `tools = "claude"`, `workers = "claude"`, then `forge sync`;
   `"Run everything in Codex"` → `tools = "codex"`, `workers = "codex"`, then `forge sync`;
   `"Use both"` → `tools = "both"`.
   The worker brief (`src/forge/templates/brief.md`) says a subagent never runs `forge handback`,
   `forge work` or `forge stop` itself. `docs/guide.md` gets one settings paragraph. The synced
   copies in `.claude/skills/forge/` and `.codex/skills/forge/` are written with `forge sync`.
   Test (one): the synced skill holds the three intent rows, the route words and the upgrade step;
   the brief holds the never-run line; the copies match the template.

## Tasks

Every part may add its paragraph to `src/forge/templates/skill.md` and regenerate `.claude/skills/forge/` and `.codex/skills/forge/` with `forge sync`; those are left out of the Scope column so parts of this story and FORGE-BOARD-2 that share only the guide run in parallel. Each part merges main, keeps every other part's paragraph and regenerates the skills.

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| SETTING | Tools setting | The `tools` key, `repo.route` and `repo.coordinator` pinned, workers following `tools`, reviews on the repo's tool with Autoreview's defaults and doctor's unused-model note, the skill's Tools section and intent rows | 1, 7, 9 | `src/forge/repo.py`, `src/forge/story.py`, `src/forge/worker.py` (the design fallback's `tools` gate), `src/forge/review.py`, `src/forge/init.py`, `src/forge/doctor.py`, `src/forge/templates/brief.md`, `docs/guide.md`, the existing tests that assert a review model | `tests/test_tools_setting.py`, `tests/test_tools_reviews.py`, `tests/test_tools_guide.py` | | no | |
| SWITCH | Tests coordinate from Claude Code | The `claude_session` fixture and the existing Codex-worker tests moved onto it, passing before and after the route change | 1 | `tests/conftest.py` and the existing tests that run a Codex worker | the moved tests | | no | |
| READS | Reads as session subagents | `forge handback` in and `forge ask` out (the explorer subagent answers questions), the session lookup and its hold of the item lock and agent-line place, native cold reads with the `reader` role and the read's result step moved into one function both paths call | 2, 5 | `src/forge/native.py`, `src/forge/story.py`, `src/forge/machine.py`, `src/forge/cli.py`, `src/forge/ask.py`, `src/forge/codex.py`, `src/forge/worker.py` (`ready` skips the Codex SDK probe on a native route), `src/forge/roles.py`, `docs/commands.md`, `docs/guide.md`, `.claude/agents/`, `.codex/agents/`, `tests/test_steer_ask.py`, `tests/test_steer_ask_model.py` and the `forge ask` cases in other tests | `tests/test_tools_native_reads.py`, `tests/test_tools_questions.py`, `tests/test_subagent_roles.py` | SETTING, SWITCH | no | |
| HOLD | The session holds handed-out work | `forge stop` and `forge next` for handed-out runs, the round number that refuses a stopped or replaced round's hand-back, the continue-or-start-fresh rule, the no-session refusal | 4 | `src/forge/native.py`, `src/forge/machine.py`, `src/forge/nextstep.py`, `src/forge/repo.py`, `src/forge/story.py`, `.codex/skills/forge/` | `tests/test_tools_session_hold.py` | READS | no | |
| WORK | Build rounds as session subagents | Native build rounds with the `worker`, `fixer` and `frontend` roles, also under `split`, in the item's checkout, with the busy check before the status commit, the work half of `forge handback` (settings restore, committed included, question, nudge, timing, session record), `forge land` stopping at a handed-out round | 3 | `src/forge/worker.py`, `src/forge/native.py`, `src/forge/repo.py` (`check_pin` for `handback`), `src/forge/land.py`, `src/forge/roles.py`, `src/forge/templates/brief.md`, `.claude/agents/`, `.codex/agents/`, the existing tests that drive a Claude worker from Claude Code | `tests/test_tools_native_work.py`, `tests/test_subagent_roles.py` | HOLD | no | |
| SDK | Claude workers through the Agent SDK | The pinned SDK environment, its `doctor --fix` install and its driver, Claude workers run through it, the stub SDK for tests, the boundary contract | 6 | `src/forge/claude_sdk.py`, `src/forge/claude_turn.py`, `src/forge/worker.py`, `src/forge/doctor.py`, `tests/conftest.py` and the existing tests that drive the stub `claude` for a worker | `tests/test_tools_agent_sdk.py`, `tests/test_contracts.py` | WORK | no | |
| SDKREAD | Claude reads through the Agent SDK | Claude cold reads run through the driver in plan mode, `story._claude_read` and the last `claude -p` removed | 6 | `src/forge/story.py`, `src/forge/claude_turn.py`, `tests/conftest.py` and the existing tests that drive the stub `claude` for a read | `tests/test_tools_agent_sdk.py` | SDK | no | |
| CHECKS | Missing tools stop plainly | The `tool_missing` refusal everywhere, doctor's program and SDK rows and `--fix` | 8 | `src/forge/repo.py`, `src/forge/worker.py`, `src/forge/story.py`, `src/forge/review.py`, `src/forge/close.py`, `src/forge/doctor.py`, `.codex/skills/forge/` | `tests/test_tools_missing.py` | SDKREAD | no | |

New moving parts: the Claude Agent SDK, pinned in its own environment (item 6)

## Notes

- SETTING and SWITCH run side by side (no shared file); the rest run one after another, READS,
  HOLD, WORK, SDK, SDKREAD, CHECKS, because each changes the skill or shares `story.py`,
  `worker.py` or `native.py` with the next. `forge ask` leaves in READS together with `forge
  handback` arriving, so the command count never passes 23.
- Starts after the in-flight fixes that change the same code merge: the Claude defaults fix (init's
  Claude models and the roles) and the fix that keeps one worker and reader chat per item across
  rounds (worker.py, story.py). READS, HOLD and WORK build on that fix's session record.
- Module sizes: `story.py` is at 987 lines; READS moves the read's result step into one function
  and SDKREAD removes `_claude_read`, so it stays under 1,200. `native.py` and `claude_sdk.py` are new
  and small. The command count stays at 23: `forge handback` in, `forge ask` out.
- Native subagents don't carry `FORGE_WORKER=1`, so the commit hook's worker settings guard doesn't
  see them; `forge handback` restores an uncommitted `forge.toml` as today's round end does and a
  committed one in a new commit (item 3), and the brief says a subagent never runs `forge stop`,
  `forge work` or `forge handback`.
- Forge's own repo stays on both tools with `workers = "split"`, coordinated from Claude Code: its
  user-facing parts build as session `frontend` subagents, everything else on Codex as today.
- No client repo is named anywhere in this story's code, tests, texts or commits.
- Owner decisions (2026-10-09): Forge's process stays identical whatever the tool. Same-tool repos
  run workers (with the commit nudge), cold reads, questions and the explorer as the coordinating
  session's own background subagents, with no CLI: `forge work` and `forge read` write the brief
  and hold the machine-line place, the session runs the subagent, one command hands the result
  back, Forge keeps the rules, records and gates; no session open means the work waits. Native
  subagents continue the same chat per item and count in the machine's agent line. Claude
  coordinating with Codex building keeps the Codex app server; Codex coordinating with Claude
  building uses the Claude Agent SDK, one resumable session per item, streamed, with a clean stop;
  `claude -p` is removed everywhere. Autoreview stays an external program. Claude defaults (build
  Sonnet 5.5 xhigh, reads Opus 5.5 high, explore Haiku 5.5 high) ship in the Claude defaults fix,
  not here.
- Owner decisions (2026-10-10):
  - Native whenever the run's tool is the coordinating session's, under every `tools` value,
    `both` included; work for the other tool goes through its kit (Codex app server, Claude Agent
    SDK). Forge's own repo builds its user-facing parts as session subagents. The larger test
    change (the Codex-worker tests moving to a Claude Code session) is accepted.
  - `forge ask` is removed everywhere; the explorer subagent replaces it; the command count stays
    23 with `forge handback`.
  - Autoreview always runs on the repo's tool with its own default model and effort for normal,
    light and sign-off reviews; Forge never passes a review model; a review entry in `forge.toml`
    is ignored and doctor says so in one line; existing repos keep the entry and nothing rewrites
    it.
- Owner decision (2026-09-30) that still holds: with one tool, `tools` wins and `workers` is
  ignored, and the skill's rows set both keys. Superseded: sign-off pinned per tool (2026-09-30,
  now Autoreview's defaults, 2026-10-10) and `forge ask` following `tools` (2026-09-30, now the
  explorer subagent, 2026-10-10).
