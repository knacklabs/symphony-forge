---
issue: FORGE-BOARD-6
title: knacklabs-upgrade-project skill (machinery upgrade + guided re-authoring)
status: approved
saved: 2026-08-08T19:15:56+00:00
story: FORGE-BOARD-6
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
  - 0032-jit-task-planning
---

# Plan — FORGE-BOARD-6: knacklabs-upgrade-project skill

> Story FORGE-BOARD-6, epic `traceable-board`, spec `docs/specs/traceable-board.md`.
> Worktree `/Users/dev/Workdir/symphony-forge-UPG6`, branch off main. Depends on
> FORGE-BOARD-4 (audit/backfill) and FORGE-BOARD-5 (`roadmap fill` + backfill honesty).

## Problem

Every deterministic piece now exists — `forge upgrade` (machinery), `forge doctor
--fix` (tooling), `forge project audit`/`backfill` (project-state, FORGE-BOARD-4),
`forge roadmap fill` + `forge project mark-predates` (safe repair + honest
provenance, FORGE-BOARD-5) — but there is no operator skill that SEQUENCES them
into the constant, change-driven upgrade the user asked for. `knacklabs-migrate-project`
covers first-time `adopt`; this is its `forge upgrade` sibling. It must
compose the deterministic commands and add one human-in-the-loop step (guided
re-authoring of *pending* stories), incorporating the fixes from the Codex plan
review (safe repair primitive is now `roadmap fill`, not `import`).

## Scope / Non-goals

**In scope:** one operator skill `install/claude/knacklabs-upgrade-project/SKILL.md`
(a runbook), its registration in `setup`, updated docs, and a structure/registration
test. Non-goals: NO new `forge` command (all primitives exist); NO change to
`upgrade`/`doctor`/`project`/`roadmap fill` behaviour; NO schema/harness.yaml/dual-runtime
gate change (operator skills are outside them); NO re-authoring of done stories.

## Acceptance Criteria

1. `install/claude/knacklabs-upgrade-project/SKILL.md` exists and runs, in order:
   **locate the harness robustly** (verify the `{{HARNESS_PATH}}` clone's canonical
   origin + expected ref + CLEAN worktree; halt on pull failure — never clone into
   an existing dir) → **preflight** (`forge project audit --repo "$TARGET"` +
   `forge doctor`; its nonzero exit is diagnostic) → **machinery upgrade**
   (`cd "$HARNESS" && forge upgrade --target "$TARGET"` from a clean harness +
   `forge doctor --fix`) → review diff → **deterministic backfill**
   (`forge project backfill --repo "$TARGET"`; unresolved provenance is surfaced
   for the human to resolve with `forge pr-link` or `forge project mark-predates`)
   → **guided re-authoring** of PENDING incomplete stories via `forge roadmap fill`
   (agent proposes, human confirms; NEVER `roadmap import`, NEVER done stories) →
   **re-verify** (`check_vendor_integrity`, `check_board_complete`, `forge project
   audit`) → hand off (`forge next`).
2. Every CLIENT-targeting command carries an absolute `--repo "$TARGET"` (or an
   explicit `cd "$TARGET"`) so the runbook never audits/backfills the HARNESS
   (Codex major 4). Machinery upgrade is the only step run from `$HARNESS`.
3. The skill frames itself as a **periodic, convergent** runbook (not blind-idempotent):
   a clean committed baseline is required before each upgrade cycle; the repair
   steps are conditional on current audit gaps (Codex minor 5).
4. The skill is registered (name added to `setup`'s bootstrap loop → installs to
   both `~/.claude/skills` and `~/.codex/skills`). The existing "Upgrading an
   existing repo" doc section routes through it (updated, not duplicated).

## Technical Approach

### The skill — `install/claude/knacklabs-upgrade-project/SKILL.md`

Mirror `knacklabs-migrate-project`/`knacklabs-new-project` structure: frontmatter
(name + trigger phrases "upgrade this project", "bring the harness up to date"),
H1 + framing, "The model" (constant/convergent; machinery is deterministic,
re-authoring is judgment), "Find the target" (absolute `TARGET`), `## Steps` (the
AC#1 sequence with the robust locate block — explicit `if [ -d "$HARNESS/.git" ]`
verify-origin/ref/clean, `git -C "$HARNESS" fetch` + halt-on-failure, else clone
fresh; then `cd "$HARNESS"` only for `forge upgrade`), `## Rules` (never `import`,
never done stories, always `--repo "$TARGET"`, commit before re-upgrading).

### Registration + docs

- `setup` — add `knacklabs-upgrade-project` to the bootstrap-skill loop.
- Update the EXISTING `docs/getting-started.md` "Upgrading an existing repo"
  section (do not add a competitor — Codex nit 7) to route through the skill,
  keeping the direct `forge upgrade` command as the documented deterministic core.
  Parallel rows in `README.md` and `factory/skills/forge.md`.

### Test

Model on `test_forge_skill_maps_lite_mode_phrase`: read the SKILL.md + `setup`,
assert existence, frontmatter `name` + trigger phrases, the `{{HARNESS_PATH}}`
robust-locate block, `--repo "$TARGET"` on client commands, `forge roadmap fill`
present and `roadmap import` ABSENT (the safety invariant), and the skill name in
`setup`'s loop.

## Decisions

No new decision. All 28 active reviewed (frontmatter). Load-bearing: **project-record**
(re-authoring is forward-only via `roadmap fill`; the skill never fabricates done-story
history), **0009** (the skill drives `forge upgrade`, which re-arms the frozen gate —
never patches gates in a client), **0001** (the deterministic primitives do the
enforcing; the skill only sequences + gathers human judgment). No contradiction with
an active decision.

## Surface Impact

- `install/claude/knacklabs-upgrade-project/SKILL.md` — NEW (the runbook).
- `setup` — register the skill.
- `docs/getting-started.md` (update existing upgrade section), `README.md`,
  `factory/skills/forge.md` — doc parallels.
- `factory/tests/test_gates.py` — the skill structure/registration/safety-invariant test.

## Task Decomposition

One leaf task (a cohesive "ship the upgrade skill" deliverable).

1. **FORGE-BOARD-6.1 — the knacklabs-upgrade-project skill + registration + docs +
   test** (no deps) — the SKILL.md runbook (robust locate, `--repo TARGET`
   routing, `roadmap fill` re-authoring, convergent framing), `setup` registration,
   doc updates, and the structure/safety test.

## Risks

- **Skill is guidance; determinism lives in the commands it calls.** The one place
  the skill itself must be exact is the `--repo "$TARGET"` routing and "fill not
  import" invariant — both asserted by the test (Codex majors 4 + the test he
  wanted, minor 6).
- **The robust-locate block is shell in a doc.** It's copied/adapted, not executed
  by tests; the test asserts the guard STRINGS are present (origin/ref/clean check,
  no clone-into-existing), keeping it honest without a live clone.
- **`--kind feature`; net-additive** (a new skill + a test + doc rows).

## Verify Plan

- **Test** (`factory/tests/test_gates.py`): the skill exists; carries the name +
  trigger phrases + the robust `{{HARNESS_PATH}}` block; every client command uses
  `--repo "$TARGET"`; `forge roadmap fill` is present and `roadmap import` is
  absent; it's in `setup`'s loop.
- **Determinism:** `check_dual_runtime.py` + `verify.py` green (the skill touches
  no gated surface — confirms no regression).
- **Live smoke:** inspecting the skill's steps resolves to real commands; `setup`'s
  loop includes the skill so it stamps into both runtime homes.
