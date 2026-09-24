---
slug: warm-codex-threads
title: Hybrid mode reuses warm Codex worker threads
status: confirmed
saved: 2026-09-24T01:10:38+00:00
---

# Hybrid mode reuses warm Codex worker threads

## Why

In hybrid mode Claude coordinates and Codex executes. Every Codex delegation today starts a new
conversation through the plugin companion, so each worker re-reads the repository before it can act,
and every review-fix round starts cold again. Codex's app-server keeps conversations ("threads") that
can be resumed, steered and watched live, and the official `openai-codex` Python SDK exposes them.
Resuming a task's own worker for its fix rounds removes most of that repeated context gathering.

Decision 0085 (executor modes) is accepted but not yet implemented; this story implements it, because
"hybrid" is the mode this story speeds up.

Out of scope here (a follow-up story): a warm story-level thread forked per task, and approving task
plans from the primary checkout. Worker approvals are not routed to Claude: Forge-managed Codex chats
keep full access with `approval_policy="never"` (decision 0081); scope stays enforced by the hooks and
the measured diff, as today.

## Behaviour

### Executor modes (decision 0085)
- `FORGE_EXECUTOR` (in `.envrc`) selects `hybrid` (default: Claude coordinates, Codex executes),
  `codex` (only Codex writes) or `claude` (Claude only; no Codex needed). It is independent of the
  existing `FORGE_COORDINATOR` (`claude`|`codex`), which keeps choosing the coordinating runtime.
- `claude` mode admits the Claude session and its subagents as writers under the same task, scope,
  proof and review gates; its cold grill uses a fresh Claude reader and Autoreview's claude engine.

### The SDK route (hybrid mode, Claude coordinating)
- A new decision (0086) makes the Forge-owned SDK route the primary Claude→Codex delegation route in
  hybrid mode and amends the delegation-boundary spec, the dual-coordinator parity architecture and the
  product brief accordingly; the codex-plugin-cc companion becomes the fallback. Native Codex
  coordination (host subagents) is unchanged.
- Route selection happens once, before dispatch, in `forge delegate`: the SDK route is used when
  `forge doctor`'s SDK check passes; otherwise the plugin route is used and the reason is printed.
  Once a thread or turn has started, there is no fallback: a failure is reported and the delegation
  is recorded as failed, never retried on another route.
- The SDK is pinned: `openai-codex` at an exact version recorded in the harness, driving the
  installed `codex` binary through `CodexConfig.codex_bin` (never the SDK's bundled binary). `forge
  doctor` checks the SDK version, the binary version against the SDK's minimum, and the path; a
  mismatch selects the plugin route pre-dispatch and names both versions.
- Admission and close proof are per turn: every delegated turn is admitted by a ledger row binding
  thread id, turn id, story, task, stage incarnation, delegation id, task worktree (and its Git common
  directory), approved contract digest and base commit. The existing worker-admission and
  stage-close checks accept an SDK row as equivalent to a companion launch row; a stage closes only
  when its last turn reached a terminal `turn/completed` state and no turn of that task is loaded.
- The SDK's approval handler is overridden on every path with an explicit handler that declines;
  with `approval_policy="never"` no approval request is expected, and any request is declined and
  logged.

### Resuming the worker for fix rounds
- Each task records its worker thread. A review-fix round runs `forge delegate` exactly as today
  (current task, stage, brief, effective scope, triage checks) and then resumes the recorded thread
  with a turn that carries: the fresh brief, the current HEAD, the committed diff from the stage base
  to HEAD plus the worktree's uncommitted changes, and the triaged findings.
- If any binding changed (task, stage incarnation, worktree, contract digest), or the thread is
  missing, archived or compacted past its base, Forge starts a new thread instead and says why.
- The delegated thread keeps its Sol/medium lead; edits go to Luna/max subagents (decision 0084).

### Live events and steering
- Forge consumes the event stream of every delegated turn (items, diff updates, token usage, turn
  completion) and writes progress to the delegation log it already watches. If the supervising
  process loses the stream, it reattaches and reconciles with `thread/read`; duplicate events are
  idempotent; a turn whose state cannot be established blocks close as "unknown", never as done.
- A worker signal pauses the worker as today; Forge maps the recorded resolution to `turn/steer` on
  the exact active turn (by turn id), or `turn/interrupt` plus a resumed turn when steering is not
  possible. A signal that arrives after the turn completed is delivered in the next resumed turn.

### One app-server, one owner
- One Forge-owned app-server per repository (keyed by the Git common directory) holds all Forge
  threads. Ownership is a lease file in the Git common directory with pid, process start time and a
  fencing counter; a stale lease (dead process) is detected and cleared; a live foreign holder is
  reported, never raced.

### Upgrade and cleanup
- `forge upgrade` of an existing client: adds the pinned SDK requirement and the doctor check, keeps
  the plugin route working, sets no `FORGE_EXECUTOR` (default `hybrid`), and changes nothing about
  in-flight tasks: a task started on the plugin route finishes on it. Re-running the upgrade is a
  no-op. The Lean client-upgrade hold must be lifted before this ships to clients.
- Cleanup: a task's worker thread is archived when its PR merges (task marker on trunk); remaining
  Forge threads are archived when the story's outcome is recorded; archival is idempotent and retried
  by `forge doctor`. The app-server lease is released on shutdown. `forge doctor --prune-threads`
  removes archived rollouts of Forge-owned threads only (by the ledger's thread ids), never the
  user's own Codex threads.

## Acceptance criteria

1. `FORGE_EXECUTOR` selects hybrid, codex or claude as decision 0085 describes; claude mode passes
   task close with Claude writers under the same gates; hybrid is the default.
2. In hybrid mode with a passing doctor check, `forge delegate` runs the task on the SDK route; with a
   failing check it runs on the plugin route pre-dispatch and prints why; after dispatch there is no
   route fallback.
3. The SDK and binary versions are pinned and checked; a mismatch names both versions.
4. Every SDK turn is admitted by a ledger row with the bindings above, recorded through a
   schema-validated recorder; stage close requires a terminal turn and no loaded turn for the task.
5. A review-fix round resumes the task's recorded thread with the fresh brief, HEAD, stage-base diff
   plus uncommitted changes and the findings; a changed binding starts a new thread with the reason.
6. Benchmark: for three recorded fix rounds, replaying the same findings on a cold delegation and on
   a resumed thread (same model, effort and brief, three runs each, median), the resumed round uses
   fewer uncached input tokens and less wall time; the numbers are recorded as story evidence.
7. Forge follows each turn through the event stream, reattaches after a lost stream, and blocks
   close on an unknown turn state.
8. A worker signal resolution reaches the exact active turn by steer or interrupt-and-resume, never
   by cancel-and-relaunch.
9. Only the lease holder resumes Forge threads; a stale lease is cleared; a live foreign holder is
   reported.
10. `forge upgrade` on an existing client installs the pinned SDK requirement and doctor check,
    keeps plugin-route tasks working, and is idempotent.
11. Worker threads are archived at task merge and story outcome; pruning touches Forge-owned threads
    only.
12. The dual-runtime parity matrix covers claude, codex and hybrid (SDK and plugin routes) across
    setup, init/adopt/upgrade, scoped writes, hook delivery and task close on macOS, Linux and
    Windows, per docs/specs/dual-coordinator-parity.md.
