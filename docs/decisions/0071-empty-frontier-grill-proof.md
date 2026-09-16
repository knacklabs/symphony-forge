---
status: superseded
confirmed_by: "User (all plans approved, Codex conversation 2026-09-12)"
date: 2026-09-12
stories: [FORGE-COORD-1]
superseded_by: 0073-grill-round-reuse-and-empty-frontier-coexist
---

# Empty-frontier cold reads need no forced human question

## Context
Decision 0051 requires at least one ledger-matched human question for every
grill, even when a ledgered independent cold read found no human decision and
the repository already answers every issue. That turns an empty frontier into
a compulsory approval-shaped interruption. The approved coordinator plan makes
native cold reads first-class and removes this repeated loop after the Shared
task can prove the empty result directly.

## Decision
Amend only Decision 0051's one-round floor after
`SHARED-COORDINATOR-JOURNEY` ships. A successful ledgered cold-read result may
record zero human rounds only when it is bound to the exact artifact/gate/task
input, explicitly reports an empty human frontier, and every repository-owned
finding is resolved in the recorded result. Any human question, missing
authority, contradiction, failed or incomplete read still uses the existing
ledger-matched question and single-use rules.

Before Shared ships, every incumbent floor remains unchanged. No old grill is
rewritten or reclassified.

## Consequences
Shared updates the one gate-table row/predicate and recorder schema rather than
adding a bypass command or synthetic question. The same cold-read launch and
input digests remain mandatory. `frontier_empty` becomes cold-reader evidence
when rounds are empty and remains the final human-round assertion otherwise.
All other Decision 0051 requirements remain active, including one gate table,
ledger matching, no round reuse, and exact artifact freshness.
