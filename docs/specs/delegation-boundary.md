---
slug: delegation-boundary
title: Delegation boundary: briefed, bounded, measured
status: confirmed
saved: 2026-07-27T12:06:47+00:00
---

# Delegation boundary: briefed, bounded, measured

## Capability

The Claude→Codex handoff becomes an instrumented boundary. Three facts that
are today decided by judgement — *may this run write?*, *did it finish?*,
*what does it know?* — become artifacts a script can check and refuse on.

## Why

Four reported failures, each traced to a mechanical cause:

1. **The harness gets skipped and nobody can say why.** The delegation step
   has no command, so there is no deterministic record of what should have
   happened.
2. **Codex is launched read-only and stalls silently.** Three layers disagree
   about the default (the companion, this repo's hook, and the plugin's own
   subagent), and a `read-only` sandbox with `approvalPolicy: never` cannot
   write *and* cannot ask — so it narrates a plan and exits 0.
3. **Partial work reports clean.** Success is "the model stopped talking".
   Nothing compares what changed against what the task declared.
4. **Codex ignores existing components and design rules.** No script composes
   context for it, and the design skills the harness demands it attest are not
   installed for that runtime.

## Behaviour

**A delegation is a briefed, recorded act.** `forge delegate <task-id>`
composes a brief from artifacts that already exist — the task's objective,
acceptance criteria, `write_scope`, `required_tests`, `reviewer_focus`, the
implementer prompt, the active decisions, the lessons matching the task's
paths, and the modules already present in that scope — writes it to
`.factory/briefs/<task-id>.md`, invokes the installed companion directly with
a subprocess argument vector, and records running and terminal evidence with
one launch id and the brief's digest. Stage close refuses while any matching
launch remains active. An OS-backed single-writer lock in Git's
protected control directory prevents canonical-brief rewrites and is held by
stage close through its persisted done transition; a shared state lock
serializes stage-state changes and revalidates stage identity. Retry reconciles
a dead interruption, and every terminal path reaps the process group plus
trusted descendants observed during execution and a post-exit quiet window on
TERM, HUP and QUIT. PID start identity prevents a recycled PID
from being mistaken for the original worker; an unverified reused process group
blocks retry and is never signalled. Authoritative launch evidence,
decomposition, and stage state are protected with the locks; their `.factory/`
copies are best-effort, non-authoritative mirrors. `--print-only` never counts
as a launch.

**Write permission is derived, not typed.** An active stage with a non-empty
`write_scope` is a write run. `--read-only` is the explicit exception.

`forge delegate <task-id> --scope <repo-path> [--scope ...]` may narrow a
write launch to a proper subset of the effective approved scope. One exact
approved file is a valid member. The normalized subset is stored in the
existing delegation `write_scope`, included in the brief and launch identity,
and enforced by admission hooks; it creates no second scope ledger. Omitting
the flag uses the complete effective scope. Equal, empty, escaping, duplicate,
or out-of-scope selections refuse before launch.

**A brief is not skippable.** `forge delegate` is the canonical execution
boundary; direct companion Bash calls are off-contract and routed back to it.
`stage done` refuses without a successful write launch bound to the active
stage and its recorded launch identity, including the narrowed write scope.
The recorded brief digest remains historical launch evidence; later valid
regeneration of the derived brief does not invalidate a completed stage-bound
write. The hook does not try
to authorize arbitrary shell by reconstructing its final argv; every literal
companion token is routed through `forge delegate`.
Active write stages run in the foreground; background mode is read-only
exploration because a queued worker cannot be included in the final measurement.

**Completion is a measurement.** `forge stage done` refuses unless the diff
since the stage's base commit is non-empty, every changed product path is
covered by the task's `write_scope`, a successful write launch was recorded,
every `required_tests` proof names an existing repo-relative path, its
runner-owned command exits green, and its fresh JUnit report names the declared
test; every `verify_commands` entry also runs green. Required tests use
`{id, path, command}` objects whose command includes runner-native `{path}` and
`{id}` plus fresh-report `{report}` placeholders. The fresh report must
name the testcase exactly and carry a testcase `file` attribute equal to the
declared path. Parameterized cases declare their exact emitted name. Every
proof set is wrapped in one exact product-tree and protected-authority
transaction. Neither required tests nor `verify_commands` may change tracked
content, mode, symlink, index flag, status, or Forge authority; every observed
trusted-command process tree must also be empty. This avoids rehashing the repository after
each required test while binding all proofs to one final snapshot. Source-text
inference is not test evidence. Commands must invoke the runner directly —
prose, shells, and `env` wrappers are refused at record time.

**Tasks are sequential; stories may be parallel.** One story owns one isolated
Git worktree. Its task stages run strictly in decomposition order, so two tasks
never edit that worktree concurrently and task-level `--parallel` is refused.
The roadmap's story dependency graph decides which stories are ready at the
same time; independent ready stories may run in separate worktrees.

**Partial delivery is sayable.** `forge stage done --incomplete "<what is
missing>"` leaves the stage open and records the gap, so a worker that
finished 60% has vocabulary other than silence.

**A stalled run is visible without being asked for.** `forge codex status`
reads the plugin's job registry and reports each job's status, phase, write
flag and age, flagging a long-running job with no phase change and a
`write: false` job launched while a stage was active.

**A skill the harness demands must be loadable where it is attested.**
`forge doctor` checks the required and advised skills against every runtime
expected to attest them, and `--fix` installs what is missing.

## Acceptance criteria

- A stage cannot be closed on an empty diff, an out-of-scope change, a
  missing declared test, or a failing per-task verify command.
- A stage cannot close with different staged and worktree content for the same
  path, or after proof code changes product or protected authority state.
- Task-level `--parallel` is refused; task stages run in order inside one story
  worktree.
- A decomposition recording prose where a command belongs is refused.
- A stage without a successful fresh write launch through `forge delegate`
  cannot close; direct literal companion Bash calls are routed to that command.
- New decompositions reject opaque `required_tests` strings; each required
  test is a runner-owned `{id, path, command}` proof executed at stage close
  and confirmed through fresh JUnit XML written at `{report}`. The testcase
  name exactly matches the declared id and its `file` attribute exactly matches
  the declared path.
- The generated brief carries the acceptance criteria, the write scope with
  its existing modules, and — for user-facing work — the design rules inline.
- A narrowed delegation records and enforces only its proper approved subset;
  omission retains the full effective scope and no parallel scope authority is
  created.
- `forge codex status` reports the write flag per job and flags a stalled one.
- `forge doctor` reports a required skill that a runtime cannot load.
- `forge next` names the delegation step.

## Boundaries

`forge codex status` reads a third-party path; it is a diagnostic and must
never be able to block a ship. The board stays read-only — delegation state is
CLI-surfaced this round. Existing shipped history keeps its prose
`verify_commands`; only new decompositions are refused.

Delegation and proof commands are trusted repository inputs. Process groups,
PID identity, inherited launch tokens, termination handlers, and a post-exit
quiet window provide deterministic cleanup for ordinary detached children;
they are not a hostile-code sandbox against a process that deliberately
double-forks and clears its environment. Supporting untrusted commands requires
the separately deferred, digest-pinned container runtime boundary.
