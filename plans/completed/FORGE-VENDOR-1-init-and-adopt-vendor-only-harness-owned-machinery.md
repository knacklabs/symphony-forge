---
issue: FORGE-VENDOR-1
title: init and adopt vendor only harness-owned machinery
status: approved
saved: 2026-08-06T17:50:59+00:00
story: FORGE-VENDOR-1
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
---

# FORGE-VENDOR-1 — init and adopt vendor only harness-owned machinery

## Problem

`forge init` and `forge adopt` vendor the machinery by copying `.claude` (in
`COPY_TREES`, `scaffold.py:15`) and `.codex/skills` **wholesale from
`repo_root()`** — the repo the command runs in. `upgrade` instead copies only a
harness-owned set (`CLAUDE_HARNESS_OWNED = ["CLAUDE.md","settings.json",
"skills/forge"]`, `upgrade.py:38`). All three source from `repo_root()`
(`scaffold.py:487`, `adopt.py:165`, `upgrade.py:397`), so when a **client**
repo's vendored gate tests run `init`/`adopt` in CI, `repo_root()` is the client
and the wholesale copy drags the client's own `.claude/skills/<x>/SKILL.md` into
the scaffold. Its `<!-- canon: skills/<x>/... -->` target is a root `skills/`
the harness never vendors → dangling marker → `check_dual_runtime` fails.
Confirmed in knacklabs/cadence (factory-scaffold red, ~13/~6 failures, ~8 from
this cause). Separately, the vendored `factory-scaffold` workflow runs
`pytest factory/tests` in every client, but a few tests bind to symphony-forge's
own `FORGE-INIT-1` fixtures (`test_gates.py:6505, 6736, 7985`) and can never pass
elsewhere.

## Scope / Non-goals

In scope: one shared harness-owned manifest for `.claude`/`.codex`, applied by
`init` and `adopt` (and `upgrade` already close); gating the fixture-bound tests
so the vendored suite passes in a client; a client-repo simulation test.

Out of scope, deliberately:

- **No change for `init`/`adopt` of symphony-forge itself** — the harness's own
  `.claude`/`.codex` IS exactly the manifest, so a normal run is unchanged.
- **Not the path-boundary work** (0028, just shipped) — this is ownership
  filtering, a different concern in the same copy code.
- **Not dropping `pytest` from the vendored workflow** — the human chose to GATE
  the symphony-forge-only tests so clients keep running the portable suite.
- **No new dependency**; stdlib only.

## Acceptance Criteria

Verbatim from the roadmap story, each with its proof:

1. `init` and `adopt` vendor only the harness-owned `.claude`/`.codex` manifest
   and never the source's other `.claude/skills/*` or `.codex/skills/*`. Proof: a
   test runs `init` from a source carrying a decoy `.claude/skills/decoy/SKILL.md`
   and asserts the scaffold has no `decoy` and `check_dual_runtime` is clean.
2. The harness-owned set is defined ONCE and shared by `init`, `adopt`,
   `upgrade`. Proof: a test imports the single manifest and asserts each command
   uses it (no second hard-coded list).
3. The `FORGE-INIT-1` fixture-bound tests skip when their fixture is absent and
   still run in symphony-forge. Proof: the tests carry a skip guard keyed on the
   fixture's presence; they still execute here (fixture present).
4. A simulated client-repo run of the vendored checks (init + dual-runtime + the
   gated suite) passes. Proof: a test scaffolds from a source with a client skill
   and runs `check_dual_runtime` on the result.
5. `init`/`adopt`/`upgrade` of symphony-forge behave exactly as before. Proof:
   the full existing suite stays green, unweakened.

## Technical Approach

**The rule is skill ownership (human decision).** SKILLS carry the canon markers
that break; agents and config do not. So the shared source of truth is the set of
harness-owned skills — `forge`, present as `.claude/skills/forge` and
`.codex/skills/forge`. `.codex/agents` and the `.codex` config files
(`COPY_CODEX`) are copied AS-IS (harmless in a scaffold — no canon markers — and a
normal dev run sources from the harness anyway).

**One shared manifest (Task 1).** In `scaffold.py` (imported by adopt and
upgrade), the harness-owned `.claude` surface is exactly `upgrade`'s existing
`CLAUDE_HARNESS_OWNED` (`CLAUDE.md`, `settings.json`, `skills/forge`); express the
harness skill set once so `.claude/skills` and `.codex/skills` filter to the same
`forge` and both init and upgrade read one definition. A test asserts init, adopt
and upgrade agree on the skill set.

**`init` routes through it (Task 1).** Remove `.claude` from the wholesale
`COPY_TREES`; copy the manifest's `.claude` files file-by-file and only
`.claude/skills/forge`. Replace the wholesale `.codex/skills` copytree with only
`.codex/skills/forge`. `.codex/agents` and config copy as today. Every copy still
routes through the FORGE-BOUNDARY-1 boundary helpers already in place.

**`adopt` routes through it (Task 2).** Replace `vendor_tree(".claude")` and
`vendor_tree(".codex/skills")` (`adopt.py:74,81`) with manifest-scoped copies of
the same paths, keeping adopt's per-file `vendor_file` boundary check.

**Gate the fixture tests (Task 3).** The three `FORGE-INIT-1`-bound tests get a
`pytest.mark.skipif`/guard keyed on the fixture's presence
(`.factory/history/FORGE-INIT-1/`), so they run in symphony-forge and skip in a
client. Add the client-repo simulation test (AC1/AC4).

**Rejected:** dropping `pytest factory/tests` from the vendored workflow (human
chose to keep the portable suite in client CI); a per-command owned-list (the
exact drift this story removes); a runtime "is this the harness?" check (the
source can legitimately be a client — the manifest is the source of truth).

## Decisions

No new decision record required: the ownership rule already exists as
`upgrade`'s `CLAUDE_HARNESS_OWNED` (decision 0016 established the machinery-dir
ownership split); this story makes `init`/`adopt` obey the same rule and shares
one definition. If review judges the manifest a durable contract, a short record
can capture it — flagged, not assumed.

## Surface Impact

| Surface | Classification | Notes |
| --- | --- | --- |
| Runtime behavior | Changed | init/adopt no longer copy a source repo's non-harness `.claude`/`.codex` skills; a symphony-forge run is unchanged. |
| API | N-A | No HTTP surface. |
| Data/schema | Unchanged by design | No artifact shapes change. |
| CLI/ops | Changed | The vendored factory-scaffold workflow now passes in a client (gated fixture tests); its success path is otherwise identical. |
| UI | Unchanged by design | The board does not vendor. |
| Docs | Changed | The confirmed spec `docs/specs/harness-owned-vendoring.md` records the capability. |
| Tests | Changed | Shared-manifest agreement test; init decoy-skill test; client-repo dual-runtime simulation; skip guards on the three fixture-bound tests. |

## Task Decomposition

Three sequential tasks in one worktree (0002), one bounded concern each:

1. **Shared harness-owned manifest + init.** Scope:
   `factory/scripts/forge_cli/scaffold.py`, `factory/scripts/forge_cli/upgrade.py`,
   `factory/tests/test_gates.py`. The manifest, `upgrade` re-expressed on it,
   init routed through it, the agreement test and the init decoy-skill test.
2. **adopt routes through the manifest.** Scope:
   `factory/scripts/forge_cli/adopt.py`, `factory/tests/test_gates.py`. Replace
   the wholesale `.claude`/`.codex/skills` vendoring; adopt decoy-skill test.
3. **Gate the fixture tests + client-CI simulation.** Scope:
   `factory/tests/test_gates.py`. Skip guards on the three `FORGE-INIT-1` tests;
   a test that scaffolds from a client-skill source and asserts dual-runtime is
   clean (the vendored-workflow-in-a-client guarantee).

`user_facing: false` — CLI setup commands, no functional check.

## Risks

- **Missing a harness-owned path in the manifest** → a real harness file stops
  being vendored, breaking a fresh scaffold. Mitigation: the agreement test plus
  the existing init/adopt scaffold tests (which assert the vendored files exist)
  catch an under-inclusive manifest.
- **Over-broad gate guard** hides a genuinely failing fixture test in
  symphony-forge. Mitigation: the guard keys on the fixture's presence, so it is
  a no-op here (fixture present) and only skips where the fixture is absent.
- **A client custom agent copied into a scaffold** (agents are vendored as-is).
  Accepted (human decision): agents carry no canon markers, so this is cosmetic,
  not breaking; filtering skills closes the actual bug without agent-list drift.

## Verify Plan

Deterministic, the commands CI runs (harness-only, from `.envrc`):

```bash
python3 factory/scripts/verify.py
```

running `check_dual_runtime.py`, `check_factory_scaffold.py`, and
`pytest factory/tests -q`. What falsifies the work: an `init`/`adopt` scaffold
that contains a source repo's non-harness skill; a dangling canon marker on a
scaffold from a client-skill source; a second hard-coded owned-list diverging
from the manifest; a `FORGE-INIT-1` fixture test failing in a client (or skipped
in symphony-forge); or any existing scaffold test needing to be weakened. Each
has a test. Review is one autoreview pass, three lenses (0011).
