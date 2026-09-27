---
status: superseded
superseded_by: 0093-lean-forge-rebuild
confirmed_by: "Ravi"
date: 2026-07-21
stories: []
---

# Committed lessons ledger with schema-validated recording and pre-work relevance injection

## Context

The harness had a curation loop (skill-miner → proposed skills) but no
fast-path memory: a worker that hit the same failure twice, or absorbed an
accepted review finding, had nowhere durable to leave the lesson, so the
next task relearned it. The Gantry factory's `lessons.jsonl` +
`select_relevant_lessons` pair closes exactly this loop.

## Decision

Lessons live in committed `plans/lessons.jsonl` — one JSON object per line,
validated by `.agents/schemas/lesson.json` (topic, lesson, source,
`applies_to` path globs, severity, attested `generated_by`), recorded only
via `forge lesson add` (dedup on lesson text), merged across branches by the
jsonl-append driver. Before planning or implementation, workers run
`forge lesson relevant --files <write scope>` and honor matches; the
session-start hook surfaces the ledger count. The skill-miner curates at
retro cadence: recurring lessons promote into decisions/constitution, stale
ones retire, chronically-violated ones become hard gates.

## Consequences

- Repeated failures become one-time costs; the source field keeps every
  lesson falsifiable.
- The ledger is knowledge, not law — the constitution and decision records
  stay the contract; a lesson that deserves law status gets promoted, not
  enforced in place.
- Strict line parsing means merge artifacts fail loudly instead of silently
  dropping knowledge.
