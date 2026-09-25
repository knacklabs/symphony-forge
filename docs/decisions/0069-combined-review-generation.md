---
status: superseded
confirmed_by: "User (explicit approval, Codex conversation 2026-09-11)"
date: 2026-09-11
stories: [FORGE-COORD-1]
superseded_by: 0092-close-is-green-ci-and-clean-review
---

# One combined review generation with one selected pointer

## Context
Decision 0064 reduced review to one combined quality, performance, and security
operation, but still required three separately published review artifacts. That
keeps three files in sync and makes interrupted publication ambiguous. The user
subsequently directed Forge to keep this design simple and to review the final
simplified plan before approval.

## Decision
Amend only Decision 0064's review-publication shape. Each complete review
attempt calls the installed helper once and publishes one immutable generation
containing the raw helper result and all three genuine lens records, followed
by one small task-scoped pointer selecting that generation. A blocking attempt
is selected and revokes clean status; fixes require a new complete generation.

The existing three fixed review files become one-time upgrade inputs and are
never runtime fallback authority after migration. A citation-based finding
rejection creates another immutable generation bound to its source generation
and citation. It does not rewrite helper output or claim that the rejected
projection came directly from unchanged output.

Also narrow Decision 0054's early draft-PR permission for this story: use a
draft only when a required platform CI result cannot run without one. The draft
is CI transport only. Formal review happens once the complete required platform
report exists, and the same draft then follows normal readiness and promotion.

## Consequences
The complete set and its pointer share one schema and one resolver. Incomplete
or tampered output cannot replace the selected generation. Migration binds old
sealed proof from the current upgrade commit to the original marker and exact
fixed-artifact bytes; it does not pretend that a pointer existed in the old
marker commit. All other Decision 0064 and Decision 0054 requirements remain
active, including genuine three-lens assessment, complete review input,
lossless helper output, normal task proof, and declared platform gaps.
