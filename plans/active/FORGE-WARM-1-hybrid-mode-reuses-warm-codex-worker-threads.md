# Hybrid mode reuses warm Codex worker threads

## What and why

When Claude hands work to Codex, every job starts a brand-new Codex conversation. The worker spends its
first minutes re-reading the repository, and every round of fixes after a review starts cold again,
even though the same worker read the same code minutes earlier. That repeated reading is most of the
waiting. Codex can keep a conversation alive and continue it; Forge just never asks it to.

## What changes for you

- Fix rounds after a review continue with the worker that already knows the task, told only what
  changed, so they come back faster.
- You can see what a Codex worker is doing while it works, and Forge can redirect or pause it instead
  of killing and restarting it.
- One setting in `.envrc` picks who does the work: Claude and Codex together (the default), Codex
  only, or Claude only.
- Existing client repos get this through `forge upgrade`; work already in progress finishes the old
  way, and Forge cleans up its own Codex conversations when tasks and stories finish.

Not in this story: one shared story conversation every task branches from, approving task plans from
the main checkout, and letting Claude write a single task while in hybrid mode — all come later. Workers on the new Codex route run with full access and never ask, as
native Codex chats do; the plugin fallback keeps its current settings. Forge's checks review every
worker's changes against the task but do not sandbox them.

## Done when

- The `.envrc` setting picks hybrid, Codex-only or Claude-only, and each passes the same task checks.
- In hybrid mode Forge talks to Codex through its own long-running Codex server when the setup check
  passes, and through today's plugin otherwise — decided before a job starts, never midway.
- Every job on the new route is recorded as strictly as today's, and a task can't close
  while its worker is still running or in an unknown state.
- A fix round continues the task's own worker with the latest code and the review findings; if the
  task changed underneath it, Forge starts a fresh worker and says why.
- A recorded before-and-after measurement shows fix rounds taking less time and less re-reading.
- Forge watches workers live, recovers if it loses the connection, and answers a worker's question by
  redirecting or pausing the running job.
- Only one Forge Codex server owns a repository's conversations at a time.
- `forge upgrade` brings existing clients on safely and can be re-run; Forge archives and prunes only
  its own Codex conversations.
- All three modes pass the same checks on macOS, Linux and Windows.

## Risks

- Codex's server interface is still marked experimental; Forge pins the exact version, and on a
  mismatch that job simply runs on the plugin instead, decided before it starts.
- Client rollout waits until the Lean fixes lift today's client-upgrade hold.
- A continued worker doesn't know about commits made since it last ran; every continuation is told
  the current code and what changed.
- Long-lived conversations keep whatever they read; Forge archives them when the work ends.

## What I need from you

Nothing beyond approving this plan.

---

## Technical approach

- One `FORGE_EXECUTOR` resolver (hybrid default, codex, claude) for Claude-coordinated sessions,
  read by delegate, doctor, grill, review and close. Under full access (decision 0087) it decides whom
  `forge delegate` hands work to; it admits or refuses no writes. Claude mode hands tasks to a Claude
  subagent writer, grills with a fresh Claude subagent reader and reviews with Autoreview's claude
  engine. Codex-coordinated sessions keep native Codex execution (any other setting there is refused
  with a message). Hybrid Claude writes for a single task are deferred (D-0044), and
  Codex-coordinated sessions support only Codex execution in this story (D-0045). EXEC-MODES is
  replanned on top of FORGE-ACCESS-1's CODE task and starts after it merges.
- SDK route: `openai-codex` pinned exactly in `factory/requirements-sdk.txt`; the installed `codex`
  binary must be at least the SDK's minimum; `forge doctor --fix` installs the pinned SDK into a
  Forge-managed uv environment used by doctor and delegate and, when needed, the minimum `codex`; every turn sets `danger-full-access` and
  `approval_policy="never"` explicitly (decision 0081), keeps Codex hooks on, runs the Sol/medium
  lead with Luna/max subagents (decision 0084); the approval handler declines on every path.
- Supervisor: one detached supervisor per Git common directory owns the lease (pid, start time,
  fencing counter) and the app-server; delegate attaches over an owner-only socket with a private token
  (Windows: the existing private-file DACL helper);
  every request names a worktree of that common directory; takeover only of a provably dead holder
  (uncertain liveness is refused; an orphaned app-server is terminated first); stale counters refused.
- Routes are sticky per task in both directions (a task with any existing companion launch is a
  plugin task). A version mismatch or unhealthy supervisor selects the plugin only for a task's FIRST
  delegation; a task already on the SDK route refuses with the fix or an explicit, recorded
  `--fresh-route` restart.
- Turn records: the supervisor holds the task lock per turn, binds the brief digest and scope, and
  records a terminal turn entry (under full access nothing is admitted or revoked, and close needs no
  launch record); per-turn ledger rows (thread, turn, story, task,
  stage incarnation, delegation, worktree, common dir, contract digest, base commit) go through a
  schema-validated recorder; close requires `turn/completed` and no loaded turn. Native close rules
  are unchanged.
- Resume: fix rounds run `forge delegate` as today, snapshot HEAD, the stage base, a tree built from a
  temporary index (tracked and untracked in-scope files; ignored and out-of-scope excluded) and the
  findings digest, re-verify it before `thread_resume`, and send the brief, HEAD, the diff and the
  findings; binding drift or a missing, archived or over-compacted thread starts fresh with the reason.
- Events: per-turn state machine (started, running, completed, failed, interrupted, unknown);
  duplicates ignored by item id; a lost stream reattaches and `thread/read` settles the state; unknown
  blocks close. Signals record task, thread and turn; resolutions go by `turn/steer`, else interrupt
  plus resume; a resolution is delivered once the turn carrying it has started, which is recorded; an
  undelivered resolution blocks close; older signals without turn ids keep today's meaning. If the
  app-server dies and a turn can never be read, a recorded `forge delegate --abandon-turn` marks it
  failed and the task continues on a fresh thread.
- Upgrade and cleanup: `forge upgrade` adds the requirement and doctor check idempotently and leaves
  `.envrc` alone; plugin-started tasks stay on the plugin; client upgrades wait for FORGE-UPG-2 to lift the client-upgrade hold.
  Threads archive at task merge and story outcome (retried by doctor); pruning touches only ledger
  threads.
- Docs: README.md, docs/getting-started.md, `.claude/CLAUDE.md`, AGENTS.md, the
  Forge skill, the delegation-boundary and dual-coordinator parity specs, the parity
  architecture, the product brief, WORKFLOW.md and docs/FACTORY.md wherever they name the plugin as the
  only Claude route or deny Claude writers.
- Task-level mechanics (per-turn supervisor binding, ledger location, abandon-turn cleanup, signal
  delivery proof, benchmark artifacts, platform evidence) are specified in each task's own plan and
  cold read, planned just in time.
- Activation: the new route stays off until SDK-ADMISSION ships (SDK-SETUP and SDK-SUPERVISOR install
  and check only); SDK-ADMISSION includes terminal-turn proof via `thread/read`; until LIVE-EVENTS
  ships, worker signals work as today (pause, resolve, resume) and LIVE-EVENTS then adds streaming,
  reattach and steering.

## Task decomposition

SDK-SETUP starts now; SDK-SUPERVISOR follows it. EXEC-MODES starts once FORGE-ACCESS-1's CODE task has
merged; SDK-ADMISSION needs both EXEC-MODES and SDK-SUPERVISOR. Each task ships its own pull request.

| Label / exact task ID | What it delivers | Depends on | user_facing |
|---|---|---|---|
| Modes / EXEC-MODES | `FORGE_EXECUTOR` hybrid/codex/claude deciding whom `forge delegate` hands work to, with the same close checks for every writer | none | false |
| Setup / SDK-SETUP | Pinned SDK, minimum binary, Forge-managed environment, doctor check and repair, docs (route stays off) | none | false |
| Supervisor / SDK-SUPERVISOR | Detached supervisor, secured socket, lease with fencing and takeover, app-server lifecycle | SDK-SETUP | false |
| Admission / SDK-ADMISSION | Per-turn ledger, close parity with terminal-turn proof, sticky routes, declining approval handler, route switched on, first real delegation | SDK-SUPERVISOR, EXEC-MODES | false |
| Resume / RESUME-FIX | Fix rounds continue the task's worker thread; drift starts fresh; benchmark evidence | SDK-ADMISSION | false |
| Live / LIVE-EVENTS | Turn state machine, reattach, signals bound to their turn and answered by steer or interrupt | RESUME-FIX | false |
| Rollout / UPGRADE-CLEANUP | Client upgrade path, archival and pruning, parity matrix, end-to-end runs | LIVE-EVENTS | false |

## Verify plan

Each task: focused regression tests, `forge task close` (full suite plus one three-lens review), green
CI. Checks include version-mismatch messages naming both versions; an unexpected approval request
declined and logged; stale-lease takeover and live or uncertain holder refusals; close refused on an
unknown or running turn and on an undelivered signal; exact-turn signal delivery; archive and prune
touching ledger threads only. RESUME-FIX records the benchmark: three recorded fix rounds, each
replayed three times cold and three times resumed (same model, effort and brief; each trial in a fresh
worktree at the round's snapshot with the same findings; resumed trials fork the saved worker thread);
median uncached input tokens and wall time. UPGRADE-CLEANUP runs the parity matrix — claude mode,
codex mode, and hybrid on the SDK and plugin routes; each cell checks setup, init/adopt/upgrade, a
out-of-scope file shown to the reviewer, hook delivery and task close — as pytest cells on Ubuntu and native-Windows
CI, labelled per decision 0065, plus one real task per mode observed locally on macOS. End-to-end, in
throwaway clients (never a real client): a fresh `forge init` client running one real task with a
resumed fix round, and an older-template client with an active plugin task upgraded twice, the task
finishing on the plugin.
