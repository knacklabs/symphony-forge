---
status: superseded
superseded_by: 0093-lean-forge-rebuild
confirmed_by: "vrknetha"
date: 2026-07-27
stories: [FORGE-DELEG-1]
---

# Delegation Gates

## Context

The Claude to Codex handoff was governed by prose. Four reported failures each
traced to something a script could have checked and did not:

- Write permission was decided per request by a subagent, and three layers
  disagreed on the default (the companion defaulted read-only, this repo's hook
  said read-only unless `--write`, the plugin's own subagent said default to
  `--write`). A `read-only` sandbox with `approvalPolicy: never` cannot write
  *and* cannot ask, so a run narrated a plan and exited 0.
- Completion meant "the model stopped talking": `forge stage done` checked only
  that the stage had been started, so a run that did three of eight acceptance
  criteria closed clean and `pr_ready` printed PR_READY.
- Nothing composed context for the executing runtime. `factory/prompts/
  implementer.md` was referenced by five docs and read by zero scripts.
- The design skills `harness.yaml` demands for user-facing work were not
  installed for the runtime asked to attest them, so those attestations were
  false.

The task contract already carried `write_scope`, `verify_commands` and
`required_tests`. All three were consumed only by the renderer.

## Decision

The delegation boundary is instrumented rather than described. Six gates:

1. `stage start` records the stage's base commit and the dirt already in the
   tree; `stage done` measures against them and refuses on an empty product
   diff, an out-of-scope path, a missing successful write launch, a failing
   required-test proof, or a failing `verify_commands` entry.
2. `stage done --incomplete "<what is missing>"` gives partial delivery a
   vocabulary: the stage stays open and the gap enters the timeline.
3. `forge delegate` composes the brief, derives write permission from stage
   state, invokes the installed companion directly with a subprocess argument
   vector, and records running and terminal evidence under one launch id.
   An OS-backed per-task lock beside the protected authority ledger
   excludes concurrent writers and is also held across the final stage
   measurement and persisted done transition. A shared state lock serializes
   stage-state transitions.
   Stage close refuses while any matching launch is active. `--print-only` is
   diagnostic and cannot satisfy stage close. Background write launches are
   refused because their completion cannot be bound to the final measurement.
   A retry reconciles a dead interrupted process before starting another
   writer; every terminal path reaps the process group plus trusted descendants
   observed during execution and a post-exit quiet window before evidence or
   lock release on TERM, HUP and QUIT. PID start identity prevents
   a recycled PID from being mistaken for the original worker. If only an
   unverified numeric process group remains, retry blocks without signalling it.
   Authoritative launch rows, decomposition, stage state, and locks live in
   Git's protected control directory; their `.factory/` copies are best-effort
   diagnostic mirrors the worker may write but gates never trust.
4. Direct companion Bash calls are off-contract and routed to `forge
   delegate`; the pre-tool hook is not an authorization parser for arbitrary
   shell. Every literal companion token is routed through `forge delegate`;
   lock paths validate the canonical task-id grammar.
   `stage done` enforces the successful-launch postcondition.
5. Required tests are runner-owned `{id, path, command}` proof objects. The
   shell-free command substitutes `{path}` and `{id}` in the runner's native
   selector, writes fresh JUnit XML at `{report}`, and stage close verifies that
   report names the declared test exactly and carries `file="{path}"`.
   Parameterized cases declare their exact emitted testcase name. Shell and
   `env` wrappers are refused. Every required-test command must leave the
   verified product tree unchanged before the next proof runs, including every
   tracked path, modes, symlinks, index flags and status; its process tree
   must also be empty.
   `verify_commands` remain broader proof commands. Both command classes are
   read-only: stage close snapshots the product tree and protected Forge
   authority once around the whole proof set, refuses any mutation, and then
   binds the done transition to that exact final snapshot. Both command classes
   must be runnable and prose is refused at record time.
6. `forge doctor` checks that every skill the harness demands is loadable by
   each runtime expected to attest it.

`forge codex status` is deliberately advisory: it reads a third-party plugin
path, and a diagnostic over data this repo does not own must never be able to
block a ship.

## Consequences

A stage can now fail to close. That is the point — the previous behaviour was
that it could not. Two costs are accepted:

- Emptiness is judged on product paths only (`.factory/` and `plans/` are
  exempt), because the workflow writes those itself on every command. This
  exemption is deliberately narrower than `pr_ready`'s `EVIDENCE_PATHS`, which
  exempts all of `factory/` and `docs/` — in the harness's own repo that is the
  product, and reusing it would make the scope check vacuous exactly where it
  is dogfooded.
- A path already dirty when the stage started is not attributed to the stage,
  compared by CONTENT rather than name — otherwise a worker could keep editing
  an out-of-scope dirty file invisibly, and work confined to an in-scope dirty
  file would read as an empty diff.
- A path cannot close with staged content different from the tested worktree;
  split index/worktree states are refused.
- The decomposition may still be re-recorded mid-stage (the sanctioned repair
  for a scope that turns out to be wrong), but closing over a contract rewritten
  after the stage started is refused: `stage start` again to re-baseline, on the
  record. Re-baselining discards credit for work already in the tree, so it is
  the first move after a scope correction, not the last.
- Tasks are sequential inside one story worktree and follow decomposition
  order. Parallel delivery happens between dependency-ready stories, each in
  its own worktree; task-level `--parallel` is refused.
- Companion cache lookup can drift. Delegation fails closed with
  `forge doctor --fix` guidance and never falls back to a pasted shell command.
- Runner ownership stays in the decomposition: Forge executes the declared
  required-test command instead of guessing collection from source syntax.

Existing shipped history is untouched: the `verify_commands` refusal applies at
record time only, and `forge doctor` reports an active decomposition still
carrying prose so it is fixed before the next stage closes.

Delegation and proof commands are trusted repository inputs. The cleanup gate
is deliberately not described as hostile-code containment: a process that
double-forks and clears its environment needs a digest-pinned container
boundary. That separate runtime capability is deferred until Forge permits
untrusted commands or third-party worker code to execute with write access.
