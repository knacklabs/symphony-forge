---
status: superseded
superseded_by: 0093-lean-forge-rebuild
confirmed_by: "Ravi"
date: 2026-08-09
stories: [FORGE-BOARD-7]
---

# The improvement loops are themselves audited (forge audit)

## Context

The harness is a graph of improvement loops (findings escalation — 0005,
lessons — 0006, deferrals, structured reviews). Each emits advisories, and an
advisory nobody acts on decays into theater: the recurring-class warning can
fire at every ship forever, an open deferral's trigger can come due unnoticed,
a lesson's `applies_to` globs rot after a rename and the lesson silently dies.
A graph of loops that only confirms itself fails circularly — sophisticated,
consistent, and detached from reality. Some loop must answer for the loops.

## Decision

`./forge audit` is that loop: a deterministic check that each improvement
loop still touches reality — ignored escalations (RECURRING class, ships
since flagging, no consolidating decision or refactor story), stale deferrals
(open > 60 days), decayed lessons (globs matching zero tracked files), and
review drift (latest shipped task's findings carry no structure, so
clustering is blind). It runs at ship cadence — `pr_ready` prints the
summary, `forge next` surfaces the count — and on real activity: the
`harness-health` workflow runs it in CI on `push:main` and manual
`workflow_dispatch`, not a daily cron. ADVISORY, never a ship gate.

## Consequences

- A decaying watcher becomes visible at the next ship instead of never;
  the fix is routed work (refactor story, `defer resolve`, lesson edit by
  PR), not a silenced warning.
- Advisory means a task can still ship over audit findings deliberately —
  the audit routes debt, it does not hold unrelated work hostage (same
  doctrine as the recurring-findings warning it extends).
- Thresholds (60 days, one ship past flagging) are frozen constants in the
  vendored machinery — projects do not tune them (see 0009).
