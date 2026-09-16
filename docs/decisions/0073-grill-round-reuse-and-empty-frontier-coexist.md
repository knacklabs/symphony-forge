---
status: accepted
confirmed_by: "User (selected reuse same gate, 2026-09-13)"
date: 2026-09-13
stories: [FORGE-COORD-1]
supersedes: 0071-empty-frontier-grill-proof
---

# Grill round reuse and empty-frontier proof coexist

## Context
Decision 0067 superseded Decision 0051 and permits a real question round to be
reused only when re-recording the same gate for the same story and task.
Decision 0071 later changed only the future one-round floor, but repeated
0051's retired no-reuse rule in its consequences. After both branches were
integrated, the accepted corpus therefore gave the recorder two incompatible
answers for the same re-recording.

## Decision
Decision 0067 remains the sole reuse rule: one pass may claim a matched round
once, and the same round may be reused only to re-record the same gate, story,
and task. Preserve Decision 0071's narrow exception after
`SHARED-COORDINATOR-JOURNEY`: an exact ledgered cold read with a complete
one-to-one finding-resolution map and no human frontier may record zero human
rounds.

## Consequences
- Supersede Decision 0071 as a record, while carrying its empty-frontier
  exception forward unchanged.
- Cross-gate, cross-story, cross-task, duplicate-within-pass, synthetic, and
  unbound reuse still refuse.
- No existing round, grill, schema, or task is rewritten. Shared owns the
  future zero-round proof fields and tests already assigned by the story plan.
