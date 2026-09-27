---
status: superseded
superseded_by: 0093-lean-forge-rebuild
confirmed_by: "Ravi"
date: 2026-07-21
stories: []
---

# Recurring review findings escalate to refactors, never a fourth patch

## Context

Review findings were fixed one at a time with no memory across tasks: the
same defect class could be patched in task after task without anyone seeing
the pattern, and the structural cause was never removed. The Gantry factory's
review-loop escalation rule ("recurring findings are a design signal, not a
fix queue") proved that clustering findings by class and forcing a
consolidate-or-split decision keeps a repo from accreting the same debt
forever.

## Decision

Review findings are recorded structured (`{category, area, summary}`) so
`./forge findings patterns` can cluster them across shipped tasks. When the
same class surfaces MORE THAN TWICE, patching stops: the team either
CONSOLIDATES (invariant decision record + a `kind: refactor` roadmap story
auditing every site, pinned with tests) or SPLITS OUT (removes the entangled
scope with an explicit revisit trigger in the deferral ledger). A recurring
CLASS is distinguished from a converging TAIL — distinct findings trending
down stay in the normal loop. Surfacing is advisory (`forge next` banner,
`pr_ready` warning), never a ship blocker: the recurring class predates the
task at the gate, so it routes to a refactor story instead of holding an
unrelated ship hostage.

## Consequences

- Reviewers must categorize findings with stable kebab-case slugs; a renamed
  class is an undetected class.
- Planners and grillers must consult `forge findings patterns`; a plan that
  silently patches a known recurring class fails the plan grill.
- The escalation consumes roadmap capacity deliberately (a refactor story)
  instead of invisibly (endless per-task fixes).
- Doctrine lives in WORKFLOW.md "Recurring Findings — a design signal".
- Provenance-note categories are NOT defect classes and do not escalate:
  `reviewed-separately` records that an artifact's code changed after the review
  was recorded (a review-vs-code timing note, not a defect), so its recurrence
  is expected and routes to no consolidation.
