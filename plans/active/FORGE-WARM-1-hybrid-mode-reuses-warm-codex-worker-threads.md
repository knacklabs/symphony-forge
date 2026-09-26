# Codex builds your tasks and picks up where it left off

## What changes for you

- Set `workers = "codex"` in `forge.toml` and `forge work` builds each task or fix with Codex
  instead of Claude Code. The worker gets the same brief, works with full access in the task's own
  checkout, and is closed and reviewed exactly as before.
- The Codex model and reasoning effort come from the project's own Codex settings, the same file
  Codex itself reads. A cold read, or any other kind of work, can have its own settings file.
  Forge adds no setting of its own for this.
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
  Codex workers on, it also fails when Codex doesn't trust the project, because Forge's safety hook
  and the project's Codex settings only apply in a trusted one.
- The cold read of a plan or spec can run on Codex too, read-only, the same way.
- The new Forge doesn't use the Claude Codex plugin, and the guide shows how to uninstall it.
- Reviews don't change: Autoreview still reviews every piece of work, on its own terms.

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
   request asks for runs. If Forge can't put its declining handler in place, `forge work` refuses
   before any conversation starts.
3. Model, effort and verbosity come from the checkout's Codex settings. A settings file named after
   the kind of work may change only those three, and any other setting or a broken file makes
   `forge work` refuse and say what to fix. The settings are read again on every call.
4. When a turn starts, the item's turn log on this machine gets a "started" line. When Codex
   reports that the turn ended, the log gets a line with these fields:
   - the turn's id and kind;
   - whether it continued the conversation;
   - its status as Codex reported it;
   - its start and end;
   - its token counts, left blank when Codex doesn't report them.
5. Only one `forge work` runs per task or fix at a time, and a second one refuses and says to wait.
   Forge records its Codex process as soon as the process starts, before any conversation, and the
   conversation right after that starts. A process is known by its id and its start time, so an id
   the system reuses is never mistaken for it.
6. When `forge work` ends, whether normally, on an error or on Ctrl-C, no Codex process of it is
   left. A leftover one from a crash is stopped by the next `forge work` or by `forge doctor`.
7. A fix round, or any later `forge work`, continues the item's conversation. It tells the
   conversation the findings, the failing checks, the new commits, and every change in the
   checkout since its last turn, including new files.
   - Forge starts fresh, and says why, when the conversation isn't recorded here, can't be
     resumed, was started in another checkout, or its history was rewritten underneath it.
8. If the story's approved part changed, `forge work` refuses before it records any status, until
   the change is approved again. The conversation started under the old approval is then not
   continued.
9. A turn still running from an earlier call is interrupted through Codex and awaited before
   anything else.
   - A turn whose end never arrived is logged as interrupted once Codex confirms it isn't running.
   - If Forge can't confirm the turn stopped, `forge work` refuses, so two turns never run for one
     item.
   - Forge never records a finished status that Codex didn't report.
10. With Codex workers chosen, the first cold read of a story or spec runs on a read-only "Grill"
    conversation.
    - Recording the amendment runs no model.
    - A failed or interrupted read leaves both the notes and the story's state unchanged.
    - A file change during the read discards it.
11. With Codex workers chosen, `forge doctor` fails on a missing or wrong Codex SDK and on a
    project Codex doesn't trust, runs its hook health check, and reminds you to approve Forge's
    hooks when Codex asks. `forge doctor --fix` installs the pinned SDK.
12. A smoke test drives the real pinned SDK through six steps: start, naming, resume, a declined
    request, events and shutdown. It runs wherever the SDK is installed, on a developer machine and
    in an optional CI job that installs it.
13. Nothing in the new Forge package, its templates or its docs uses or mentions the Claude Codex
    plugin. The old Forge's mentions go when the old Forge is removed. The guide explains three
    things:
    - Codex workers and where their model settings live;
    - conversation names;
    - how to uninstall the plugin.
14. This repository builds its work with Codex workers. Its old per-role model choices now live in
    its Codex settings, and a test checks both.
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
| BUILD | Codex builds a task or fix | `forge work` with Codex workers runs the brief as one turn on a new, named Build or Lite conversation, with full access and approval policy "never". One handler answers every request Codex sends, known or unknown, with a decline, and it goes in before any conversation starts or the command refuses. It is tested with an unknown method. The model settings come from the checkout, and a per-kind file may override only three keys. The driver reports the Codex process first. Events go to the terminal and the work log, the turn log gets a "started" line and an end line, and the client is closed in a `finally` block. The runner takes the sandbox, the kind and the name, so the reader can reuse it | 1, 2, 3, 4 | `src/forge/worker.py`, `src/forge/codex.py`, `src/forge/codex_turn.py` | `tests/test_codex_worker.py`, `tests/stubs/codex-app-server` | SDK | yes |
| RECORD | One worker per item, nothing left running | Right after the SDK client starts, and before any conversation, the Codex process is recorded by its id and start time. The conversation is added right after it starts, and each write is atomic. The per-item lock holds its owner's id and start time, and a second `forge work` refuses. A stale lock or a leftover Codex process is recognised only when both the id and the start time match, and the next `forge work` or `forge doctor` then clears or stops it | 5, 6 | `src/forge/codex.py`, `src/forge/worker.py`, `src/forge/doctor.py` | `tests/test_codex_record.py` | BUILD | yes |
| RESUME | Fix rounds continue the conversation | A later `forge work` resumes the recorded conversation and renames it "Fix". It sends the fresh brief, the new commits, and the working-tree diff including untracked files. The four drift cases start fresh with a reason. The approval check runs in the worker before its "working" or "fixing" status commit, and a changed approval refuses until it is approved again. A turn still in progress is interrupted through the SDK and awaited, or the command refuses. A turn with no end line is logged as interrupted after checking the conversation. The recovery is tested with two processes against the stub | 7, 8, 9 | `src/forge/worker.py`, `src/forge/codex.py`, `src/forge/codex_turn.py` | `tests/test_codex_resume.py` | RECORD | yes |
| READER | Cold read on Codex | The first `forge read` with Codex workers runs on a "Grill" conversation with the read-only sandbox at start and on each turn, through the same runner. `--amended` opens no client. A failed, interrupted or discarded read leaves both the notes and the story's state unchanged, and `codex exec` goes away | 10 | `src/forge/story.py` | `tests/test_codex_reader.py` | BUILD | yes |
| SMOKE | Real SDK smoke test | A smoke test runs against the real pinned SDK: start, naming, resume, a declined request, events and shutdown. It runs locally whenever the SDK environment exists, and in an optional CI job that installs the SDK and isn't a required check. The required proof is one real run by the coordinator, whose output goes into the plugin-removal pull request | 12 | `.github/workflows/codex-smoke.yml` | `tests/test_codex_smoke.py` | RESUME | no |
| USE-CODEX | This repository builds with Codex | This repository switches to Codex workers. The old per-role model pins move into its Codex settings: the lead's model and effort, the edit subagents' model and effort, and the cold read's own settings file. A test checks that `forge.toml` says `workers = "codex"` and that the committed settings files hold the model keys. It starts only after this repository moves onto the new Forge, which gives it `forge.toml` | 14 | `forge.toml`, `.codex/config.toml`, `.codex/grill.config.toml` | `tests/test_codex_config.py` | RESUME, READER, SMOKE | no |
| UNPLUG | Plugin gone, built end to end by Codex | The guide covers Codex workers and their settings files, the conversation names and the two uninstall commands. A test checks that nothing in the new package, its templates or its docs mentions the plugin. A Codex worker builds this task after `forge doctor` shows the project trusted and the hook health check passing. Its pull request body shows three things: the conversation name, the turn-log lines proving that the first build and a later round shared one conversation, and the coordinator's real smoke-test output. It starts only after this repository moves onto the new Forge | 13, 15 | `docs/guide.md` | `tests/test_no_plugin.py` | USE-CODEX | no |

New moving parts: the pinned Codex SDK in its own Forge-managed environment, about 300 MB once per machine (Done when 1, 11); one small script that the SDK environment's Python runs for each call, which starts Codex and stops it again, so there is no daemon (1, 6); per item, a conversation record, a lock file and a turn log in Forge's local folder inside `.git`, never committed (4, 5); an optional CI job that installs the SDK for the smoke test (12).

## Risks

- **Timing.** The code tasks start now, on the new Forge package that has already merged, and
  ahead of the switch, because Codex workers are wanted early. Only the last two tasks wait for
  this repository to move onto the new Forge, which gives it its `forge.toml`. That step belongs to
  the rebuild story, and Forge can't make a task wait on another story's task. So the coordinator
  starts those two only after the move has merged.
- Full access with no approval prompts means a Codex worker can run any command. The guards are:
  - Forge's deny hook, which blocks destructive commands, skipped git hooks and merges. Codex runs
    it only in a trusted project, so doctor now fails an untrusted one.
  - the review of every diff against its Scope, which is where Scope is enforced;
  - the human merge.

  Nothing is sandboxed.
- Forge can't see whether Codex actually ran its hook. It claims only what it can see: the project
  is trusted and the hook health check passes.
- A process is recognised by its id together with its start time, so a leftover Codex process or a
  stale lock is never confused with an unrelated process that reused the id.
- Codex's server interface is marked experimental. The SDK is pinned to one exact version, and
  moving to a newer one is a deliberate change that reruns the contract and smoke tests.
- The smoke test talks to the real Codex, so it needs a Codex login and costs a little per run. The
  one required run is the coordinator's, and in CI the test stays optional.
- The SDK brings its own Codex program. It can differ from the `codex` that Autoreview uses, but
  both use the same login and the same conversation store.
- The SDK's built-in approval handler accepts everything. Forge replaces it through a private
  attribute, refuses to run if that fails, and a contract test catches a new SDK version that
  moves it.
- Codex's settings format is still changing. This version already rejects the old "profile" line.
  Forge allows only three keys in a per-kind file, so a surprise key fails loudly.
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

  For the plugin, the story's narrower rule is that nothing in the new package, its templates or
  its docs mentions it. The old Forge's mentions go when the old Forge is removed.
- **What the pinned SDK (openai-codex 0.156.1) does**, checked in its source and with live probes:
  - `Codex()` starts `codex app-server --listen stdio://` as a child of the calling process as soon
    as the client is constructed, and stops it on close. There is no shared server, so each
    `forge work` or first `forge read` owns one for its lifetime.
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
    policy "never") on start, on resume and on each turn.
  - The SDK sends every server request, whatever its method, to one handler, and writes the
    handler's return value back as the answer. The default handler accepts command and file-change
    requests.
    - `Codex(config)` takes no handler. Right after `Codex(...)` returns, set
      `codex._client._approval_handler` to a function that logs the method and returns
      `{"decision": "decline"}` for every method, known or unknown.
    - If that attribute is missing, refuse before any thread exists.
    - The stub sends an unknown method and checks the answer is a decline and that nothing ran.
  - `Sandbox.full_access` maps to danger-full-access, both for the thread and for the turn policy.
    For Grill, pass `Sandbox.read_only` on start and on every turn.
  - `Thread.set_name(name)` names a thread, and the name shows in the Codex app and in
    `thread_list`.
  - `TurnHandle.stream()` yields a turn's events, and `TurnHandle.interrupt()` interrupts a turn by
    its id. `Thread.read(include_turns=True)` shows each turn's status. `TurnResult` carries the
    status, the error, the final response and the token usage (`usage.last`).
- **How the SDK picks up the project's Codex settings.** This was checked with a throwaway Codex
  home, reading the model and effort that `thread/start` reports:
  - The thread's own folder (`cwd` on `thread_start`) decides which project `.codex/config.toml`
    applies, not the folder the app-server process started in.
  - The project layer applies when the user's Codex config trusts the project. A task worktree
    beside the main checkout gets its main repo's trust, because Codex resolves a worktree through
    its main repo. It reads the worktree's own committed copy of `.codex/config.toml`.
  - A project marked untrusted gets the user's defaults, and so does a plain folder with no trust
    entry. Unexpectedly, an unlisted git repo still got its project settings.
  - Profiles can't be switched through the app-server:
    - `codex --profile x app-server` is refused;
    - a `profile = "x"` line inside the config is rejected as legacy.
  - What works is passing the per-kind file's keys as the thread's `config` overrides, which was
    verified in a worktree. Pass them on `thread_start` and on `thread_resume`.
- **The model routing that moves out of `harness.yaml`** into this repo's Codex settings:
  - the worker lead is `gpt-6-sol` at medium: top-level `model` and `model_reasoning_effort` in
    `.codex/config.toml`;
  - the edit subagents are `gpt-6-luna` at max: `default_subagent_model` and
    `default_subagent_reasoning_effort` under `[agents]`, which are already there;
  - the cold read is `gpt-6-sol` at high: `.codex/grill.config.toml`.

  `forge sync` keeps `.codex/config.toml` and merges only Forge's hooks key into it, and it never
  touches the per-kind files.
- **Harvest** from the earlier setup work (`factory/scripts/forge_cli/codex_sdk.py` on the setup
  branch):
  - keep the pin, the environment folder, the ready marker, the import probe and the uv install
    steps;
  - drop the minimum-binary check and the npm install of `codex`;
  - make the pin one constant in `src/forge/codex.py`, like the Autoreview pin in `review.py`.
- **Two files:**
  - `src/forge/codex.py` is the Forge side and never imports the SDK. It holds the pin, the
    environment, the doctor checks, the install, the per-kind settings check, the record, the lock,
    the turn log, and `run(checkout, kind, name, prompt, sandbox, thread=None)`.
  - `src/forge/codex_turn.py` is the script the SDK environment's Python runs. It reads one JSON
    request on stdin and constructs the client. It prints the app-server's process id at once,
    before installing the handler or starting a thread. It then starts or resumes the thread, prints
    its id, names it and runs the turn. It prints one JSON line per event, then a result line with
    the usage.
- **Process identity:** a process is its id plus its start time. On POSIX the start time comes
  from `ps -o lstart= -p <pid>`, and on Windows from PowerShell
  `(Get-Process -Id <pid>).StartTime`. The record and the lock both store the pair. A stale lock or
  a leftover child is acted on only when both match.
- **The record, the lock and the logs:**
  - `.git/forge/threads/<item>.json` holds the app-server's id and start time (written first), the
    thread id, the checkout folder, the approval and HEAD at the end of each turn. Every write goes
    through a temporary file and a rename.
  - `.git/forge/threads/<item>.lock` is created exclusively and holds its owner's id and start
    time.
  - `.git/forge/threads/<item>.log` gets a "started" line per turn and an end line with the status
    Codex reported. When no end line exists, the next `forge work` reads the thread. It interrupts
    and awaits the turn if it is still in progress, or adds an "interrupted" line if it isn't. It
    never writes "completed" on its own.
  - The event stream still goes to `.git/forge/work-<item>.log`.
  - All of it is machine-local and never committed.
- **Order in `worker.work`:**
  1. the approval-change refusal;
  2. the lock;
  3. the leftover-process cleanup;
  4. the "working" or "fixing" status commit;
  5. the run.

  A refused call therefore changes no committed state.
- **The resumed turn's text:** today's fix-round brief, then `git log --oneline <recorded>..HEAD`,
  then the diff from the recorded HEAD to the working tree, with untracked files included through a
  temporary index.
- **Conversation names:** Forge produces only Build, Lite, Fix and Grill. Review, Explore and Debug
  are named in the guide as advice for threads opened by hand.
- **Worker refusal:** the refusal "Codex workers come with the warm-threads story" goes, and the
  v1 worker test stops expecting it.
- **Tests:**
  - Each test file declares `STORY = "<this story's key>"`, and its `test_<n>_` names cite this
    story's Done-when items.
  - Stub-based tests run the pinned SDK without its bundled program: install it with `--no-deps`,
    plus its two libraries. They talk to the stub app-server through `CODEX_BIN`.
  - The stub replays recorded responses, each carrying an extra unknown field. It sends a known
    and an unknown request, to prove each is declined and nothing runs. It can leave a turn in
    progress for the two-process recovery test, and it echoes the `config` overrides it receives.
  - The smoke test skips when the SDK environment is missing. The coordinator's one real run is
    the required proof.
  - `tests/test_codex_config.py` reads this repository's `forge.toml`, `.codex/config.toml` and
    `.codex/grill.config.toml`.
- **The SDK has its own environment**, installed by `forge doctor --fix`, instead of being a Python
  extra of Forge. With its program, the SDK is about 300 MB, so this keeps Forge's own install
  small.
- **Autoreview** keeps its own Codex use, unchanged.
- **Not in this story:**
  - live steering of a running turn;
  - a shared story conversation forked per task;
  - archiving conversations at merge;
  - the speed benchmark;
  - executor modes.
