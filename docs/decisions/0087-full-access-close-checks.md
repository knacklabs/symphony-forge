---
status: accepted
confirmed_by: "Ravi Kiran Vemula"
date: 2026-09-24
stories: []
supersedes: 0037-strict-role-split
---

# Full access: review and close checks replace the write lock

## Context

Forge stops the coordinator from writing product files with a session write
lock. For Bash it has to guess from the command text whether a command writes,
and that guess can never be complete: every review round found another way
through (sed `w`, `find -exec`, `xargs`, redirects, interpreters). The lock
cost about 1,100 lines of hook code, about 60 tests, a degraded-mode outage
valve, false refusals of harmless reads, and a steady stream of findings. It
still proved nothing about who wrote a change, and the checks at close were
already advisory.

## Decision

Agents get full access. Forge no longer blocks writes while work happens; it
judges the result. `task close`, `mode done`, the review and CI remain the
enforcement: proof must pass, the review must be clean, and files outside the
task's declared scope are listed for the reviewer and in the PR body instead
of being refused. Close no longer requires a recorded Codex launch. The
executor mode (hybrid, codex, claude) says who is expected to write; it is the
default way of working, not a hook-enforced lock.

## Consequences

- The Bash write parser, the Edit/Write/apply_patch lock, write admission and
  revocation, degraded mode and the old quickfix window are deleted. Lite
  stays as the plan-free small-fix path, measured at `mode done`.
- Kept: the question gate, the ban on raw `codex exec` and direct companion
  launches, the commit check, the sign-off gate, the destructive-command
  denylist, approval recording, the delegation lock and task close's proof
  and review.
- Out-of-scope work is caught by people and review, not by refusal; no scope
  amendments are needed for a legitimate extra file.
- A hand-edited `.factory` record is caught only when it is inconsistent;
  records are checked, not signed. This was already true.
- The executor-modes task gets simpler: claude mode needs no write admission.
- Amends 0085: the executor mode chooses whom `forge delegate` hands work to;
  it no longer restricts who may write or requires write admission.
