---
issue: PH-5
title: The project knows what it built
status: approved
saved: 2026-08-06T04:13:57+00:00
story: PH-5
decisions_reviewed:
  - 0001-determinism-contract
  - 0002-concurrency-one-task-per-branch
  - 0003-model-tiers-terra-explore-sol-implement
  - 0005-recurring-findings-escalation
  - 0006-lessons-ledger
  - 0007-stage-commit-loop
  - 0008-loop-health-audit
  - 0009-frozen-gate-integrity
  - 0010-client-signoff
  - 0011-orchestrator-runs-autoreview
  - 0012-project-level-memory
  - 0013-always-armed-planning-lock
  - 0014-specs-before-signoff
  - 0015-plan-contradiction-gate
  - 0016-machinery-dir-rename
  - 0017-repo-as-system-of-record
  - 0018-delegation-gates
  - 0021-derived-ordering
  - 0022-conflict-free-ledgers
  - 0023-stage-delta-by-ref
  - 0025-evidence-lifetime-contract
  - 0026-bundled-example-validated-by-production-validators
  - 0027-responsive-proof-without-a-browser
---


# PH-5 — The project knows what it built

## Problem

A read-only audit measured what the in-repo record covers: the story spine is
good and covers roughly half the work. 30 of 188 substantive commits (22
touching product code) trace to nothing but a commit message; 30 of 36 merged
PRs are invisible in-repo; `quickfix.files` is empty in 29 of 29 real records
so the bounded escape hatch neither binds nor reports; two shipped stories
(FORGE-INIT-1, harness-v2-wedge) have `.factory/history/` archives but never
appeared on the roadmap and have no outcome; and `.factory/events.jsonl` holds
314 committed events across ~29 types with no reader that surfaces them.

The confirmed spec `docs/specs/project-record.md` is the design record; this
plan implements it. Exploration (Codex, read-only) confirmed the seams and
corrected three assumptions the plan now builds on:

- `load_events(base, story=None)` (`events.py:20`) filters only by story. A
  history reader must add type and date filtering rather than assume it exists.
- Event `event` values are open strings — `update_run.py` emits an
  unrestricted phase string (refusing only `pr-ready`). History discovers the
  types present; it must not hardcode a closed set.
- `--pr-url` already exists (`update_run.py:99`) and lands in `run.json`, but
  `pr_ready.py:332` reduces `run.json` to `{project, phase}` at ship, so a
  PR value stored there is destroyed at exactly the moment the story ships.
  This is why the spec's one home for the PR link is an EVENT, not run state.

## Scope / Non-goals

In scope: the five behaviours the confirmed spec names — `forge history` over
the committed events, quickfix windows recording touched files, the PR link as
an event, the init/adopt record-boundary marker, and marking the two
pre-contract stories.

Out of scope, deliberately:

- **No backfilled outcomes.** The two pre-contract stories are MARKED as
  predating the outcome gate, never given a reconstructed outcome — the spec's
  boundary, and the same honesty rule as the "record begins here" marker.
- **`roadmap.json` merge-hardening is named, not done.** It has lost items to
  merges twice; making it conflict-free the way 0022 made the ledgers is a
  separate decision (spec Boundaries), not smuggled in here.
- **No new database, service or index** (spec). The record stays files.
- **`forge history` never writes** (spec). It is a pure reader.
- **The board's cross-worktree view and task depth on cards are a different
  capability** — the board's view, not the record's completeness. Deferred
  material, not this story.
- **Decision 0025's brief-durability question is out of scope** — it is a
  capture question ("what was a worker told"), and the spec grill parked it as
  an open item rather than widening this story.

## Acceptance Criteria

Verbatim from the roadmap story, each with its proof:

1. `forge history` answers what happened for a story, event type, or date range
   from the committed events, and NAMES events with no story attribution rather
   than hiding them. Proof: tests over a seeded `events.jsonl` asserting each
   filter and that unattributed events appear in unfiltered output.
2. A quickfix window records every product file it touched — including inside
   an approved story, where claiming does not happen today — and the five-file
   budget still binds where the quickfix is the authorization. Proof: a test
   that writes through an ACTIVE story and asserts the window's `files` is
   populated; a second asserting the budget still refuses a sixth file on the
   unplanned path.
3. A merged PR is linked to the work it shipped by an event in
   `.factory/events.jsonl`, so the link survives a clone with no GitHub remote.
   Proof: a test emitting the link and reading it back via `forge history` with
   no remote configured.
4. `forge init` and `forge adopt` write a boundary marker naming the date, the
   commit, and the count of preceding commits; the board reports it instead of
   implying the record is complete. Proof: init into a repo with prior commits,
   assert the marker's count, assert the board surfaces it.
5. Every shipped story has an outcome or an explicit marker that it predates the
   outcome contract; no outcome is written after the fact. Proof: the two
   pre-contract stories appear in `plans/roadmap.json` carrying a
   `predates_outcome_contract` marker and no `outcome`, and a test asserts no
   done item is both unmarked and outcome-less.

## Technical Approach

**One recommendation per choice.**

**`forge history` (Task 1) — the keystone, lands first** because it is the
reader that makes every other gap visible. A new `forge_cli/history.py` reads
`.factory/events.jsonl` through an extended `load_events` that gains `event=`
(type) and `since=`/`until=` (date) filters alongside the existing `story=`.
Types are discovered from the data, never hardcoded. Output groups by story and
prints an explicit "unattributed" section for events with no `story`, so a gap
is shown rather than filtered away. Wired into `forge.py` as a `history`
subparser. Stdlib only.

**Quickfix records touched files (Task 2)** at the one choke point every
product write passes, `guard_product_writes` (`pre_tool_use.py:221`). When a
quickfix window is open, the classified product paths are RECORDED against it
before the approved-plan early return — recording is passive and authorizes
nothing. `claim_files` (the five-file BUDGET) stays exactly where it is, on the
path where the quickfix is the sole authorization. This is the spec's explicit
separation of recording from bounding: a window opened during an active story
now says what it touched, while a task's write scope keeps bounding story work
and no second budget fights it. The planning lock is unchanged — no new
authorization path, only a new record.

**PR link as an event (Task 3).** `pr_ready` cannot know a PR number (merge is
external), so a small `forge pr-link <PR>` (or `forge history --link-pr`)
appends a `pr-linked` event carrying the issue key and PR reference. The event
ledger is the spec's one home: cumulative, committed, union-merged, never
pruned, already spanning stories, so the link survives a clone with no remote
and `forge history` surfaces it with no second reader.

**Record-boundary marker (Task 4).** A dedicated committed file
`.factory/record-origin.json` — NOT `run.json`, because `pr_ready` reduces that
to `{project, phase}` and would erase a marker stored there at first ship.
Written once by `forge init` and `forge adopt` (create-if-absent, so a
re-adopt never rewrites history): `{date, commit, preceding_commits}`. The
board reads it and reports "record begins here; N commits precede it". This
file is durable record under 0025, joining the committed set.

**The two pre-contract stories (Task 4, same slice).** Added to
`plans/roadmap.json` as `done` items carrying `predates_outcome_contract: true`
and no `outcome`, reconstructing only what committed evidence already states
(their history archives and PRs) — key, title, status — never a synthesised
outcome. The roadmap item schema permits additional fields, so the marker needs
no schema change. The guard against a future silent gap goes in `forge doctor`
as a REPORT, not in `load_roadmap` — validating at load would refuse a legacy
roadmap, the explicit lesson from PH-2 (validate where content is authored,
never at load). `pr_ready` already requires an outcome to ship, so a new story
cannot become outcome-less; doctor names any done item that is both unmarked
and outcome-less for the historical case.

**Rejected:** storing the PR link or the boundary marker in `run.json` (erased
at ship — the map proved it); a closed event-type enum in `forge history` (the
emitters use open strings, so an enum would hide new types); backfilling the two
stories' outcomes (fabrication the spec forbids); a `forge history` write mode
(the spec makes it a pure reader).

## Decisions

No new decisions. Every choice here is derivable from the confirmed spec
`docs/specs/project-record.md` (one home for the PR link, recording separated
from budgeting, mark-don't-backfill, the boundary-marker shape) or from an
existing record: 0017 (the repo is the system of record — the marker and the
PR link are committed artifacts), 0022 (the event ledger is conflict-free, which
is why it is the PR link's home), 0025 (the boundary file is durable record),
0013 (the recording change must not weaken the always-armed lock — it adds a
record, not an authorization). The storage-location choice (dedicated file over
`run.json`) is forced by `pr_ready`'s projection, not a product decision.

## Surface Impact

| Surface | Classification | Notes |
| --- | --- | --- |
| Runtime behavior | Changed | New `forge history` reader; quickfix windows now record touched files; init/adopt write a boundary marker. |
| API | N-A | No HTTP surface; the board's read of the marker is covered under UI. |
| Data/schema | Changed | New committed `.factory/record-origin.json`; `pr-linked` event type; `predates_outcome_contract` roadmap field (schema already permits additional fields — no schema edit). |
| CLI/ops | Changed | `forge history` added; `forge pr-link` added; `forge init`/`forge adopt` gain the marker write. |
| UI | Changed | The board reports the record boundary. Read-only, no mutating route (unchanged). |
| Docs | Changed | `docs/getting-started.md` and `factory/skills/forge.md` gain `forge history` and the boundary concept. |
| Tests | Changed | history filters + unattributed events; quickfix recording through an active story; PR link round-trip with no remote; marker count; the no-unmarked-outcome-less-done-item check. |

## Task Decomposition

Four sequential tasks in one worktree (0002), each tracing to criteria:

1. **`forge history` reads the committed events** → AC1. Scope:
   `factory/scripts/forge_cli/events.py`, `factory/scripts/forge_cli/history.py`
   (new), `factory/scripts/forge.py`, `factory/tests/test_gates.py`.
2. **Quickfix windows record what they touched** → AC2. Scope:
   `factory/scripts/pre_tool_use.py`, `factory/scripts/forge_cli/quickfix.py`,
   `factory/tests/test_gates.py`.
3. **The PR link is an event** → AC3. Scope:
   `factory/scripts/forge_cli/history.py` (or a small `pr_link.py`),
   `factory/scripts/forge.py`, `factory/tests/test_gates.py`.
4. **The record states where it begins, and no shipped story is silently
   outcome-less** → AC4, AC5. Scope:
   `factory/scripts/forge_cli/scaffold.py`,
   `factory/scripts/forge_cli/adopt.py`, `factory/scripts/forge_cli/board.py`,
   `plans/roadmap.json`, `factory/scripts/forge_cli/doctor.py` (the
   unmarked-outcome-less REPORT, not a load-time gate), `docs/getting-started.md`,
   `factory/skills/forge.md`, `factory/tests/test_gates.py`.

`user_facing: true` — the board change (Task 4) surfaces the boundary to a
reader, so the functional check runs.

## Risks

- **Touching the planning-lock hook.** Task 2 edits `pre_tool_use.py`, the
  always-armed lock (0013). Mitigation: recording is append-only and authorizes
  nothing; the budget and every deny path are unchanged; a test asserts the lock
  still refuses an unbudgeted write. If review reads the recording path as an
  authorization path, that is a blocking finding, not a nitpick.
- **A marker that lies after a merge.** `record-origin.json` is create-if-absent
  so a re-adopt cannot rewrite the origin; a test asserts a second adopt leaves
  it untouched.
- **Fabrication creeping into the backfill.** The two stories get key/title/
  status from evidence and a `predates` marker — never an outcome. A test
  asserts no done item is both unmarked and outcome-less, which also prevents a
  future story from shipping outcome-less.
- **Recurring-findings tripwire.** Both RECURRING classes (`reviewed-separately`,
  `repository-escape`) live in `upgrade.py`, a different area, so no
  consolidation is owed. If review flags either against PH-5 code, escalate per
  WORKFLOW.md Recurring Findings rather than patching a fourth time.

## Verify Plan

Deterministic, the same commands CI runs; `.envrc` names them (harness-only,
guarded on `constitution/VENDORED_FROM`):

```bash
python3 factory/scripts/verify.py
```

running structural (`check_dual_runtime.py`), typecheck slot
(`check_factory_scaffold.py`), and tests (`pytest factory/tests -q`). Per-task
verify commands are runnable pytest selections recorded in the decomposition.
What falsifies this work: `forge history` that hides an unattributed event; a
quickfix through an active story whose `files` stays empty; a PR link
unreadable after a clone with no remote; a boundary marker whose count is wrong;
a done item both unmarked and outcome-less. Each has a test. Review is one
autoreview pass, three lenses (0011); the functional check runs
(`user_facing: true`).
