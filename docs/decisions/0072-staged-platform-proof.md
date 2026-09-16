---
status: accepted
confirmed_by: "User (all plans approved, Codex conversation 2026-09-12)"
date: 2026-09-12
stories: [FORGE-COORD-1]
---

# Stage platform proof at the task that installs its CI

## Context
Decision 0065 requires Ubuntu and native Windows CI results before each normal
review, readiness, marker, shipping, and closeout. The approved eight-task graph
puts the workflow and pinned CI implementation in `QUALITY-BASELINE`, after six
predecessor tasks. Applying 0065 literally would require those predecessors to
consume CI jobs that do not exist yet, so the graph cannot start. Quality's new
jobs also require a pull request before their first results can exist.

## Decision
Amend only Decision 0065's delivery timing for FORGE-COORD-1. Tasks before
`QUALITY-BASELINE` close with their declared local deterministic proof, real
macOS evidence where applicable, independent review, and green incumbent CI;
they record unavailable new Ubuntu/Windows coverage as a scheduled gap rather
than fabricate it. Quality installs the pinned jobs and may open one early draft
PR through the existing Git/GitHub route solely to obtain those results. The
draft grants no proof, review, readiness, seal, or merge authority. After the
new required jobs pass, Quality completes formal review and the ordinary
`forge task close` path against that same PR.

`FORGE-COORD-1.1` and story closeout require the new Ubuntu and Windows results,
the mandatory local Mac CLI/Desktop observations, and client/dogfood proof on
the final Quality-or-later harness revision. An actual failure remains blocking.

## Consequences
This removes an impossible dependency cycle without weakening final parity.
The early draft is idempotent CI transport: Main pushes the Quality branch,
creates or reuses exactly its matching draft PR, records the PR identity, waits
for required checks, and never merges before normal proof/review/closeout.
Earlier task proof does not claim the later platform coverage. All other
Decision 0065 evidence labels, exact logs, limitation rules, pinned real CLI
smoke, and no-fabrication requirements remain active.
