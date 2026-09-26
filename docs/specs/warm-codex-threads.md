---
slug: warm-codex-threads
title: Codex workers keep a warm conversation per task
status: confirmed
saved: 2026-09-25T17:42:37+00:00
---

# Codex workers keep a warm conversation per task

## Why

Forge can run its workers on Claude Code or on Codex. The old Forge reached Codex through a Claude
plugin, and every hand-off started a brand-new conversation. Each worker re-read the repository
before it could act, and every review-fix round started cold again. The new Forge dropped that
plugin, and it refuses Codex workers until this lands.

Codex's official Python SDK drives Codex's own app-server. With it, a program can start a named
conversation ("thread"), stop, and later resume the same thread in a new process with its memory
intact. A probe on the pinned SDK showed exactly that, with 99% of the resumed turn's input read
from cache. Forge can therefore give each task one warm Codex thread, continue it for every fix
round, and run nothing in the background.

## Behaviour

### One route to Codex: Forge's own SDK client
- `workers = "codex"` in `forge.toml` sends two things to Codex: `forge work`, and the first cold
  read of a story or spec. `forge read --amended` runs no model turn, because it only records the
  amendment. Nothing else selects Codex, and there is no fallback route. A failure is reported
  with its next step, never retried another way.
- Each `forge work` call, and each first cold read, opens one SDK client. That client starts
  Codex's app-server as a child process, runs one turn and closes. No daemon, lease or shared
  server exists between calls.
- The client is closed in a `finally` block, so it closes on a normal exit, on an error and on
  Ctrl-C.
- `forge work` records the app-server child's process id in the item's thread record. If the
  recorded process is still running, the next `forge work` on that item, or `forge doctor`,
  terminates it first. Before terminating, it checks that the process is still a Codex app-server.

### The pinned SDK
- The SDK is `openai-codex` 0.156.1, harvested from the earlier setup work. It is installed in a
  Forge-managed environment at `~/.local/share/forge/codex-sdk/openai-codex-0.156.1` and is not a
  dependency of the Forge package.
- `forge doctor --fix` creates that environment, including on an existing Forge installation.
- Workers use the Codex program bundled with that SDK version. With `workers = "codex"`, doctor
  checks the environment and its bundled Codex program, not a standalone `codex` executable.

### Full access, approvals declined, failing closed
- Worker threads run with full access (danger-full-access) and approval policy "never", set on
  every thread start, resume and turn.
- Forge installs an approval handler that declines every approval request, known or unknown, and
  logs it. The handler goes in before any thread exists. If it can't be installed, for example
  because a new SDK moved the hook, `forge work` refuses before any thread exists.
- A declined request does not execute.
- There is no sandbox. The guards are these:
  - Forge's deny hook, which blocks destructive commands, skipped git hooks and merges. It does
    not enforce Scope.
  - Scope, which is enforced by the review of each diff against its task's Scope.
  - The human merge.
- Codex runs project hooks only in a trusted project. So with `workers = "codex"`:
  - an untrusted project is a failing `forge doctor` row;
  - doctor still runs its hook health check;
  - Codex asks separately to approve each hook, and an outside program can't see that approval,
    so doctor prints a note to approve Forge's hooks when Codex asks.

### Model settings live in the project's Codex settings
- Codex workers and readers take their model settings from Codex's own settings stack: the
  project's `.codex/config.toml` and the user's Codex config. Forge adds no setting for them.
- `.codex/config.toml` is committed, so every task worktree has its own copy. Codex reads the
  project settings from the thread's folder, which is the item's checkout. `forge sync` writes
  that file in the checkout it runs in, and merges only Forge's hooks key into it.
- A settings file named after a kind of work, `.codex/<kind>.config.toml` (for example
  `grill.config.toml`), overrides the settings for that kind. It may set only `model`,
  `model_reasoning_effort` and `model_verbosity`.
  - Any other key, sandbox and approval keys included, makes `forge work` refuse with a `Next:`
    line.
  - A file that isn't valid TOML also makes `forge work` refuse.
- Settings are read on every `forge work` call, resumes included.
- **Note:** the owner decisions of 2026-09-26 in the FORGE-WARM-1 story doc govern here: each
  kind's models live in `forge.toml`'s `[models]` table, not in `.codex/<kind>.config.toml`.

### Named threads
- Forge names every thread it starts:
  - a task's thread is `<Kind> · <STORY>/<TASK> · <task name>`;
  - a fix's thread is `<Kind> · <fix name> · <why>`, for example `Fix · <fix name> · <why>`;
  - a cold read's thread is `Grill · <STORY or spec slug> · <title>`.
- Forge produces four kinds:
  - Build, for a task's first turn;
  - Lite, for a fix's first turn;
  - Fix, for any later round, renamed when that round starts;
  - Grill, for a cold read.
- Review, Explore and Debug are naming guidance for threads a person opens by hand. They are
  documented, but Forge never produces or tests them.

### Thread record and one worker per item
- Each task or fix has a thread record on the machine that made it, at
  `.git/forge/threads/<item>.json`, which is never committed. It holds:
  - the thread id;
  - the checkout folder;
  - the approval the thread started under;
  - the app-server's process id;
  - HEAD at the end of the last turn.
- The record is written atomically right after the thread starts, before its first turn.
- Only one `forge work` runs per item at a time. It holds an exclusive lock file under
  `.git/forge/threads/`, and a second caller refuses with a `Next:` line. A lock left by a process
  that is no longer running is cleared.

### Resume and drift
- A fix round, or any later `forge work` on the same item, resumes the recorded thread. It renames
  the thread for the round and sends one turn with three things:
  - the fresh brief, with the open findings and the failing checks;
  - the commits since the recorded HEAD;
  - the diff from that commit to the working tree, untracked files included.
- Forge starts a new thread instead, and prints why, when any of these holds:
  - there is no record on this machine;
  - the recorded thread can't be resumed;
  - the thread was started in another checkout;
  - the recorded HEAD is no longer an ancestor of HEAD, after a rebase or an amended commit.
- If the story's approved part changed, `forge work` refuses until the change is approved again.
  It never runs on unapproved text. Once the change is approved, the thread started under the old
  approval is not continued, and a fresh one starts.
- A turn may still be in progress from an earlier call, for example after a lost connection or a
  killed `forge work`. Forge then interrupts it through the SDK and waits for its terminal state.
  If that state can't be confirmed, `forge work` refuses with `Next: forge work <item>`. Two turns
  never run for one item.
- **Note:** the owner decisions of 2026-09-26 in the FORGE-WARM-1 story doc govern here: after a
  crash, Forge stops the leftover Codex process first, then reads the conversation back, instead
  of interrupting a running turn.

### Progress and the turn log
- Each turn's events are printed to the terminal and to the item's work log in `.git/forge/`:
  messages, commands run and files changed.
- Each turn also adds one line to the item's turn log, `.git/forge/threads/<item>.log`, which is
  kept on this machine and never committed. The line holds:
  - the turn id and kind;
  - whether the turn continued the thread, or why it started fresh;
  - the status;
  - the start and end times;
  - the input, cached and output tokens, each null when the SDK omits it.
- Duplicate events are ignored by turn id. The final status comes only from the SDK's
  turn-completed event.
- A turn that fails or is interrupted stops `forge work` with the reason and the log's path. The
  thread stays resumable.
- **Note:** the owner decisions of 2026-09-26 in the FORGE-WARM-1 story doc govern here: a turn
  writes a "started" line when it starts and an end line when Codex reports its end, not one line.

### The cold reader on Codex
- With Codex workers, the first `forge read` of a story or spec runs on a thread named Grill. The
  thread starts, and runs each turn, with the read-only sandbox.
- A failed or interrupted read writes no notes and records no read.
- The existing discard rule stays. A read is discarded when any tracked file, or any untracked file
  that git doesn't ignore, changes during the read.

### The plugin is removed
- Outside history, nothing in Forge uses or mentions the Claude Codex plugin (codex-plugin-cc and
  its companion) any more. The guide shows how to uninstall it.
- Autoreview stays an external black box with its own Codex use.

## Acceptance criteria

1. **Route and cleanup.** With `workers = "codex"`, `forge work` runs the brief as one turn on a
   new thread with full access and approval policy "never".
   - After `forge work` exits, normally, on an error or on Ctrl-C, no app-server child of it
     remains.
   - A recorded child that is still running is terminated by the next `forge work` or by
     `forge doctor`, and only after the check that it is a Codex app-server.
2. **Approvals.** Every approval request, known or unknown, is declined and logged. A contract test
   shows that a declined request does not execute. When the declining handler can't be installed,
   `forge work` refuses before any thread exists.
3. **Settings.** Workers and readers use the checkout's Codex settings.
   - `.codex/<kind>.config.toml` can change only `model`, `model_reasoning_effort` and
     `model_verbosity`.
   - Any other key, or a file that isn't valid TOML, makes `forge work` refuse with `Next:`.
   - Settings are read again on every call, resumes included.
4. **Titles.** Task, fix and cold-read threads carry the titles above. Forge produces the kinds
   Build, Lite, Fix and Grill, and no other kind.
5. **Record and lock.**
   - The thread record is written before the first turn.
   - A second `forge work` on an item while one is running refuses with `Next:`.
   - A stale lock is cleared.
6. **Resume and drift.**
   - A fix round resumes the recorded thread with the fresh brief, the commits since the recorded
     HEAD, and the working-tree diff including untracked files.
   - Each of the four fresh-start cases starts a fresh thread and prints its reason.
   - A changed approved part refuses until it is approved again.
7. **Unknown turn.** A turn left in progress is interrupted and awaited before a new turn starts.
   When its end can't be confirmed, `forge work` refuses, and two turns never run for one item.
8. **Turn log.**
   - Each turn writes one line with the fields above, and tokens are null when the SDK omits them.
   - Duplicate events don't add lines.
   - The status comes only from the turn-completed event.
9. **Cold reader.**
   - With `workers = "codex"`, the first read of a story or spec runs on a Grill thread with the
     read-only sandbox, both at start and on each turn.
   - `forge read --amended` opens no client.
   - A failed or interrupted read writes no notes and records no read.
   - A change to any tracked or unignored untracked file discards the read.
10. **Doctor.** With `workers = "codex"`, `forge doctor` fails on two things:
    - a missing or wrong SDK environment or bundled Codex program;
    - an untrusted project.

    It still runs the hook health check, and it prints the note about approving Forge's hooks.
    `forge doctor --fix` creates the pinned SDK environment.
11. **Contract and smoke test.**
    - A stub app-server replays recorded responses, each carrying an extra unknown field.
    - A real smoke test against the pinned SDK exercises start, naming, resume, a declined
      request, events and shutdown. It runs whenever the SDK environment exists, on a developer
      machine and in an optional CI job that installs it.
12. **Plugin removed.** Outside history, nothing in Forge references codex-plugin-cc or its
    companion, and the guide documents how to uninstall the plugin.
13. **A real task.** A Codex worker builds the task that removes the plugin.
    - Its pull request body shows the thread name and the turn-log lines proving that the first
      build and a later round used one thread id.
    - It then passes review and its checks, and a human merges it.

## Success measure

- Metric: two numbers from the turn logs:
  - the share of Codex fix rounds that continue their task's thread;
  - the median share of a fix round's input tokens read from cache.
- Window: every Codex fix round from the merge of the change that switches Forge's own repository
  to Codex workers, until the check date.
  - A fresh start because of drift or a lost thread counts as not continued.
  - Failed rounds are left out.
  - Rounds with missing token usage are left out of the cache median.
- Baseline:
  - continued rounds: 0%, because every Codex round starts a new conversation today;
  - cache share: not measured on real fix rounds, though a two-turn probe read 99% from cache.
- Target: at least 90% of Codex fix rounds continue their thread, and the median cache share is at
  least 80%.
- Check date: 2026-12-15

## Out of scope

- Any fallback route to Codex, including the plugin.
- A per-turn ledger, a lease or supervisor process, and a shared app-server.
- Live steering of a running turn, and signals bound to turns.
- Executor modes: `workers` in `forge.toml` replaces them.
- A shared story thread forked per task.
- Archiving or pruning threads at merge.
- A client-upgrade path.
- The before-and-after benchmark.
- The cross-platform parity matrix beyond the v1 suite's own runners.

## Roadmap

- FORGE-WARM-1: Codex builds your tasks and picks up where it left off
