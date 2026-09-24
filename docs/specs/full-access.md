---
slug: full-access
title: Full access: Forge judges the result, not each write
status: confirmed
saved: 2026-09-24T15:16:16+00:00
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

**Writing.** No hook refuses or claims a write because of the file it writes
or where it is: product and canon files, `.factory/` records, conflicted
files, other worktrees and paths under symlinked parents are all writable.
The retained command gates still apply to the commands themselves (below).
Recorders keep checking records for consistency; a deliberate, consistent
hand edit of a record is not detected because records are not signed, as
today.

**Shipping.** The boundary is the existing PR ticket check, unchanged: every
PR declares a completed work record (a closed task marker, a closed Lite
window, or a harness re-vendor) through a `Ticket:` line or its canonical
branch name. A task marker exists only after `task close`, which needs an
approved plan, passing proof and a clean review. Unplanned work can be
written but cannot ship without such a record.

**Task close.** `task close` keeps its proof, review and seal, and no longer
requires a recorded Codex launch. The review brief lists every file in the
task's full diff since its stage base that is outside the declared write
scope, derived from the diff itself (not from scope amendments), names any
that overlap another active task's write scope, and lists changed records,
plans and decisions separately so the reviewer sees them too. The task PR
body carries the same list inside a Forge-owned marked block; re-running
close on an open PR replaces only that block (appending it if absent) and
never touches the rest of the body. Nothing here refuses.

**Scope corrections mid-task.** Amending a task's write scope, tests or verify
commands during an active stage no longer needs a recorded launch; the
recorder binds the amendment to the active stage instead.

**Lite.** `mode done` reviews every committed change since the window opened
(nothing filtered out) and counts every committed file except tests and
Markdown against the five-file budget, including files previously exempt.

**Removed.** Degraded mode and the old quickfix window are removed entirely:
their start and close commands say they were removed and change nothing.
Existing closed records stay readable and still satisfy the ticket check for
history. No window may be open in this repository when this change merges;
client repos can't carry one across, because upgrade refuses open windows.

**Hooks kept.** The question gate, the ban on raw `codex exec` and direct
companion launches, the commit check, the sign-off gate and the
destructive-command denylist. Registration contract: Claude's PreToolUse
matcher covers `Bash` and `AskUserQuestion`; Codex's covers its shell tool and
`request_user_input`; Edit, Write, MultiEdit, NotebookEdit and `apply_patch`
must NOT be routed to the hook. `check_dual_runtime.py` and `forge doctor`
check both what is covered and what is absent.

**Who writes.** `forge delegate` keeps handing work to Codex as today. The
executor setting planned in the warm-threads story will choose whom delegate
hands work to; this story adds no executor guidance.

**Canon.** `docs/specs/strict-role-split.md` is marked superseded by this
spec: it stops governing new work, and roadmap items already linked to it
stay valid. The criteria in `delegation-boundary.md` and
`dual-coordinator-parity.md` that require out-of-scope refusal, coordinator
write denial, protected-state write enforcement or a degraded substitute are
replaced by this spec's criteria. `docs/degraded-mode.md` is deleted. The
session-start message, AGENTS.md, CLAUDE.md, WORKFLOW.md, the Forge skill,
the product brief, `workflow-modes.md`, `docs/QUALITY.md`, `docs/FACTORY.md`
and the parity architecture describe the new rule in one or two sentences
and stop mentioning degraded mode or a launch requirement.

## Acceptance criteria

- A coordinator Edit, Write, apply_patch or Bash write to any file (product,
  canon, `.factory/`, a conflicted file, another worktree) is never refused
  because of the file it writes; destructive commands, raw `codex exec` and
  phase-advancing scripts without sign-off are still refused.
- A PR without a completed work record declared by a `Ticket:` line or its
  canonical branch is still refused by the PR ticket check.
- `task close` on a task whose diff includes a file outside its write scope,
  with no scope amendment and no recorded launch, succeeds when proof and
  review pass; that file is in the review brief and in the PR body's Forge
  block, an overlap with another active task is named, and changed records
  are listed separately.
- Re-running `task close` on an open PR replaces only the Forge block and
  keeps human edits and Ticket lines.
- A write-scope amendment during an active stage records without a launch.
- `mode done` reviews every committed change in the window and refuses when
  more than five non-test, non-Markdown files changed.
- `forge mode degraded start|done`, `forge quickfix start|done` say they are
  removed and change nothing; old closed records still satisfy the ticket
  check.
- `check_dual_runtime.py` and `forge doctor` fail if an edit tool or
  `apply_patch` is routed to the hook; the Windows hook CI job passes with a
  selector that no longer names deleted tests.
- `strict-role-split.md` shows as superseded and is not offered for new
  roadmap links; existing links still resolve.
- The write-guard code and its tests are deleted, not disabled.

## Success measure

- Metric: false write refusals per week and review-found guard bypasses.
- Baseline: several false refusals a day in coordinator sessions and a guard
  finding in most reviews of guard changes (2026-09-24 session).
- Target: zero write refusals; no guard code left to review.
- Check date: 2026-10-15
