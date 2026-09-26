# Codex builds your tasks and picks up where it left off

## What changes for you

- Set `workers = "codex"` in `forge.toml` and `forge work` builds each task or fix with Codex
  instead of Claude Code. The worker gets the same brief, works with full access in the task's own
  checkout, and is closed and reviewed exactly as before.
- Each kind of work has its own model and reasoning effort in `forge.toml`: building a task, a fix
  round, a quick fix, a cold read and a review. Building and fixing also name the model and effort
  of the subagents that make the edits, for example Sol at medium leading and Luna at max editing.
  Reviews run on Astra. Your agent keeps these settings: it asks you, then changes them in a fix.
- Each task gets its own Codex conversation, and you can find it in the Codex app by its name, for
  example "Build · <story>/<task> · <task name>". Fix rounds show as "Fix", quick fixes as "Lite"
  and cold reads as "Grill".
- When a review or a failing check sends the work back, the fix round continues that same
  conversation. The worker already knows the task and is told only what was found and what changed,
  so it comes back sooner. If the conversation can't be continued, Forge starts a fresh one and
  tells you why. If the plan changed, Forge waits for your approval first.
- Nothing keeps running between commands. Each `forge work` starts Codex and stops it again, even
  when it fails or you press Ctrl-C, and only one runs per task at a time.
- `forge doctor` checks the Codex SDK that Forge uses, and `forge doctor --fix` installs it. With
  Codex workers on, doctor fails, and `forge work` refuses, when Codex doesn't trust the project,
  because Forge's safety hook only runs in a trusted one.
- The cold read of a story or spec always runs on the other family from whoever coordinates:
  under Claude Code it runs on Codex, read-only, and under Codex it runs on Claude. The reader never
  shares the author's family.
- The new Forge doesn't use the Claude Codex plugin, and the guide shows how to uninstall it.
- Autoreview still reviews every piece of work, now on the review kind's model.

## Why

In the old Forge, every hand-off to Codex went through a Claude plugin and started a brand-new
conversation. The worker re-read the repository each time, and every fix round started cold again.
The new Forge doesn't use that plugin, and until this story it refuses Codex workers altogether.

Codex's own SDK lets a program start a named conversation, stop, and pick the conversation up
later. A check on the pinned SDK version confirmed it: a conversation started by one short-lived
process was picked up by a second one with its memory intact, and 99% of the second turn's input
came from cache. So Forge can keep one conversation per task without running anything in the
background.

## Done when

1. With Codex workers chosen, `forge work` builds a task or fix as one turn on a new Codex
   conversation with full access. Its progress shows in the terminal and the work log. The
   conversation is named "<kind> · <story>/<task> · <task name>" for a task, or
   "<kind> · <fix name> · <why>" for a fix.
2. Every request Codex sends to Forge, known or unknown, gets a decline and is logged, and nothing a
   request asks for runs. Forge checks that it can put its declining handler in place before it
   records any status; if it can't, `forge work` refuses before any conversation starts.
3. Each call uses its kind's models from `forge.toml`: the model and effort, and for building and
   fixing the subagents' model and effort. A missing kind or an unknown key makes `forge work`
   refuse and say what to fix. The settings are read again on every call, from the item's own
   checkout.
4. When a turn starts, the item's turn log on this machine gets a "started" line. When Codex
   reports that the turn ended, the log gets a line with these fields:
   - the conversation's id, the turn's id and its kind;
   - whether it continued the conversation, and if not, why it started fresh;
   - its status as Codex reported it;
   - its start and end;
   - its token counts, left blank when Codex doesn't report them.
5. Only one `forge work` runs per task or fix at a time, and a second one refuses and says to wait.
   Forge records its Codex process as soon as the process starts, before any conversation, and the
   conversation right after that starts. A process is known by its id, its start time and its
   command, so an id the system reuses is never mistaken for it. When Forge can't tell, it treats
   the owner as still running and refuses.
6. When `forge work` ends, whether normally, on an error or on Ctrl-C, no Codex process of it is
   left. A leftover one from a crash is stopped by the next `forge work` or by `forge doctor`.
7. A fix round, or any later `forge work`, continues the item's conversation under the name "Fix".
   It tells the conversation the findings, the failing checks, the new commits, and every change git
   sees in the checkout since its last turn, including new files. A very large change is listed by
   file instead of shown in full.
   - Forge starts fresh, and says why, when the conversation isn't recorded here, can't be
     resumed, was started in another checkout, or its history was rewritten underneath it.
8. If the story's approved part changed, `forge work` refuses before it records any status, until
   the change is approved again. The conversation started under the old approval is then not
   continued.
9. If an earlier `forge work` crashed, the next one stops that call's leftover Codex process first,
   then reads the conversation back.
   - A turn whose end was never logged is logged with the status Codex now reports, or as "lost"
     when Codex reports none. Forge never records a finished status that Codex didn't report.
   - If Codex still says the turn is running, `forge work` refuses, so two turns never run for one
     item.
10. The first cold read of a story or spec runs on the family that didn't coordinate: under Claude
    Code on a read-only Codex "Grill" conversation, and under Codex on Claude, each with the grill
    kind's models. If Forge can't tell who coordinates, `forge read` refuses and says how to run it.
    - Recording the amendment runs no model.
    - A failed or interrupted read leaves both the notes and the story's state unchanged.
    - A file change during the read discards it.
11. With Codex workers chosen, `forge doctor` fails on a missing or wrong Codex SDK and on a
    project Codex doesn't trust, runs its hook health check, and reminds you to approve Forge's
    hooks when Codex asks. `forge work` refuses to start Codex in a project Codex doesn't trust.
    `forge doctor --fix` installs the pinned SDK.
12. A smoke test drives the real pinned SDK through six steps: start, naming, resume, a declined
    request (a read-only turn asks to write a file, Forge declines, and the file isn't written),
    events and shutdown. It runs wherever the SDK is installed, on a developer machine and in an
    optional CI job that installs it.
13. Nothing in the new Forge package, its templates or its docs uses or mentions the Claude Codex
    plugin, except the guide's section on uninstalling it. The old Forge's mentions go when the old
    Forge is removed. The guide explains three things:
    - Codex workers and where their model settings live;
    - conversation names;
    - how to uninstall the plugin.
14. This repository builds its work with Codex workers. Its old per-role model choices now live in
    its `forge.toml`, and a test checks both.
15. A Codex worker builds the plugin-removal task.
    - Before the build, `forge doctor` shows that the project is trusted and that its hook health
      check passes.
    - The task's pull request shows the conversation name and the turn-log lines proving that the
      first build and a later round used one conversation. It also shows the output of one real
      smoke-test run.
    - It then passes review and its checks, and a human merges it.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SDK | Codex SDK set up and checked | The pinned SDK (openai-codex 0.156.1) in Forge's own environment, harvested from the earlier setup work, and `forge doctor --fix`, which creates it. With Codex workers chosen, doctor checks that environment and its bundled Codex program instead of a standalone `codex`. It fails on an untrusted project, still runs the hook health check, and prints the note about approving Forge's hooks | 11 | `src/forge/codex.py`, `src/forge/doctor.py`, `src/forge/cli.py` | `tests/test_codex_setup.py` | — | yes |
| BUILD | Codex builds a task or fix | `forge work` with Codex workers runs the brief as one turn on a new, named Build or Lite conversation, with full access and approval policy "never". One handler answers every request Codex sends, known or unknown, with a decline; the SDK check confirms the handler can go in before any status is recorded, and it is tested with an unknown method. The `[models.<kind>]` table in `forge.toml` is read from the item's own checkout: build, fix, lite, grill and review, with subagents for build and fix. Claude workers take a kind's model and effort, and Autoreview gets the review kind's model. `forge work` refuses an untrusted project with Codex workers. The driver reports the Codex process first. Events go to the terminal and the work log, the turn log gets a "started" line and an end line, and the client is closed in a `finally` block. The runner takes the item, the kind, the name, the sandbox and an optional conversation, and returns the conversation, the turn, the status, the final text and the usage, so the reader can reuse it | 1, 2, 3, 4, 11 | `src/forge/worker.py`, `src/forge/codex.py`, `src/forge/codex_turn.py`, `src/forge/repo.py`, `src/forge/review.py` | `tests/test_codex_worker.py`, `tests/stubs/codex-app-server` | SDK | yes |
| RECORD | One worker per item, nothing left running | Right after the SDK client starts, and before any conversation, the Codex process is recorded by its id, start time and command. The conversation is added right after it starts, and each write is atomic. Records, locks and logs sit in git's shared folder, one per task or fix, so every worktree sees the same ones and no two items share a file. The per-item lock holds its owner's identity, and a second `forge work` refuses. A stale lock or a leftover Codex process is acted on only when its identity matches; an owner Forge can't identify counts as running. The driver closes its client when the calling process goes away. The next `forge work` or `forge doctor` then clears or stops a leftover; doctor reports a running owner and never stops it | 5, 6 | `src/forge/codex.py`, `src/forge/worker.py`, `src/forge/doctor.py`, `src/forge/codex_turn.py` | `tests/test_codex_record.py` | BUILD | yes |
| RESUME | Fix rounds continue the conversation | Any `forge work` after an item's first recorded turn resumes the recorded conversation as a fix round named "Fix", on the fix kind's models. It sends the fresh brief, the new commits, and the change git sees since the turn started, including untracked files, listed by file when very large. The record keeps the commit each turn started from. The four drift cases start fresh with a reason. The approval check runs in the worker before its "working" or "fixing" status commit, and a changed approval refuses until it is approved again. After a crash, the leftover process is stopped and the conversation read back; a turn with no end line is logged with the status Codex reports, or "lost", and a turn Codex says is still running refuses. The recovery is tested with two processes against the stub | 7, 8, 9 | `src/forge/worker.py`, `src/forge/codex.py`, `src/forge/codex_turn.py` | `tests/test_codex_resume.py` | RECORD | yes |
| READER | Cold read on the other family | The first `forge read` runs on the family that didn't coordinate, which Forge tells from the coordinator's environment: under Claude Code, a read-only "Grill" conversation through the same runner (read-only at start and on each turn); under Codex, Claude with the grill kind's model. Both use the grill kind's models, and an unknown coordinator refuses. `--amended` opens no model. A failed, interrupted or discarded read leaves both the notes and the story's state unchanged, and `codex exec` goes away. `forge init` writes the default models table, and the single `model` key goes, with a clear refusal for an old one | 10 | `src/forge/story.py`, `src/forge/init.py`, `src/forge/repo.py`, `src/forge/codex.py`, `src/forge/codex_turn.py` | `tests/test_codex_reader.py` | BUILD | yes |
| SMOKE | Real SDK smoke test | A smoke test runs against the real pinned SDK: start, naming, resume, a declined request (a read-only turn that asks to write a file, declined, and the file absent), events and shutdown. It runs locally whenever the SDK environment exists, and in an optional CI job that installs the SDK and isn't a required check. The required proof is one real run by the coordinator, whose output goes into the plugin-removal pull request | 12 | `.github/workflows/codex-smoke.yml` | `tests/test_codex_smoke.py` | RESUME | no |
| USE-CODEX | This repository builds with Codex | This repository switches to Codex workers. The old per-role model choices move into its `forge.toml` models table: build and fix led by Sol at medium with Luna at max subagents, quick fixes on Sol at medium, cold reads on Sol at high, reviews on Astra. A test checks that `forge.toml` says `workers = "codex"` and holds that table. It starts once this repository's `forge.toml`, with `repo = "forge-source"`, is on main | 14 | `forge.toml` | `tests/test_codex_config.py` | RESUME, READER, SMOKE | no |
| UNPLUG | Plugin gone, built end to end by Codex | The guide covers Codex workers and their model settings, the conversation names and the two uninstall commands. A test checks that nothing in the new package, its templates or its docs mentions the plugin outside the guide's uninstall section. A Codex worker builds this task after `forge doctor` shows the project trusted and the hook health check passing. The coordinator writes into its pull request body the conversation name, the turn-log lines proving that the first build and a later round shared one conversation, and its real smoke-test output; if review finds nothing, the coordinator runs one follow-up `forge work` turn so the later round exists. It starts only after this repository moves onto the new Forge | 13, 15 | `docs/guide.md` | `tests/test_no_plugin.py` | USE-CODEX | no |

New moving parts: the pinned Codex SDK in its own Forge-managed environment, about 300 MB once per machine (Done when 1, 11); one small script that the SDK environment's Python runs for each call, which starts Codex and stops it again, so there is no daemon (1, 6); per item, a conversation record, a lock file and a turn log in Forge's local folder inside `.git`, never committed (4, 5); an optional CI job that installs the SDK for the smoke test (12).

## Risks

- **Timing.** The code tasks start now, on the new Forge package that has already merged, and
  ahead of the switch, because the owner asked for Codex workers early ("Start with codex warm
  stories", 2026-09-26). That instruction overrides the rebuild decision's "nothing else starts
  until the switch" for this story. Only the last two tasks wait for this repository's `forge.toml`
  to be on main. That step belongs to the rebuild story, and Forge can't make a task wait on
  another story's task, so the coordinator starts those two only after it has merged.
- Full access with no approval prompts means a Codex worker can run any command. The guards are:
  - Forge's deny hook, which blocks destructive commands, skipped git hooks and merges. Codex runs
    it only in a trusted project, so doctor fails, and `forge work` refuses, an untrusted one.
  - the review of every diff against its Scope, which is where Scope is enforced;
  - the human merge.

  Nothing is sandboxed.
- Forge can't see whether Codex actually ran its hook. It claims only what it can see: the project
  is trusted and the hook health check passes.
- A process is recognised by its id, its start time and its command, so a leftover Codex process
  or a stale lock is never confused with an unrelated process that reused the id.
- Codex's server interface is marked experimental. The SDK is pinned to one exact version, and
  moving to a newer one is a deliberate change that reruns the contract and smoke tests.
- The smoke test talks to the real Codex, so it needs a Codex login and costs a little per run. The
  one required run is the coordinator's, and in CI the test stays optional.
- The SDK brings its own Codex program. It can differ from the `codex` that Autoreview uses, but
  both use the same login and the same conversation store.
- The SDK's built-in approval handler accepts command and file-change requests. Forge replaces it
  through a private attribute, checks the attribute is there before it records any status, and a
  contract test catches a new SDK version that moves it. No request can arrive before a
  conversation exists, and the handler goes in before the first one starts.
- Codex's settings format is still changing. This version already rejects the old "profile" line.
  Forge passes only the kind's model keys from its table, and an unknown key in the table fails
  loudly.
- Conversations pile up in the Codex app. Archiving them when work merges is left for later.
- Each person uninstalls the plugin on their own machine. Reinstalling it undoes the step.

## Notes

- **The amended spec** is `docs/specs/warm-codex-threads.md`. Its acceptance criteria 1–13 map to
  this story's Done-when items as follows:
  - 1 maps to items 1, 5 and 6;
  - 2 maps to 2;
  - 3 maps to 3;
  - 4 maps to 1 and 10;
  - 5 maps to 5;
  - 6 maps to 7 and 8;
  - 7 maps to 9;
  - 8 maps to 4 and 9;
  - 9 maps to 10;
  - 10 maps to 11;
  - 11 maps to 12 and the stub in BUILD;
  - 12 maps to 13;
  - 13 maps to 15.

  Where the spec still describes per-kind Codex settings files, one log line per turn, or
  interrupting a running turn, this story's owner decisions of 2026-09-26 govern: the models table,
  a started line plus an end line, and stop-then-read recovery. BUILD adds a note saying so to the
  spec.
- **Task-level grill, 2026-09-26.** Before more tasks were built, one read-only Codex cold read went
  through every task. Of its 30 items, the owner decided two (crash recovery; the cold reader's
  family), and the rest were settled by simple rules now written into the Done-when items, the task
  rows and these notes.
- **What the pinned SDK (openai-codex 0.156.1) does**, checked in its source and with live probes:
  - `Codex()` starts `codex app-server --listen stdio://` as a child of the calling process and runs
    `initialize` inside the constructor, and stops the server on close (terminate, wait, kill). There
    is no shared server, so each `forge work` or first `forge read` owns one for its lifetime.
  - Threads that aren't ephemeral are written to the Codex home. `thread_resume(id)` in a later
    process loads them (status `notLoaded`, then `idle`).
  - The resume probe ran two processes:
    - Process A started a read-only thread, named it, ran one turn and exited, and its app-server
      exited with it.
    - Process B found the thread by name with `thread_list(search_term=...)` and resumed it. The
      thread recalled the word from turn one.
    - Turn two read 25,600 of its 25,865 input tokens from cache.

    So no supervisor daemon is needed.
  - `thread_start` defaults to `ApprovalMode.auto_review`. Pass `ApprovalMode.deny_all` (approval
    policy "never") on start, on resume and on each turn. The smoke test's declined-request step
    alone uses approval on request in a read-only turn.
  - The SDK sends every server request, whatever its method, to one handler (the instance attribute
    `_approval_handler`), and writes the handler's return value back as the answer. The default
    handler accepts command and file-change requests and answers `{}` to anything else.
    - `Codex(config)` takes no handler. Right after `Codex(...)` returns, set
      `codex._client._approval_handler` to a function that logs the method and returns
      `{"decision": "decline"}` for every method, known or unknown.
    - If that attribute is missing, refuse before any thread exists; the SDK check looks for it
      before any status commit.
    - The stub sends an unknown method and checks the answer is a decline and that nothing ran.
  - `Sandbox.full_access` maps to danger-full-access, both for the thread and for the turn policy.
    For Grill, pass `Sandbox.read_only` on start and on every turn.
  - `Thread.set_name(name)` names a thread, and the name shows in the Codex app and in
    `thread_list`.
  - `TurnHandle.stream()` yields a turn's events and stops at `turn/completed`; `TurnHandle.run()`
    raises on a failed turn, so the driver reads the stream itself. `Thread.read(include_turns=True)`
    shows each turn's status. Usage comes from `thread/tokenUsage/updated` (`tokenUsage.last`).
  - The client's program comes from `CodexConfig.codex_bin`, falling back to the bundled program.
    Tests replace the bundled-program package with a stand-in pointing at the stub, so Forge's own
    code has no test hook.
- **How the SDK picks up settings.** This was checked with a throwaway Codex home, reading the model
  and effort that `thread/start` reports:
  - The thread's own folder (`cwd` on `thread_start`) decides which project `.codex/config.toml`
    applies, not the folder the app-server process started in.
  - The project layer applies when the user's Codex config trusts the project. A task worktree
    beside the main checkout gets its main repo's trust, because Codex resolves a worktree through
    its main repo.
  - Profiles can't be switched through the app-server:
    - `codex --profile x app-server` is refused;
    - a `profile = "x"` line inside the config is rejected as legacy.
  - What works is passing settings as the thread's `config` overrides, which was verified in a
    worktree. Forge passes the kind's models this way on `thread_start` and on `thread_resume`:
    `model`, `model_reasoning_effort`, `agents.default_subagent_model` and
    `agents.default_subagent_reasoning_effort`. A Claude worker or reader gets the kind's model and
    effort through `claude --model --effort`; subagent keys under a Claude kind refuse.
- **The models table** in `forge.toml` (owner decision, 2026-09-26) keeps `harness.yaml`'s per-work
  routing:
  - `[models.build]` and `[models.fix]`: `gpt-6-sol` at medium, with `gpt-6-luna` at max
    subagents;
  - `[models.lite]`: `gpt-6-sol` at medium;
  - `[models.grill]`: `gpt-6-sol` at high;
  - `[models.review]`: `gpt-6-astra`, passed to Autoreview as `--model codex=<model>`.

  Each kind has `model` and `effort`, and build and fix may add `subagents` and `subagent_effort`
  as a pair. Values are strings; Codex checks the effort names. Codex's own role files in
  `.codex/agents/` (such as the Sol-at-high debugger) stay as Codex's, and `forge sync` merges only
  Forge's hooks key into `.codex/config.toml`. An old single `model` key refuses, telling you to ask
  your agent to move it into the table; no client has one yet, because the table lands before the
  release candidate.
- **Who coordinates.** Claude Code sets `CLAUDECODE=1` in the commands it runs; Codex sets its own
  session variables. Forge reads these to pick the other family for the cold read, and refuses when
  neither is present.
- **Harvest** (done in SDK) from `factory/scripts/forge_cli/codex_sdk.py` on
  `feat/FORGE-WARM-1-SDK-SETUP`: the pin, the environment folder, the ready marker, the import probe
  and the uv install steps.
- **Two files:**
  - `src/forge/codex.py` is the Forge side and never imports the SDK. It holds the pin, the
    environment, the doctor checks, the install, the kind's models, the record, the lock, the turn
    log, and `run(checkout, item, kind, name, prompt, sandbox, thread=None)`, which returns the
    conversation id, the turn id, the status, the final text and the usage.
  - `src/forge/codex_turn.py` is the script the SDK environment's Python runs. It reads one JSON
    request on stdin and constructs the client. It prints the app-server's process id at once,
    before installing the handler or starting a thread. It then starts or resumes the thread, prints
    its id, names it and runs the turn. It prints one JSON line per event, then a result line with
    the status, the final text and the usage. It closes the client in `finally`, and when the
    calling process goes away.
- **Process identity:** a process is its id plus its start time plus its command. On POSIX the start
  time and command come from `ps -o lstart=,command= -p <pid>`, and on Windows from PowerShell
  `Get-Process`. The record and the lock both store them. A stale lock or a leftover child is acted
  on only when they match; if they can't be read, the owner counts as running.
- **The record, the lock and the logs** live in git's shared folder (`git rev-parse
  --git-common-dir`), so every worktree sees the same ones:
  - `forge/threads/task/<STORY>/<TASK>.*` and `forge/threads/fix/<name>.*`, so no two items share a
    file, even on a disk that ignores capitals;
  - `<item>.json` holds the app-server's identity (written first), the conversation id, the
    checkout folder, the approval, the commit each turn started from and HEAD at the end of each
    turn. Every write goes through a temporary file and a rename;
  - `<item>.lock` is created exclusively and holds its owner's identity;
  - `<item>.log` gets a JSON "started" line per turn and a JSON end line with the fields in Done
    when 4. Times come from Forge's clock;
  - the event stream still goes to `.git/forge/work-<item>.log`;
  - all of it is machine-local and never committed.
- **Order in `worker.work`:**
  1. the checks that change nothing: the approval-change refusal, the SDK and handler check, the
     models, and project trust for Codex workers;
  2. the lock;
  3. the leftover-process cleanup and the read-back of any unfinished turn;
  4. the "working" or "fixing" status commit;
  5. the run.

  A refused call therefore changes no committed state.
- **The resumed turn's text:** today's fix-round brief, then `git log --oneline <start>..HEAD`,
  then the diff from the commit the last turn started from to the working tree, with untracked,
  non-ignored files included through a temporary index. Over 200 KB, the diff is replaced by the list
  of changed files.
- **Conversation names:** Forge produces only Build, Lite, Fix and Grill. Review, Explore and Debug
  are named in the guide as advice for threads opened by hand.
- **Worker refusal:** the refusal "Codex workers come with the warm-threads story" goes, and the
  v1 worker test stops expecting it.
- **Tests:**
  - Each test file declares `STORY = "<this story's key>"`, and its `test_<n>_` names cite this
    story's Done-when items; the rules test counts criteria per story.
  - Stub-based tests run the pinned SDK without its bundled program: a cached test environment
    with the SDK installed `--no-deps` plus its runtime libraries (pydantic, packaging), and a
    stand-in bundled-program package pointing at the stub app-server.
  - The stub replays recorded responses, each carrying an extra unknown field. It sends a known
    and an unknown request, to prove each is declined and nothing runs. It can leave a turn in
    progress for the two-process recovery test, and it echoes the `config` overrides it receives.
  - The smoke test skips when the SDK environment is missing. The coordinator's one real run is
    the required proof.
  - `tests/test_codex_config.py` reads this repository's `forge.toml`.
- **The SDK has its own environment**, installed by `forge doctor --fix`, instead of being a Python
  extra of Forge. With its program, the SDK is about 300 MB, so this keeps Forge's own install
  small.
- **Not in this story:**
  - live steering of a running turn;
  - a shared story conversation forked per task;
  - archiving conversations at merge;
  - the speed benchmark;
  - executor modes.
