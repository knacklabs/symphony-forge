---
slug: delegation-boundary
title: Delegation boundary: briefed, bounded, measured
status: confirmed
saved: 2026-07-27T12:06:47+00:00
---

# Delegation boundary: briefed, bounded, measured

## Capability

The coordinator→Codex handoff is a briefed, bounded boundary. Forge validates
what the task may change and what proof must pass. Claude retains an
instrumented plugin-companion lifecycle; native Codex delegates through the
host's role-based subagents without adding another process manager.

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

**A delegation is briefed and validated.** `forge delegate <task-id>` composes
a canonical brief from the task objective, acceptance criteria, `write_scope`,
`required_tests`, `reviewer_focus`, implementer prompt, active decisions,
matching lessons, and existing modules. It writes
`.factory/briefs/<task-id>.md` after validating the current task, grill, stage,
worktree and effective scope.

In native Codex the command records a preparation row binding task, worktree,
stage, brief digest and effective or narrowed scope, returns dispatch
information, and stops. Main calls
the host's role-based `spawn_agent` with the matching configured role and the
canonical brief, omitting model and reasoning overrides so that role's
configured defaults apply and may pin either value. Forge never invokes
`codex exec`, registers the native process/session, or
wraps host collaboration in a second lifecycle. In Claude, the same command
continues to invoke the protected `codex-plugin-cc` companion and retains that
route's launch, terminal, lock and cleanup evidence.

**Write permission is derived, not typed.** An active stage with a non-empty
`write_scope` is a write run. `--read-only` is the explicit exception.

`forge delegate <task-id> --scope <repo-path> [--scope ...]` may narrow a
write dispatch to a proper subset of the effective approved scope. One exact
approved file is a valid member. The normalized subset is stored in the
existing delegation `write_scope`, included in the brief, and recorded in the
native preparation row; Claude also binds it into companion launch identity.
It creates no second scope ledger. Omitting
the flag uses the complete effective scope. Equal, empty, escaping, duplicate,
or out-of-scope selections refuse before dispatch.

**A brief is not skippable.** `forge delegate` is the canonical validation and
brief-preparation boundary. Raw/direct/nested `codex exec` and direct plugin
shell launch are off-contract and hook-denied in both runtimes. In
native mode stage close requires the current preparation row but no launch ID,
terminal row, process token, PID ancestry or held lock. Later valid regeneration
of the derived brief does not invalidate completed task proof. Claude retains
its successful plugin-launch requirement and degraded-mode outage valve.

**Native host features stay at their defaults.** Forge adds no native
foreground/background rule and no status, cancel, resume, recovery, signal,
process-cleanup or session-fencing restriction. Those operations belong to the
host. This deliberately removes mechanical native authorship attribution.

**Completion is a measurement.** `forge task close` owns the integrated proof
and review sequence. Its final `stage done` step refuses unless the diff
since the stage's base commit is non-empty, every changed product path is
covered by the task's `write_scope`, every `required_tests` proof names an existing repo-relative path, its
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

**Dependency-ready tasks may be parallel.** Every leaf owns an isolated task
worktree and PR. Dependency order still binds, and siblings overlap only when
their measured scopes are disjoint; overlapping scopes remain serialized.

**Partial delivery is sayable.** `forge stage done --incomplete "<what is
missing>"` leaves the stage open and records the gap, so a worker that
finished 60% has vocabulary other than silence.

**Status uses the owning runtime.** Native Codex uses the host's normal
subagent status and coordination tools without Forge restrictions. Under
Claude, `forge codex status` reads the plugin job registry as an advisory view;
it is never a gate.

**A skill the harness demands must be loadable where it is attested.**
`forge doctor` checks the required and advised skills against every runtime
expected to attest them, and `--fix` installs what is missing.

## Acceptance criteria

- A stage cannot be closed on an empty diff, an out-of-scope change, a
  missing declared test, or a failing per-task verify command.
- A stage cannot close with different staged and worktree content for the same
  path, or after proof code changes product or protected authority state.
- Task-level `--parallel` is refused. Dependency-ready sibling tasks may run
  concurrently only in isolated task worktrees with disjoint measured scopes;
  overlapping scopes remain serialized.
- A decomposition recording prose where a command belongs is refused.
- Native Codex closeout requires a validated canonical delegation but no
  launch-process proof. Claude closeout retains its protected companion launch
  requirement or documented degraded-mode substitute. Direct `codex exec` is
  rejected in either route.
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
- Native host status/cancel/resume/background features remain available without
  Forge policy. Claude `forge codex status` remains advisory.
- `forge doctor` reports a required skill that a runtime cannot load.
- `forge next` names the delegation step.

## Boundaries

`forge codex status` reads a third-party path on the Claude route; it is a
diagnostic and must never block a ship. The board stays read-only. Existing
shipped history keeps its prose `verify_commands`; only new decompositions are
refused.

Delegation and proof commands are trusted repository inputs. Claude's process
group, PID identity, launch-token and cleanup behavior remains specific to its
plugin companion. Native Codex makes no equivalent containment, cleanup or
authorship claim; the host owns its subagent processes and Forge judges the
result through task scope and proof gates.
