---
issue: FORGE-BOARD-2
title: JIT task planning: per-task plan+grill against real prior state
status: approved
saved: 2026-08-08T05:24:17+00:00
story: FORGE-BOARD-2
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
  - 0028-path-boundary-invariant
  - 0029-plan-approval-in-plan-mode
  - 0030-harness-source-is-product-in-its-own-repo
  - 0031-workflow-modes-lite
---

# Plan — FORGE-BOARD-2: JIT task planning (per-task plan+grill against real prior state)

> Story FORGE-BOARD-2, epic `traceable-board`, spec `docs/specs/traceable-board.md`.
> Worktree `/Users/dev/Workdir/symphony-forge-BOARD-2`, branch off clean main.

## Problem

Today a story is planned and grilled ONCE, then `record_decomposition` writes
every task's contract upfront. Later tasks depend on what earlier tasks actually
built — which the upfront contract cannot know. The agent implements task N from
a contract written before tasks 1..N-1 existed, fills the unknowns by ASSUMING,
and the assumption ships as incorrect code. This is the #1 gap in the
traceable-board spec ("Speculative task contracts produce wrong code").

The fix: record only the task **list** at decomposition (id, order, deps,
one-line objective, acceptance) — then author AND grill each task's detailed
contract just-in-time, against the real repo state left by the prior tasks,
before that task is delegated. The per-task JIT grill is a **deterministic
gate**: no fresh, digest-bound passing grill for a task → its write delegation
is refused, exactly as `plan save` refuses an ungrilled plan today.

## Scope / Non-goals

**In scope:** the enforcement + data model for JIT per-task grilling, and its
board surfacing (folded in per the plan-grill). Concretely: a per-task grill
recorder + storage, a task-keyed delegation gate, the board render of per-task
grill status + a done-story PR link, and the decision + docs.

**Non-goals:** NOT loosening done-stage contract immutability (0023 stays); NOT
changing the plan/spec/epics/signoff grills; NOT changing `write_scope`-derived
write or `stage done` measurement; NOT a new stage engine — the harness already
permits list-only decomposition and already computes the per-task digest.

## Acceptance Criteria

1. `record_decomposition` records a task LIST (id, order, deps, one-line
   objective, acceptance) without full per-task contracts, and the list shows
   under its story on the board from decomposition onward.
2. A stage's write delegation is REFUSED without a fresh, digest-bound passing
   per-task grill for that task — a deterministic gate, mirroring `plan save`.
3. Each task's detailed contract (write_scope, required_tests, verify_commands)
   is authored JIT against the actual repo state after prior tasks, recorded via
   the existing 0023 ledgered re-record, and grilled before delegation.
4. A decision record amends 0007 / extends 0023 (deliberate, recorded, not a
   silent exception); done-stage immutability is preserved.
5. Both grill points are kept: the story plan-grill validates the decomposition;
   the per-task JIT grill validates each task's details.
6. The board renders each task's JIT grill status and a done story's PR link.

## Technical Approach

### What the mechanics maps found (the design is small)

- **List-only decomposition already records.** `record_decomposition_from_json.py`
  requires per task only `id`, `title`, `objective`, `acceptance_criteria`,
  ordered `dependencies`. `write_scope`, `required_tests`, `verify_commands`,
  `reviewer_focus` are optional at record time and re-read by id from the
  protected decomposition at delegate / `stage done`. No recorder change to
  record a bare list.
- **Existing gates already force a contract before productive work.** Write
  delegation is derived: `write = active stage AND non-empty write_scope`
  (`delegate.py:1124-1127`). `stage done` refuses empty `write_scope`
  (`stages.py:726-729`) and runs `required_tests`/`verify_commands`.
- **A per-task contract digest already exists.** `task_digest(task)`
  (`stages.py:568-578`) hashes `{write_scope, required_tests, verify_commands,
  acceptance_criteria}`; stamped on the stage at `stage start` (`task_sha256`)
  and passed into every delegation (`delegate.py:1146`).
- **The grill gate to mirror** is `require_grill(root, gate, prefixes, ...,
  expect_digest_of)` (`factory_lib.py:811-866`): file exists, `verdict==pass`,
  commit-stamped, `input_sha256==sha256_of(file)`, staleness vs prefixes.
  Recorded by `record_grill_from_json.py` (`--gate` ∈ {signoff,spec,epics,plan}).
- **The gap:** delegation has NO grill gate, and no grill is keyed by leaf-task id.

### The JIT loop (per task N, once N-1 is done)

```
prior stage N-1 done
  → author task N's contract (write_scope, required_tests, verify_commands)
      against the ACTUAL repo state left by 1..N-1
  → re-record the decomposition   (0023 ledgered; stage N not started yet)
  → grill task N                   (record_grill --gate task, bound to task_digest(N))
  → stage start N                  (stamps task_sha256 = task_digest(N), authored)
  → forge delegate N               (NEW gate: refuse unless fresh passing task grill)
  → stage done N
```

Authoring/re-recording **before `stage start`** means the digest stamped at start
already reflects the authored contract, so `stage done`'s
`_require_successful_launch` digest match holds with **no change to stage start
or the active-stage re-record path**.

### The one new mechanism: a per-task grill gate

1. **Recorder + storage.** Add `--gate task` (with `--task <id>`) to
   `record_grill_from_json.py`; write `.factory/grills/tasks/<id>.json` (per-task,
   retained; pr_ready archives them per story). Bind `input_sha256` to the task's
   `task_digest` VALUE (contract hash), not `sha256_of(file)`. Add `task` to the
   `grill.json` schema gate enum + a `task_id` field.
2. **`require_task_grill(root, task_id, expect_digest_value)`** in `factory_lib.py`
   — resolves `grills/tasks/<id>.json`, checks `verdict==pass`, commit stamp, and
   `input_sha256 == task_digest(task)`. Freshness is the digest itself.
3. **The delegation gate.** In `cmd_delegate`, at the `if write:` point
   (`delegate.py:~1127`), call `require_task_grill(...)` and refuse with the exact
   next command. Read-only lanes (`write==False`) unaffected. Single choke point:
   the pre_tool_use hook blocks every other write-companion path.

### Board/UI (folded in per the plan-grill — spec decomposition item 3)

The board is a localhost HTTP server (`forge_cli/board.py`) serving a single-file
SPA (`factory/board/index.html`); the Epic→Story→Task hierarchy + task dossiers
already exist. Two localized additions:

- **Per-task grill status.** The grills glob at `board.py:423-426` is
  non-recursive and MISSES `grills/tasks/<id>.json`; extend it, add a `grill`
  field to each task's `proof` in `task_dossiers` (`board.py:517-524`), render a
  grill line in `taskDossier`'s proof block (`index.html:1453-1474`).
- **Done-story PR link.** Add `events.load_events(base, event="pr-linked")` in
  `aggregate_state`/`story_detail`, render on a shipped story.

## Decisions

- **New:** `jit-task-planning` (created in planning, human-accepted before code).
  It **amends 0007** — the task LIST + execution order stay fixed at
  decomposition; only the per-task contract DETAIL becomes JIT — and **extends
  0023** — pre/mid-stage contract authoring is the normal path, gated by a fresh
  per-task grill; done-stage immutability preserved.
- All 27 active decisions reviewed (frontmatter). The one tension — the spec's
  "supersedes 0007" wording vs 0007 actually owning the list/order we KEEP — is
  resolved by amend-not-supersede (recorded in the plan-grill contradiction +
  resolution). No open contradiction signal.
- Governs: 0001 (deterministic gate), 0011 (orchestrator runs the grills), 0018
  (delegation gates — this adds one), 0009 (frozen gate surface — the new gate is
  a harness-source change shipped by PR), 0030 (harness-source is product here).

## Task Decomposition

Four tasks, sequential. This story bootstraps JIT, so its OWN decomposition is
recorded the current (upfront) way.

1. **Per-task grill recorder + schema + storage** (no deps) — `--gate task
   --task <id>`; `.factory/grills/tasks/<id>.json`; `input_sha256 = task_digest`;
   `grill.json` schema (`task` gate + `task_id`).
2. **`require_task_grill` + delegation gate** (dep: 1) — the task-keyed enforcer
   + the `if write:` precondition in `cmd_delegate`.
3. **Board/UI: per-task grill + done-story PR link** (dep: 1) — grills glob loads
   `grills/tasks/*.json`, grill status on each task's `proof`, rendered in the
   task dossier; `pr-linked` events render the PR link on a shipped story.
4. **Decision + docs** (dep: 2, 3) — the `jit-task-planning` decision + doc/skill
   updates.

## Surface Impact

- Task 1: `factory/scripts/record_grill_from_json.py`, `factory/schemas/grill.json`, `factory/tests/`.
- Task 2: `factory/scripts/factory_lib.py`, `factory/scripts/forge_cli/delegate.py`, `factory/tests/`.
- Task 3: `factory/scripts/forge_cli/board.py`, `factory/board/index.html`, `factory/board/example/`, `factory/tests/`.
- Task 4: `docs/decisions/<n>-jit-task-planning.md`, `WORKFLOW.md`, the `/forge` skill, `factory/prompts/griller.md`, the docs-decomposer prompt, `docs/degraded-mode.md`.

## Risks

- **Digest alignment.** If a task's contract is authored/re-recorded AFTER
  `stage start`, the stamped `task_sha256` diverges from the grilled+delegated
  digest and `stage done` refuses. Mitigation: the JIT loop authors + re-records
  BEFORE stage start, so digests line up with zero stage-engine changes.
- **Story at the reviewability ceiling (~4 tasks).** Folding the board/UI in was
  a deliberate human choice; if the diff won't fit one review sitting, task 3
  splits into its own story.
- **Bootstrapping.** This story is decomposed the current upfront way since JIT
  isn't built yet — expected; the new gate governs FUTURE stories only.

## Verify Plan

- **Gate tests** (`factory/tests/`): the recorder, the delegate-gate behaviours
  (refuse no/stale/blocked, pass fresh, read-only lane unaffected), and the board
  render (grill line + PR link) — each a runnable `required_tests` proof.
- **Determinism:** `python3 factory/scripts/check_dual_runtime.py` green;
  `python3 factory/scripts/verify.py` green.
- **Live smoke** on a 2-task fixture: `forge delegate <task>` REFUSES before a
  task grill; author → re-record → `record_grill --gate task` → delegate
  proceeds; edit the contract → delegate refuses again (stale digest).
