---
status: accepted
confirmed_by: "Ravi Kiran Vemula"
date: 2026-08-18
stories: [FORGE-CFS-1]
---

# Scoped-layout activation is deferred and atomic

## Context

The scoped-layout marker (the `.factory/stories/<KEY>/` story dir, tested by
`story_uses_scoped_layout`) gates BOTH story-scoped evidence (task
story-scoped-evidence) and the worktree-local untracked run pointer (task
run-pointer-untracked). Turning it on for a real story immediately routes all
story evidence — including plan grills — through `evidence_path()`. But
several consumers still read the legacy singleton paths by hand: `plans.py`
rereads `.factory/grills/plan.json` after `require_grill`, `pr_ready`
reads/archives grills, and siblings may exist. Activating the marker before
those consumers learn the helper breaks plan save and `pr_ready` — signals
S-0001, S-0003, S-0004, and S-0005 all hit exactly this across five
delegations. Every mechanism task keeps bumping into it.

## Decision

No real story runs under the new layout until `migration-and-vendor` flips the
intake marker. Tasks 1–5 deliver the layout MECHANISMS (story_dir/evidence_path,
the untracked run pointer, per-event files, in-place ship, merge-survivable
hooks) with intake staying MARKER-NEUTRAL; their required tests prove the
mechanisms by SYNTHESIZING the marker, never by activating it through intake.
`migration-and-vendor` is the single atomic activation: it audits and migrates
every remaining legacy-path consumer (`plans.py`'s plan-grill reread and any
siblings) to `evidence_path()`/`run_state_path()`, THEN sets the intake marker,
gated by a green full gate suite.

## Consequences

- The recurring scope-change signal (plans.py plan-grill read) is resolved once,
  here, instead of re-litigated per task: defer to `migration-and-vendor`; do
  not touch `plans.py`; required tests synthesize the marker.
- Tasks 1–5 are provable in isolation and cannot regress unmigrated consumers,
  because the marker is never production-on before task 6.
- `migration-and-vendor` carries the consumer audit as explicit scope: it must
  enumerate every hand-joined legacy read, migrate them, and only then activate.
  A missed consumer is a task-6 gate failure, not a shipped break.
- Clients pick up activation via `forge upgrade`, as with the rest of FORGE-CFS-1.
