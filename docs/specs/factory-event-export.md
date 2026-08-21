---
slug: factory-event-export
title: Factory event export: the committed ledger becomes a measurable, shareable record
status: confirmed
saved: 2026-08-21T05:55:05+00:00
---

# Factory event export: the committed ledger becomes a measurable, shareable record

> Captured 2026-08-19 from the cadence integration design session; revised the
> same day after a read-only gpt-5.6-sol@xhigh validation run (verdict: stop
> the write-through design, keep the direction). Cadence — a separate,
> optional cloud app — wants to measure delivery health and developer
> judgement from forge's recorded evidence. Forge already writes one JSON file
> per transition under `.factory/events/` (decision 0022) and `forge history`
> reads them; the ledger lacks stable ids, typed numbers, and a consumer-safe
> projection. Forge stays cloud-free and client-independent: no network, no
> cadence dependency, no new per-machine ledgers.

## Why

- Events carry `event, generated_by, at, story, detail`; the only id is the
  file name; `detail` is prose. Counts a consumer needs — diff measured at
  `stage done`, verify duration, tests run/failed, review blocking counts,
  signal time-to-resolve, attempt numbers — live in artifacts, in prose, or
  nowhere (verify has no timing; tests and reviews have no numeric fields;
  signal resolution records no elapsed time or resolver kind).
- Events are best-effort by design (decision 0017 accepts loss; `append_event`
  swallows write failures). A consumer must be told coverage, not promised
  completeness.
- A shared per-machine write-through file would recreate the many-writers
  problem 0022 removed (parallel story worktrees, rotation races, Windows
  sharing) and would capture events from branches that never merge.
- Vendored-harness integrity already exists (`constitution/VENDOR_MANIFEST.json`,
  `check_vendor_integrity.py`, decision 0009); the export must reuse it, not
  add a second manifest.
- Nothing separates facts that may leave the machine from text that must not.

## Behaviour

- **Stable event identity.** Every event payload carries `id` (the file's
  uuid, so filename and content agree), optional `task`, `signal_id`,
  `attempt`, and a `data` object. The event schema is discriminated per
  event kind: `data` keys are declared per kind with constrained scalar
  types (`nonnegative_number`, `boolean`, `sha256`, `opaque_id`,
  `safe_token`, closed enums); unknown keys and free strings fail. The
  validator is extended to enforce nested, closed objects (today it is
  shallow and allows extra keys).
- **Numbers come from their sources.** Artifact schemas gain the fields the
  events project: verify duration and check counts; tests run/failed (numeric);
  review blocking/non-blocking counts per lens; signal resolution elapsed
  seconds and resolver `auto|human`; stage close persists its measured diff
  (product files, product lines changed, total lines changed) and an
  `attempt`; plan save carries `attempt` (n-th save for the story — a second
  save after a grill is a revision) and result `approved|awaiting`; grill
  records require `rounds` and `questions_asked`. Only metrics consumed by a
  named view are added.
- **Missing transitions consumed by named metrics emit events:**
  `grill-recorded` (gate, rounds, questions, verdict), `plan-saved`
  (attempt, result), `outcome-set`, `decision-accepted`. Quickfix, degraded,
  lessons and signals already have structured per-record ledgers; the
  exporter projects those records — they are not duplicated into the global
  ledger.
- **Read-only exporter over a committed ref.** `forge events export
  --ref <ref> [--since <iso>] [--no-titles] --out <path>` writes
  `factory-export/v1` NDJSON from records reachable at that ref only. Two
  record kinds: `event` (facts: `source_event_id`, `ref`, `story`, `task`,
  `signal_id`, `attempt`, `event`, `at`, `generated_by` role, `data`) and
  `roadmap` (projection: epic id, story key, status, dependencies, PR link,
  and titles unless `--no-titles`). Header record: `schema: 1`,
  `harness_commit` and `integrity_status: clean|drifted|unarmed` from
  `VENDOR_MANIFEST.json` / `check_vendor_integrity`, and `coverage`
  (events read, malformed skipped, records without story). `detail` and every
  prose field other than roadmap titles are dropped. No repo hash, no actor
  hash, no per-machine file, no rotation, no backfill marker: the consumer
  attaches project and authenticated subject identity and upserts by
  `(project, source_event_id)`; re-export is harmless. Output is one success
  line; drift and coverage details are findings (terse-output).
- **Metric definitions, fixed here:** *factory cycle time* = intake →
  `shipped` (PR-ready; merge lead time is the consumer's join to GitHub);
  *right first time* = a shipped story whose stage closes, verify, reviews
  and plan save all have `attempt == 1` and no `stage-incomplete`; both
  reported with coverage. *Runs:* the exporter groups a story's events into
  runs at each `intake`; metrics use the run that ends in `shipped`, earlier
  runs are exported with `run_status: abandoned`, and the restart count is
  itself a fact.
- **Decision before code.** `export-privacy-boundary` is drafted now and must
  be *accepted* by a human before LED-1 is planned. It states: committed
  `.factory/events/` and structured ledgers are the authoritative record and
  the export is a derived, re-runnable projection; counts, ids, hashes,
  timestamps, enums, roadmap structure and (by default) story/epic/decision
  titles may leave the machine; repo names, branches, paths, prompts,
  transcripts, `detail`, and outcome/signal/grill/lesson text may not;
  identity is the consumer's; events are best-effort and every metric carries
  coverage. Collection policy is also the consumer's: on company devices
  collection defaults on at the tier the repo supports (usage → delivery →
  factory); repos under a third-party NDA are marked `client-restricted`
  (usage cost/hours only — an obligation to the client, not the employee);
  personal/OSS work aggregates into an "other work" bucket; metrics are never
  compared across coverage tiers. Forge's part is only to produce the export
  when asked.
- **Out of scope:** a local judge emitting verdict events (later spec); the
  cadence-side collector, identity, upsert and views; repo classification,
  coverage tiers, collection defaults, and retention (consumer's decision
  record mirrors the boundary above).

## Acceptance criteria

- Every event file written by any recorder carries `id` equal to its file
  name; a recorder test placing an undeclared key or free string in `data`
  fails; the gate-test lifecycle (happy path) plus focused alternate scenarios
  (quickfix, degraded, review rework, plan revision) each produce their
  declared events and data keys.
- `forge events export --ref HEAD` on the harness repo validates against
  `factory/schemas/factory-export.json`; a grep for `detail`, any path,
  branch name, or prose fixture other than roadmap titles finds nothing;
  `--no-titles` removes titles; running it twice yields identical output.
- The header's `integrity_status` flips to `drifted` when one vendored gate
  file is edited, using the existing vendor-integrity check (no new manifest).
- The export of the last 20 shipped stories in this repo reports coverage
  and joins each story to its PR link; the pilot report (LED-0) is committed
  under `docs/memory/` before LED-1 is planned.
- `forge upgrade` carries schema and exporter to a client repo;
  `check_dual_runtime.py` and `check_vendor_integrity.py` stay green.
