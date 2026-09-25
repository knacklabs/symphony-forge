---
slug: warm-codex-threads
title: Codex workers keep a warm conversation per task
status: draft
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
- `workers = "codex"` in `forge.toml` sends `forge work` and `forge read` to Codex. Nothing else
  selects Codex, and there is no fallback route. A failure is reported with its next step, never
  retried another way.
- Each `forge work` or `forge read` call opens one SDK client. That client starts Codex's
  app-server as a child process, runs one turn and closes, and the app-server exits with it. No
  daemon, lease or shared server exists between calls.
- The SDK is `openai-codex` at one exact version pinned in Forge, installed in its own
  Forge-managed environment. It uses the Codex program bundled with that exact SDK version.
  `forge doctor` reports a missing or wrong SDK, and `forge doctor --fix` installs the pinned one.

### Full access, approvals declined
- Worker threads run with full access (danger-full-access) and approval policy "never", set on
  every thread start, resume and turn. The SDK's default handler accepts approval requests. Forge
  replaces it with one that declines every request and logs it, before any thread starts.
- Scope stays enforced by Forge's deny hook, the review of the diff against the task's Scope, and
  the human merge. Codex runs the deny hook only in a trusted project, so with Codex workers on,
  `forge doctor` reports an untrusted project as a problem.

### Model settings live in the project's Codex settings
- Codex workers and readers take their model and reasoning effort from the project's own
  `.codex/config.toml` and the user's Codex config, exactly as Codex does. Forge adds no setting
  for them.
- A settings file named after a kind of work (`.codex/<kind>.config.toml`, for example
  `grill.config.toml` for the cold read) overrides them for that kind. The thread's folder is the
  item's checkout, so the settings that apply are the ones Codex applies to that checkout. For a
  task worktree, those are its main repository's settings, and only when the project is trusted.

### Named threads
- Every thread Forge starts is named `<Kind> · <STORY>/<TASK or fix> · <title>`, so people can
  find it in the Codex app.
- The kinds are Build, Fix, Lite, Grill, Review, Explore and Debug. Forge itself uses four:
  - Build, for a task's first turn;
  - Lite, for a fix's first turn;
  - Fix, for any later round;
  - Grill, for a cold read.
- Review belongs to Autoreview. Explore and Debug are for threads people open by hand.

### Resume and drift
- Each task or fix records its thread on the machine that made it; the record is never committed.
- A fix round, or any later `forge work` on the same item, resumes that thread, renames it for the
  round, and sends one turn with three things:
  - the fresh brief, with the open findings and the failing checks;
  - the commits made since the thread's last turn;
  - the checkout's uncommitted changes.
- Forge starts a new thread instead, and prints why, when any of these holds:
  - there is no record on this machine;
  - the recorded thread can't be resumed;
  - the thread was started in another checkout;
  - the story's approved part changed since the thread started.

### Progress
- Each turn's events (messages, commands run, files changed) are printed to the terminal and to
  the item's log in `.git/forge/`, never committed. The turn's status and token usage go there
  too.
- A turn that fails or is interrupted stops `forge work` with the reason and the log's path. The
  thread stays resumable.

### The cold reader on Codex
- With Codex workers, `forge read` runs the one cold read on a read-only thread named Grill,
  through the same client. The rule that discards a read when any file changed stays.

### The plugin is removed
- Nothing in Forge uses or mentions the Claude Codex plugin (codex-plugin-cc and its companion)
  any more, outside history. The guide shows how to uninstall it.
- Autoreview stays an external black box with its own Codex use.

## Acceptance criteria

1. With `workers = "codex"`, `forge work` runs the brief as one turn on a new, named Codex thread
   with full access and approval policy "never". Every approval request is declined and logged.
   Events go to the terminal and the log, and no Codex process remains after the command ends.
2. Codex workers and readers use the model and effort from the checkout's Codex settings, and
   `.codex/<kind>.config.toml`, when present, overrides them for that kind.
3. A fix round resumes the item's recorded thread with the fresh brief, the new commits and the
   uncommitted changes. Each drift case starts a fresh thread and prints its reason.
4. With `workers = "codex"`, `forge read` runs read-only on a Grill thread, and a read during which
   a file changed is discarded.
5. `forge doctor` reports a missing or wrong SDK and an untrusted project when Codex workers are
   chosen, and `forge doctor --fix` installs the pinned SDK.
6. The SDK boundary has a contract test: a stub app-server replays recorded responses that each
   carry an extra unknown field, and a changed approval-handler hook in a new SDK fails that test.
7. Outside history, nothing in Forge references codex-plugin-cc or its companion, and the guide
   documents uninstalling the plugin.
8. One real task in Forge's own repository is built on a Codex thread from first build to merge,
   and a second `forge work` on it continues the same thread.

## Success measure

- Metric: two numbers from the worker logs:
  - the share of Codex fix rounds that continue their task's thread instead of starting fresh;
  - the median share of a fix round's input tokens read from cache.
- Baseline:
  - continued rounds: 0%, because every Codex round starts a new conversation today;
  - cache share: not measured on real fix rounds, though a two-turn probe read 99% from cache.
- Target: at least 90% of Codex fix rounds continue their thread, and the median cache share is at
  least 80%.
- Check date: 2026-12-15

## Out of scope

- Any fallback route to Codex, including the plugin.
- A per-turn ledger, a lease or supervisor process, and a shared app-server.
- Live steering or interrupting a running turn, and signals bound to turns.
- Executor modes: `workers` in `forge.toml` replaces them.
- A shared story thread forked per task.
- Archiving or pruning threads at merge.
- A client-upgrade path.
- The before-and-after benchmark.
- The cross-platform parity matrix beyond the v1 suite's own runners.

## Roadmap

- FORGE-WARM-1: Codex builds your tasks and picks up where it left off
