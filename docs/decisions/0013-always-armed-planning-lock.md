---
status: accepted
confirmed_by: "vrknetha"
date: 2026-07-24
stories: []
supersedes: 0004-mandatory-plan-mode
---

# Always-armed planning lock with bounded escape hatches

## Context

Decision 0004 armed the product-code lock only for an active, signed-off,
unplanned task and explicitly excluded Bash-level writes. In practice the
main skip path was exactly that gap: devs (and drifting agent sessions)
edited product code with no task active, or wrote files via shell
redirects, and small-to-medium fixes routinely bypassed plan mode.
Confirmed in chat (workflow-enforcement design, 2026-07-24): threat model
is agent drift, small fixes need a deliberate recorded exit, not a silent
judgment call.

## Decision

The planning lock is ALWAYS armed: product-code writes are denied unless one
of three exits is active — an approved plan, an explicit quickfix window
(`forge quickfix start "<reason>"`), or an explicit lite window (`forge mode lite`).
Quickfix and lite windows have bounded file budgets and are durably ledgered
in plans/quickfixes.jsonl. The PreToolUse hook also heuristically denies Bash
write commands (redirects, tee, sed -i, cp, mv, touch) that target product
paths while locked.

## Consequences

- The "no active task" and "shell write" bypasses of 0004 are closed;
  missing or reset run state now means locked, never unlocked.
- Skipping plan mode becomes a deliberate, recorded act with a scope cap;
  exceeding the quickfix budget forces plan mode.
- The Bash guard is a drift defense, not an adversarial sandbox: it is a
  heuristic and may need pattern tightening; artifact gates
  (verify/review/pr_ready) remain the backstop, as under 0004.
- Allowlisted planning surfaces (plans/, docs/, .factory/, factory/,
  prototype/, harness files) stay freely writable, keeping discovery and
  prototyping ceremony-free.
