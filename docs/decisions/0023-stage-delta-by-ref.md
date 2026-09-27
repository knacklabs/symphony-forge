---
status: superseded
superseded_by: 0093-lean-forge-rebuild
confirmed_by: "vrknetha"
date: 2026-08-05
stories: [FORGE-UPG-1]
---

# Stage Delta By Ref

## Context

A stage asks one question worth asking: did the delegated worker change what it
said it would, and nothing else?

Answering it currently takes `base_sha`, a `dirty_at_start` content map, a
`task_sha256` contract digest, and 55 refusal paths across 1,146 lines. The
state lives in `.factory/stages.json`, which the harness rewrites on almost
every command, and the baseline is a commit sha that only `stage start` may set.

Those pieces interact, and today two of them combined into a trap with no exit.
A worker raised a correct scope-change signal; the decomposition was re-recorded
to widen the write scope; the work was done and committed; `stage done` refused
because the contract had changed after the stage started, and instructed a
`stage start` to re-baseline. That re-baselined onto the commit containing the
finished work, so the baseline became the finished state and `stage done` then
refused again — an EMPTY diff — with no way back, because restarting again is
what caused it. The work was complete, reviewed clean and committed; only the
bookkeeping was unrecoverable.

The coupling is the defect: **a contract change forces a baseline reset.** It
was meant to stop someone widening scope moments before closing over it. What
it actually does is destroy the measurement whenever the repair arrives after
the work, which is exactly when a scope signal arrives.

Underneath sits the same mistake as the ledgers: the stage tracks the identity
of a commit where it cares about the content of a delta.

## Decision

A stage's baseline is a git ref — `refs/forge/stage/<id>` — written at
`stage start`. The delta is `git diff refs/forge/stage/<id>` plus the worktree.

Re-recording a task contract mid-stage is ledgered, never baseline-resetting.
The contract change and its reason become evidence a reviewer reads; the
baseline is untouched, so the delta stays measurable.

## Consequences

- Delete the re-baseline path in `stage start`, the contract-changed refusal in
  `stage done`, and the guard added to protect the trap they formed together.
  Three mechanisms and their interactions go, replaced by one ref.
- A widened scope is now visible rather than prevented: `stage done` still
  measures the diff against `write_scope`, and the ledgered contract change
  tells a reviewer the scope moved and why. Decision 0018 already puts the
  delegation boundary under review rather than under a refusal.
- The ref survives commits, rebases and worktree switches, so the baseline
  cannot be silently overwritten by an ordinary git operation.
- `stage done` keeps its empty-diff check, which catches the stalled or
  read-only run it was written for — the signature it exists to detect.
- Stale refs need cleaning at `pr_ready`, alongside the evidence it archives.
