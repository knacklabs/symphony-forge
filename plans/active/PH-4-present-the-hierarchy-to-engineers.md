---
issue: PH-4
title: Present the hierarchy to engineers
status: approved
saved: 2026-08-05T15:26:27+00:00
story: PH-4
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
---


# PH-4 — Present the hierarchy to engineers

## Problem

The board shows lifecycle state but not the project. An engineer joining
mid-flight cannot answer, from the screen, what the product is, what each epic
delivers, which stories can start right now in parallel, why another story is
blocked, or which task is active. They open `plans/roadmap.json` instead —
exactly the artifact-reading the board exists to replace.

The answers already exist and are already derived. `ready_pending()`
(`roadmap.py:267`) returns pending stories whose dependencies are all `done`;
`aggregate_state()` (`board.py:169`) turns those keys into `frontier` and sets
`ready_to_plan`; `blocked_by` (`board.py:190`) is every `depends_on` key not yet
`done`. Decision 0021 already establishes `depends_on` as the only authored
edge, with everything else derived.

Four concrete gaps stand between that and the story:

1. **Project identity is absent from the API.** `/api/state` carries `root` — an
   absolute filesystem path — and no project object. Nothing on screen says what
   this project is or who it serves, though `docs/product/BRIEF.md` now has
   guaranteed headings because PH-1 made `record_signoff.py` refuse without them.
2. **Epic relationships are not derived.** State ships the raw `epics` array and
   each story keeps its `epic` id, but nothing derives what an epic delivers,
   which stories belong to it, or how epics gate each other. The UI resolves lane
   titles by lookup and can say nothing more.
3. **Blocked is not described as blocked where it matters.** Card marks read
   `waits on …` and drawer state says `blocked`, but the header progress bar
   merges blocked and waiting into one total labelled `waiting`
   (`index.html:802`). The API reports blocked; the most-read part of the screen
   does not.
4. **Nothing is labelled and nothing is bundled.** Epics render as lanes with no
   `EPIC` label, story cards carry no `STORY` label, task rows no `TASK` label,
   and the drawer opens with a bare `Story` eyebrow rather than a
   `Project › Epic › Story` breadcrumb. There is no bundled example project:
   today's board tests build a temp repo with `forge init` and hand-seed state,
   so nothing proves the page reads correctly against a realistic project.

PH-1, PH-2 and PH-3 closed the capture side that made projection unsafe. The
reading layer can finally be built against content guaranteed to be there.

## Scope / Non-goals

In scope: the API carries project identity and derived epic relationships; the
default view answers the four questions; every node is labelled; the drawer
opens with a breadcrumb; blocked reads as blocked on every surface; a bundled
example proves it against the production validators at three widths.

Out of scope, deliberately:

- **No mutating route, ever.** The board stays a reading layer over committed
  artifacts (spec Boundaries; decision 0017). Already true and already tested
  (`test_gates.py:3802` asserts the three handler names are absent); this story
  keeps and extends that guarantee rather than re-earning it.
- **No wave or layer numbering, and no node-and-arrow graph.** The spec rejects
  both: a wave number needs a caveat on every screen explaining it is not
  actually the order. The frontier plus per-story requires/unblocks is the
  dependency presentation, because it stays true as stories ship.
- **No dates, estimates, burndown or velocity.**
- **No new dependency, UI framework or build step.** One self-contained HTML
  file with inline CSS/JS, served by the stdlib `ThreadingHTTPServer`.
- **Leverage stays in the UI.** It is computed client-side today
  (`index.html:686`). Moving it server-side would be tidier and serves no
  acceptance criterion, so it is cut — the planner's simplicity rule applies to
  plans, not just code.
- **No per-story resolved epic object on `/api/state`.** Stories keep their
  `epic` id and state keeps its `epics` array; the UI already resolves lane
  titles from exactly those two. Copying a resolved epic onto every story would
  add a second representation of the same fact to the payload. Only
  `/api/story/<key>` gets the resolved object, because a story-detail response
  has no `epics` array of its own to resolve against.
- **No capture-side changes.** PH-1/2/3 shipped those gates.
- **`root` is not removed from `/api/state`.** Adding `project` alongside it is
  additive; removing a field the UI already reads is gratuitous breakage.

## Acceptance Criteria

Verbatim from the roadmap story, each with the proof that closes it:

1. **Every epic, story and task on screen is explicitly labelled as such, and the
   drawer opens with a `Project › Epic › Story` breadcrumb.** Proof: a test
   asserts the `EPIC`/`STORY`/`TASK` label markup and the breadcrumb render for a
   story with a known epic.
2. **`/api/state` and `/api/story/<key>` carry project identity, epic membership
   and derived relationships, and no mutating route exists.** Proof: API-shape
   tests over a live board — `project` with brief sections, epic membership and
   derived epic gating, per-story reverse `unblocks` — plus the existing
   no-mutating-handler assertion, extended to cover any route added here.
3. **The default view answers what the project is, what can start now, what each
   epic delivers, and why a story is blocked.** Proof: the Overview is the
   default view, and a test asserts each of the four answers renders from
   `/api/state`. "How many worktrees" is `len(frontier)` under decision 0002 —
   one story per worktree — not a separate computation.
4. **Blocked stories are described as blocked wherever the API reports blocked.**
   Proof: "wherever" is a closed list — header progress totals, card mark, card
   ARIA label, and drawer state — and a test asserts a blocked story reads as
   blocked on each, with the header no longer folding blocked into `waiting`.
5. **The bundled example passes the production validators and reads correctly at
   desktop, tablet and mobile widths.** Proof: a test runs the *production*
   brief/spec/roadmap validators against the bundled example and asserts the
   width rules; the human-visible half is the phase-7 functional check.

## Technical Approach

**API (`board.py`).** Two additions to `aggregate_state()`, both derived at read
time from committed artifacts, neither stored:

- `project`: name plus the BRIEF sections PH-1 made mandatory, parsed with
  `parse_sections()` (`factory_lib.py:317`) — described there as "the single
  answer to does this document have this section, with content". The required
  heading list is currently duplicated verbatim as `REQUIRED_BRIEF_HEADINGS`
  (`record_signoff.py:25`) and `BRIEF_REQUIRED_HEADINGS` (`doctor.py:31`). The
  spec requires one parser precisely so the gate and the board can never
  disagree, so this story consolidates those two into a single owner and consumes
  it from all three sites rather than adding a third copy.
- derived epic relationships: per-epic story membership and progress, and
  epic-to-epic gating computed from the existing story edges. Decision 0021
  forbids authoring a second graph; this derives from the authored one and reuses
  `roadmap.py`'s existing helpers rather than reimplementing them.

Per-story reverse `unblocks` — the inverse of the authored `depends_on` — is
added alongside the existing `blocked_by`. `/api/story/<key>` gains `project` and
the resolved `epic` object so a drawer renders its breadcrumb from one response.

**UI (`index.html`).** The Overview becomes the default view and the existing
lifecycle board becomes the second view — the spec's own wording, keeping every
current affordance rather than replacing it. Overview answers the four questions
in the spec's order: what this project is, what can start now and in how many
worktrees, what each epic delivers, and where each story sits with what it
requires and unblocks. Labels and the breadcrumb are markup additions. The
blocked fix stops merging blocked into `waiting` in the header totals and names
it.

**Bundled example.** A minimal repo-shaped tree — `docs/product/BRIEF.md`, one
confirmed spec, and a `plans/roadmap.json` with two epics, one blocked story and
at least two startable — served by the flag that already exists:
`./forge board --repo <example>`. That makes it a genuinely demonstrable example
rather than test data, and a test drives the production validators over it.

**Rejected, and why:** moving leverage server-side (tidier, serves no criterion);
resolved epic objects on every state story (a second representation of a fact the
payload already carries); a headless-browser responsive test (a new dependency
the spec forbids); a `project.json` cache (a second source of truth for something
derivable per request, contradicting 0017 and 0021).

## Decisions

Two choices are not derivable from the BRIEF, the architecture docs, or an
existing record. Both must exist as accepted records before the decomposition is
recorded:

- `docs/decisions/0026-bundled-example-validated-by-production-validators.md` —
  the example is checked-in source, not a test fixture and not generated at test
  time. A fixture drifts from the gates it demonstrates; a generated example
  proves the generator, not the page. Checked-in source the production validators
  must accept is the only form that fails when the contract changes.
- `docs/decisions/0027-responsive-proof-without-a-browser.md` — "reads correctly
  at three widths" is proven in two halves: deterministic structural assertions
  in CI (breakpoints exist; each width's required content is present and not
  clipped), and the phase-7 functional check for whether it actually reads well.
  A headless browser is a dependency the spec forbids, and screenshot diffing is
  not deterministic across machines.

**Reconciliation against the active corpus.** Binding: 0021 (only `depends_on` is
authored — everything here derives), 0017 (the repo is the system of record — the
board reads committed artifacts and stores nothing), 0002 (worktree count is
`len(frontier)`), 0011 (one autoreview pass, three lenses), 0018 (stage close
needs a bound launch), 0007 (tasks execute as stages), 0005 (tripwire below),
0013 (this plan releases the lock), 0015 (this reconciliation satisfies it).
Checked and not engaged: 0001, 0003, 0006, 0008, 0010, 0012, 0014, 0016, 0022,
0023, 0025 — none governs a read-only presentation layer, and 0025 explicitly
leaves the history archive the board reads committed and unchanged. 0009 is
inert here: `check_vendor_integrity` reports the manifest unarmed in the harness
(it arms in client repos at upgrade), so in-place board edits are not gated.

## Surface Impact

| Surface | Classification | Notes |
| --- | --- | --- |
| Runtime behavior | Changed | Overview becomes the default view; the lifecycle board becomes the second view. |
| API | Changed | `/api/state` gains `project`, derived epic relationships and per-story `unblocks`; `/api/story/<key>` gains `project` and its resolved `epic`. Purely additive: no field removed, no route added, none that writes. |
| Data/schema | Unchanged by design | Everything is derived per request from committed artifacts. Storing any of it would author a second graph (0021) and a second source of truth (0017). |
| CLI/ops | Unchanged by design | `forge board` keeps its flags, port default and localhost-only bind. `--repo` already exists and is what serves the example; this story changes what the page shows, not how it is launched. |
| UI | Changed | Overview view, `EPIC`/`STORY`/`TASK` labels, `Project › Epic › Story` breadcrumb, blocked named in the header totals, three-width behavior. |
| Docs | Changed | `docs/getting-started.md:189` and `factory/skills/forge.md` describe `forge board`; both gain the Overview default and the `--repo <example>` invocation. There is no board README to update. |
| Tests | Changed | API shape, no-mutating-route (extended), labels + breadcrumb, blocked on all four surfaces, example against production validators, width rules. |

## Task Decomposition

Four sequential tasks in one story worktree (0002). Each traces to at least one
acceptance criterion; write scopes are disjoint except that tasks 2 and 3 both
touch `index.html`, which is safe because tasks are strictly sequential (0018).

1. **API carries the hierarchy** → AC2 (and supplies AC1/AC3 their data).
   Write scope: `factory/scripts/forge_cli/board.py`,
   `factory/scripts/record_signoff.py`, `factory/scripts/forge_cli/doctor.py`,
   `factory/tests/test_gates.py`. Adds `project` via the shared parser,
   consolidates the duplicated heading constant to one owner, derives epic
   relationships and per-story `unblocks`, and extends the no-mutating-route test.
2. **Overview becomes the default view** → AC3.
   Write scope: `factory/board/index.html`, `factory/tests/test_gates.py`.
   The four answers, in the spec's order, rendered from `/api/state`.
3. **Labels, breadcrumb, and blocked named everywhere** → AC1, AC4.
   Write scope: `factory/board/index.html`, `factory/tests/test_gates.py`.
   `EPIC`/`STORY`/`TASK` labels, the drawer breadcrumb, and the header total
   split so blocked is never folded into `waiting`.
4. **Bundled example, production-validated, at three widths** → AC5.
   Write scope: the example tree, `factory/tests/test_gates.py`,
   `docs/getting-started.md`, `factory/skills/forge.md`.
   Example brief + confirmed spec + roadmap (two epics, one blocked story, two
   startable); a test drives the production validators over it and asserts the
   width rules.

`user_facing: true` — phase 7's functional check is required.

## Risks

- **Rendering blanks and calling it a hierarchy.** The spec names this failure
  directly. Mitigation: the bundled example is validated by the *production*
  validators, so a field the capture gates would refuse cannot reach the screen
  as an empty box.
- **A third copy of the heading list.** The list is already duplicated twice; the
  spec's whole point is that the gate and the board cannot disagree. Mitigation:
  task 1 consolidates to one owner instead of adding a copy.
- **A second ordering creeping in.** Any "phase 1 / phase 2" affordance is a wave
  by another name and contradicts 0021 and the spec's Boundaries. Mitigation:
  explicit non-goal; named grill target.
- **Responsive claims that are never proven.** Mitigation: the second decision
  record fixes what deterministic proof means here; the functional check covers
  the rest.
- **The example rotting.** A checked-in example nothing exercises becomes stale
  documentation. Mitigation: the production validators run over it in CI, so a
  contract change breaks the build rather than the demo.
- **Scope drift into a redesign.** The board already works; this story adds a
  view and labels. Mitigation: `root` stays, the lifecycle board stays, every
  current affordance stays.
- **Recurring-findings tripwire.** Both RECURRING classes (`reviewed-separately`,
  `repository-escape`) live in `upgrade.py`, a different area, so no
  consolidation is owed here. If review flags either class against board code,
  escalate per WORKFLOW.md Recurring Findings rather than patching a fourth time.

## Verify Plan

Deterministic, and the same commands CI runs. `.envrc` now names them for this
repo (harness-only, guarded on `constitution/VENDORED_FROM`), so `verify.py`
resolves them without inline exports:

```bash
python3 factory/scripts/verify.py
```

which runs, in order:

1. `python3 factory/scripts/check_dual_runtime.py` (structural)
2. `python3 factory/scripts/check_factory_scaffold.py` (typecheck slot)
3. `uv run --with pytest python -m pytest factory/tests -q` (tests)

Each task's own verify command is a runnable pytest selection (`-k` over the
tests that task adds), recorded in the decomposition, so a stage cannot close on
a task whose tests do not run. What would falsify this work: an API response
missing `project` or `unblocks`; a blocked story reading `waiting` on any of the
four named surfaces; a served page without the Overview as default; the bundled
example failing a production validator. Each has a test. Review is one autoreview
pass, three lenses (0011). The functional check runs because `user_facing: true`.

## Implementation Assumptions

<!-- Made during implementation, NOT part of the approved plan. Dev: review these before merge; promote any that matter to docs/decisions/. -->
- 2026-08-05: Project name means the repository root directory name, matching the board's existing root identity because no separate authored project-name field is in scope.
