---
slug: factory-event-export
title: The ledger is measurable — facts leave, prose stays
status: proposed
---

# The ledger is measurable — facts leave, prose stays

> Backfilled 2026-08-20 to satisfy the `measurable-ledger` epic's `source_refs`
> contract: the epic was queued on main (8ea57ad) referencing this spec, but the
> file was never committed, so `test_shipped_roadmap_satisfies_the_story_contract`
> failed on every PR. This captures the epic's committed objective in the spec
> shape; it is `proposed`, not human-confirmed — a maintainer should confirm and
> flesh out the inline open points via `forge spec confirm`.

## Why

The harness records a rich transition history (`.factory/history/`, signals,
stage and window events), but that record is prose- and path-bearing and stays
on the machine by design. There is today no structured, name-free feed a
delivery-health consumer could read: measuring cadence, throughput, or where the
loop stalls means either scraping prose (fragile, and it leaks paths and names)
or nothing at all. The epic's objective states the target directly: *every
transition is a structured event; a per-machine export feed lets an optional
consumer (cadence) measure delivery health and developer judgement without any
prose, path, or name leaving the machine.*

## Behaviour

- **Every lifecycle transition emits a structured event.** The events the loop
  already produces (intake, plan/approve, decomposition, stage start/done,
  verify, review, outcome, ship, window open/done) carry a stable, typed shape —
  event kind, the anchoring keys, and timestamps — not free text.
- **A per-machine export feed exposes those events to an optional consumer.**
  The feed is opt-in; nothing depends on a consumer existing, and the harness
  functions identically with none attached.
- **Nothing identifying leaves the machine.** The exported feed carries facts —
  counts, durations, event kinds, and opaque ids — and never prose, filesystem
  paths, branch or story titles, or human names. Redaction is a property of the
  exporter, enforced, not a caller convention.
- **The consumer named in the objective is `cadence`** — a measurement consumer
  of delivery health and developer judgement — kept out of the harness's own
  trust and control path.

<!-- OPEN (maintainer to confirm): the exact event schema and version contract,
     the feed's on-disk/transport form, and the redaction allow-list. These are
     not fixed by the epic objective and must not be invented here. -->

## Acceptance criteria

- Each transition the loop records also appears as a structured event with a
  typed, versioned shape — no consumer has to parse prose to read it.
- The export feed is opt-in and its absence changes no harness behaviour.
- The exported feed provably contains no prose, path, name, or title — only
  facts and opaque ids — and this is enforced by the exporter, not left to the
  caller.
- A delivery-health consumer can compute cadence and throughput from the feed
  alone, without reading any in-repo `.factory/` prose.

## Boundaries

- Per-machine only: the feed never aggregates across machines and never carries
  identifying content off the machine.
- The consumer (`cadence`) is out of scope here; this spec defines the feed and
  the event contract it reads, not the consumer.
- Inherits `project-record`'s stance: missing past events are marked, never
  fabricated; this spec adds forward emission, not backfilled history.
