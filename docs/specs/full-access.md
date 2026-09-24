---
slug: full-access
title: Full access: Forge judges the result, not each write
status: draft
saved: 2026-09-24T12:48:16+00:00
---

# Full access: Forge judges the result, not each write

## Why

Forge blocks the coordinator's writes with a session lock and guesses from
Bash command text whether a command writes. The guess can never be complete,
so every review found another hole, and each patch added code and false
refusals. The lock is about 1,100 lines of hook code and 60 tests, needs a
degraded-mode outage valve, and still proves nothing about who wrote a change.
Decision 0087 gives agents full access: the result is judged by proof, review
and CI instead.

## Behaviour

- Any agent may edit any file at any time. No hook refuses or claims a write
  because of what it writes or where: product and canon files, `.factory/`
  records, conflicted files, other worktrees and paths under symlinked
  parents are all writable. Recorded state stays trustworthy through the
  recorders' consistency checks, as today.
- The boundary moves from writing to shipping. Unplanned work can be written
  but cannot ship: every PR still needs a `Ticket:` naming an approved task or
  a closed Lite window (the PR ticket check), and a task closes only with an
  approved plan, passing proof and a clean review.
- `task close` keeps its proof, review and seal. The review brief lists every
  file in the task's measured diff that is outside its declared write scope,
  derived from the diff itself (not only from recorded scope amendments), and
  names any that overlap the write scope of another active task in the story.
  The task PR body carries the same list; when close runs again on an already
  open PR, it refreshes that list in the PR body. Nothing here refuses.
- Close no longer requires a recorded Codex launch or a degraded window.
- Lite windows stay: `mode done` measures the committed diff since the window
  opened and still enforces the file budget and clean reviews.
- Degraded mode and the old quickfix window can no longer be started;
  starting either prints a one-line explanation and changes nothing. A window
  already open from before the upgrade can still be closed or abandoned with
  its existing command, so no task is stuck behind it.
- Still enforced by hooks: the question gate, the ban on raw `codex exec` and
  direct companion launches, the commit check, the sign-off gate and the
  destructive-command denylist. The hook registration contract becomes:
  Claude's PreToolUse matcher covers `Bash` and `AskUserQuestion`; Codex's
  covers its shell tool and `request_user_input`. Edit, Write, MultiEdit,
  NotebookEdit and `apply_patch` are no longer routed to the hook, and
  `check_dual_runtime.py` and `forge doctor` check this contract.
- The executor mode (decision 0085) says who is expected to write and whom
  `forge delegate` hands work to; it is not a write lock. Decision 0087 amends
  0085 accordingly.
- `docs/specs/strict-role-split.md` is superseded by this spec. The criteria
  in `delegation-boundary.md` and `dual-coordinator-parity.md` that require
  out-of-scope refusal, coordinator write denial, protected-state write
  enforcement or a degraded substitute are replaced by this spec's criteria.
- The session-start message, AGENTS.md, CLAUDE.md, WORKFLOW.md, the Forge
  skill, the product brief and `workflow-modes.md` describe the new rule in
  one or two sentences.

## Acceptance criteria

- A coordinator Edit, Write, apply_patch or Bash write to any file (product,
  canon, `.factory/`, a conflicted file, another worktree) is never refused
  by a Forge hook.
- A PR without a `Ticket:` naming an approved task or a closed Lite window is
  still refused by the PR ticket check.
- `task close` on a task whose diff includes a file outside its write scope,
  with no scope amendment, succeeds when proof and review pass; that file is
  named in the review brief and the PR body, and an overlap with another
  active task's scope is named as such.
- Re-running `task close` on an open PR refreshes the out-of-scope list in
  its body.
- `task close` succeeds without any recorded Codex launch for the task.
- `mode done` still refuses a Lite window whose committed diff exceeds its
  file budget or has unclean reviews.
- `forge mode degraded start` and `forge quickfix start` explain they are
  removed and change nothing; an already-open degraded or quickfix window
  can still be closed or abandoned.
- Raw `codex exec`, destructive commands and phase-advancing scripts without
  sign-off are still refused.
- `check_dual_runtime.py`, `forge doctor` and the Windows hook CI job pass
  with the new registration contract; the Windows job's test selector no
  longer names deleted lock or degraded tests.
- The write-guard code and its tests are deleted, not disabled.
