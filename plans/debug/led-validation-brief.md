# Read-only plan validation: factory-event-export (forge → cadence)

You are validating an approach, not implementing it. Read the repo; do not write.
Return a structured verdict: (1) what is sound, (2) what is wrong or risky, ranked,
(3) what is missing, (4) simplifications you would make, (5) go / revise / stop.
Be blunt. Cite files and lines. Under ~150 lines.

## Vision

KnackLabs builds client apps with coding agents. Two products:

- **symphony-forge** (this repo) — the in-repo harness. Humans plan, specify,
  grill and judge; Codex writes code via `./forge delegate`. Every transition
  is recorded as schema-validated evidence under `.factory/` (events, grills,
  decomposition, stages, verify, tests, reviews, outcome, signals, lessons).
  Forge must stay cloud-free and client-independent.
- **cadence** (separate repo at ~/Workdir/cadence — read-only context if you
  want it) — a CLI + Cloudflare Workers/D1 app, optional on any developer
  machine, collecting counts-only telemetry (Claude/Codex usage, GitHub PR
  outcomes, monthly pulse, Academy grades) and showing team-level views.
  Rules: no per-developer views except self-view; no code, prompts, or chat
  ever leave a machine.

Goal: cadence becomes the read side of the factory. Forge emits *facts*;
cadence measures delivery health (leadership), roadmap progress and blockers
(PM), and the developer's own judgement/spec-writing signals (dev self-view).
Forge must never depend on cadence; cadence must never depend on forge being
present (non-forge repos show "delivery only" from GitHub).

## What exists today in forge (verify these claims)

- `factory/scripts/forge_cli/events.py`: `append_event(base, event, actor,
  story="", detail="")` writes one JSON file per event under
  `.factory/events/` (decision 0022 pattern). ~24 emitting call sites
  (stage-start/done/incomplete, delegated, verify-passed/failed, tests-*,
  review-*, signal-*, signal-resolved, decomposed, intake, plan-approved,
  shipped, spec-draft/confirmed, roadmap-*...). `forge history` reads them.
- Events carry only `event, generated_by, at, story, detail`; `detail` is prose.
- Some transitions emit nothing: grill recorded, outcome set, quickfix
  start/done, degraded start/end, lesson added, assumption recorded,
  decision accepted, plan rejected.
- `stage done` measures the diff but (claim) does not persist the numbers in
  the event.
- Harness is vendored into client repos as plain files (`forge init/adopt/
  upgrade`); `.factory/harness-source.json` names the source; nothing detects
  local modification of vendored files.
- `.factory/` is committed; story artifacts contain prose.

## The approach (confirmed spec: docs/specs/factory-event-export.md — read it)

1. `append_event` gains optional `task` and a `data` object; `data` keys are
   declared per event in the event schema, typed number | boolean | closed
   enum; any free string in `data` fails validation.
2. Existing emitters carry counts (stage-done: product-only and total
   files/+/− triples; verify: checks/duration; tests: run/failed; review:
   findings by severity; delegated: model/effort/write; signal kind;
   signal-resolved: elapsed seconds, resolver auto|human).
3. Missing transitions emit events (grill-recorded incl. gate/rounds/
   questions/verdict/input digest; plan-saved incl. digest so "grill changed
   the plan" = digest mismatch; outcome-set; quickfix-*; degraded-*;
   lesson-added; assumption-recorded; decision-accepted; plan-rejected).
4. Write-through export: every `append_event` also appends one
   `factory-export/v1` line to a per-machine, never-committed file
   `~/.local/state/forge/export/<repo-hash>.jsonl` (XDG; Windows equivalent).
   Fields: schema, repo (sha256 origin URL), harness_sha, modified, story,
   task, event, at, generated_by, actor_hash (sha256 git email), data. No
   detail/prose. Rotate at 10 MB keep 3. Write failure never fails the
   recorder. `forge events export` repairs/re-derives and does a one-time
   backfill flagged `backfilled: true`, idempotent by event file name.
   Schema checked in at `factory/schemas/factory-export.json`; CI validates
   a fixture.
5. Vendored-file manifest `.factory/harness-manifest.json` (path→sha256)
   written by init/adopt/upgrade; `forge doctor` reports locally modified
   files; export lines carry `modified: true`. Visibility only.
6. Decision `export-privacy-boundary`: committed `.factory/events/` is
   authoritative, export is a derived feed a consumer may verify against git;
   counts/ids/hashes/timestamps/enums and story/decision TITLES may leave the
   machine; repo names, branches, paths, prompts, transcripts,
   outcome/signal/grill/lesson text may not.
7. Out of scope: a local judge that grades text-bound signals and emits
   verdict events (later spec); the cadence-side collector/views.

Roadmap (plans/roadmap.json, epic `measurable-ledger`): FORGE-LED-1 decision +
schema; LED-2 counts on existing emitters; LED-3 missing transitions; LED-4
write-through export + backfill; LED-5 manifest + upgrade carry. LED-2 and
LED-3 parallel after LED-1.

## What cadence will compute from it (context only)

Leadership: stories delivered, lead time p50/p75 (intake→shipped),
right-first-time (no stage-incomplete / verify-failed / review redo /
plan-rejected), reverts (GitHub), Claude spend per story, per-project health
by rule (question open >3d = stuck; lead time +25% or any revert = slowing),
signals by kind per week, pulse vs measured. PM: epics→stories with gate
squares, open questions count+age, scope changes, decisions accepted,
changed-this-week. Dev self-view: tasks finished, right-first-time, redo
causes, signals by kind, own spend, reverted PR → local trace. Epic id +
titles therefore must be in the export (roadmap-add/shipped events).

## Questions to answer specifically

1. Is "write-through from append_event" the right trigger, or should export
   be a separate derived step (collector reads committed events)? Consider
   worktrees, merges, events recorded on a branch that never merges,
   duplicate event files after `roadmap heal`, idempotency.
2. Is a per-event closed-enum `data` schema maintainable across ~35 event
   kinds, or should `data` be a small fixed envelope (counts, duration_s,
   kind, model, effort, result) shared by all events?
3. Is sha256(origin URL) a stable repo id (https vs ssh remotes, renames,
   forks, multiple remotes)? Is sha256(git email) acceptable given cadence
   already holds the email? Salt or not?
4. Does `modified` via a sha manifest give real signal, given `forge upgrade`
   rewrites files and devs legitimately patch vendored hooks? Cheaper
   alternative?
5. Conflicts with active decisions or specs (`./forge decision list
   --active`, docs/specs/conflict-free-story-state.md,
   harness-owned-vendoring.md, terse-output.md, strict-role-split.md)?
6. Can right-first-time and lead time be computed unambiguously from the
   listed events? Name the missing event or field if not.
7. Story split: is LED-1..5 the smallest correct sequence? Merge, reorder,
   cut? Is there a simpler shape that gets cadence the same numbers with less
   machinery?
8. Privacy: any proposed export field that is actually prose or
   re-identifying (titles, `generated_by` values, task ids embedding slugs)?
9. Failure modes: disk full, XDG path unwritable, Windows, concurrent
   appends from parallel story worktrees, rotation races, backfill replays.
10. What would you measure first to know whether this direction is worth it,
    before building LED-2..5?
