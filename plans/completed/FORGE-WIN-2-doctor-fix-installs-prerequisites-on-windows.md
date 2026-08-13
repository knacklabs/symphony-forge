---
issue: FORGE-WIN-2
title: Doctor --fix installs prerequisites on Windows
status: approved
saved: 2026-08-12T09:20:01+00:00
story: FORGE-WIN-2
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
  - 0033-gate-a-declares-all-work-records
  - 0034-vendored-docs-are-client-safe
  - 0035-commit-belt-keeps-ledger-fresh
  - 0036-client-gates-arm-on-roadmap
  - 0037-strict-role-split
  - 0038-portable-fail-closed-hooks
---

# FORGE-WIN-2 — Doctor --fix installs prerequisites on Windows

## Problem

WIN-1 made the harness fail CLOSED on a broken Windows machine — hooks block,
doctor names what's missing, `forge next` points at remediation. But the
remediation itself doesn't exist: `doctor --fix` has NO install branch for
git or python on any platform (all existing `--fix` work is user-scope
direnv/npm/plugin installs; nothing ever elevates), doctor has no python row
at all (`HOOK_HEALTH_FIX` at doctor.py:220 promises "doctor --fix installs
Python 3.10+" — a promise the code does not keep), and the git row's fix
string is macOS-centric. A Windows dev with no Git or Python is told
what's wrong and given nothing but manual installer URLs — the opposite of
the spec's zero-setup directive.

Grilled settlements binding this plan (docs/specs/windows-zero-setup.md):
zero user-typed setup; anything the OS forces through elevation batched into
ONE consolidated UAC confirm; init/adopt/upgrade run remediation as part of
the flow; the harness never writes user-global config files.

Deferral D-0018 fires at this planning gate (its trigger): `forge.cmd`'s
native fallback omits a `python3.exe` probe — in scope here.

## Scope / Non-goals

In scope — the story's two ACs: (1) on Windows missing Git or Python,
`doctor --fix` converges to green with zero typed setup and ≤1 UAC confirm;
(2) init/adopt/upgrade leave a client hook-healthy on Windows.

Out of scope, deliberately:

- **No bundled binary downloads for Git/Python** (the `_install_direnv_windows`
  urllib pattern does NOT scale to full installers — attack and maintenance
  surface). winget is the only installer; winget absent → named red row
  with the manual URLs. Recorded in new decision 0039.
- **No PowerShell port of forge** (spec boundary). PowerShell as elevation
  TRANSPORT (`Start-Process -Verb RunAs`) is not a port.
- **No user-global config writes** (spec boundary) — installs yes, config no.
- **No widening of the windows CI selector to the full suite** (D-0020:
  a latent msvcrt test failure fires if widened; new tests join the explicit
  node-id list only).
- **Executor-fidelity certification** stays deferred (D-0019 → WIN-3).

## Acceptance Criteria

From `plans/roadmap.json` FORGE-WIN-2:

1. On Windows missing Git or Python, `doctor --fix` converges to green with
   no user-typed setup and at most one UAC confirm.
2. init/adopt/upgrade each leave a client repo hook-healthy on Windows;
   upgrade replaces pinned-interpreter settings (WIN-1 proved the config
   propagation; this story adds the remediation wiring in those flows).

## Technical Approach

Seams verified by read-only exploration 2026-08-12 (doctor.py is 1141 lines
post-WIN-1; all line refs current).

- **Python becomes a first-class doctor row** (required): version-floored
  `>= 3.10` probe across `py -3`/`python3`/`python`, mirrored into
  `fast_status()` (doctor.py:437) — the :422 comment mandates the two sites
  agree. Git row (:792) keeps its check but gains a platform-branched fix
  string (pattern: `_direnv_fix_message` :745).
- **Windows install path** — new `_install_git_windows` / `_install_python_windows`
  mirroring the `_install_direnv` dispatcher shape (:724), driven from new
  `if args.fix:` branches beside the existing ones (:837-:1005 family):
  1. **winget presence probe** — absent → required red row naming the two
     manual installers; never a bundled download.
  2. **User-scope first**: `winget install --id Git.Git --scope user` /
     `--id Python.Python.3.12 --scope user`, `--silent
     --accept-package-agreements --accept-source-agreements` via direct
     `subprocess.run` with a generous timeout — NOT `run_quiet` (its
     hardcoded 15s at common.py:17 cannot carry an installer; the ~15 other
     call sites stay untouched).
  3. **Single elevated batch fallback**: only when user-scope is refused by
     the OS/policy, ONE `powershell Start-Process -Verb RunAs` invocation
     whose argument list runs BOTH pending installs — one UAC confirm total,
     never per-package (the `_install_direnv_linux` per-command sudo shape
     at :689 is explicitly the anti-pattern here).
  4. **In-process PATH refresh + re-probe**: after install, extend
     `os.environ["PATH"]` with the known install dirs (pattern:
     `_prepend_user_bin_to_path` :624) and re-run the checks so the SAME
     doctor run reports green — "converges" means this run, not a re-run.
- **`forge next` names `--fix`**: phase.py:41 currently prints "run
  `./forge doctor` first"; the spec criterion says `doctor --fix` — one-word
  settle in the spec's favor.
- **D-0018 — `forge.cmd` python3 probe**: third fallback label between
  `:python_fallback` and `:missing` (py -3 → python → python3 → missing).
  The two text assertions in `test_forge_cmd_routes_git_bash_then_python_fallbacks`
  (`count("sys.version_info >= (3, 10)") == 2` at test_gates.py:2672 and the
  where-index chain at :2660) update in the same change — they run on every
  platform.
- **init/adopt/upgrade remediation wiring** (spec :57-62): on Windows, the
  tails of `cmd_init`/`cmd_adopt`/`cmd_upgrade` run the fast hook check and,
  when red, invoke the same `--fix` remediation (one-confirm guarantee
  carries through); POSIX flows byte-identical. Placement honors the
  write_manifest ordering (remediation mutates no vendored files).
- **Docs**: `docs/getting-started.md:70-78` install list gains Git-for-Windows/
  Python; the Windows remediation flow documented (new short docs/windows.md,
  cross-linked from degraded-mode.md — carried over from WIN-1's plan where
  it was descoped by the narrowing).
- **Tests** (patterns already in the file): argv-recording fakes via
  `monkeypatch.setattr(doctor.run_quiet | doctor.subprocess.run)` — the
  batching test asserts EXACTLY ONE elevation-shaped invocation carrying
  both package ids and zero per-package elevations; winget-absent red row;
  PATH-refresh convergence with stub executables (pattern of
  test_doctor_discovers_and_probes_git_bash_outside_path :2857);
  fast_status/doctor python-row agreement. New Windows-relevant node ids
  join the windows-hook-gates explicit selector
  (factory-scaffold.yml:88-96, `-q` stays last).

## Decisions

- NEW: `0039-windows-remediation-via-winget` (record before decomposition):
  winget is the sole installer for Windows prerequisites; user-scope
  installs first, a single elevated PowerShell batch as the only elevation
  (≤1 UAC confirm per doctor run); winget absent is a named red row, never
  a bundled download. Rejected: urllib installer downloads (attack/
  maintenance surface — the direnv single-binary precedent does not scale),
  per-package elevation (linux sudo shape), auto-elevating when user scope
  suffices.
- "converges in the same run" (in-process PATH refresh) is design, derived
  from AC 1's wording — no separate record.
- No other new decisions; the elevation-batching policy itself was settled
  at the spec grill (2026-08-11).

## Surface Impact

| Surface | Class | Note |
|---|---|---|
| Runtime behavior | Changed | doctor gains python row + Windows install branches; init/adopt/upgrade tails gain Windows remediation; forge.cmd gains python3 probe |
| API | N-A | — |
| Data/schema | Unchanged by design | no new artifacts; check rows keep existing shape |
| CLI/ops | Changed | doctor --fix does real Windows installs; forge next says --fix |
| UI | N-A | — |
| Docs | Changed | getting-started install list; docs/windows.md |
| Tests | Changed | faked-installer batching tests; selector additions (explicit ids only, D-0020) |

## Task Decomposition

(JIT contracts per 0032; disjoint scopes; test_gates.py shared across
sequential stages only.)

1. **WIN-2.1 Doctor remediation core** — python row (+fast_status mirror),
   platform-branched git fix string, winget user-scope-first installs,
   single-elevation batch, PATH-refresh convergence, phase.py `--fix`
   string, decision 0039, faked-installer tests.
   Scope: `factory/scripts/forge_cli/doctor.py`, `factory/scripts/forge_cli/phase.py`,
   `docs/decisions/0039-*.md`, `factory/tests/test_gates.py`.
2. **WIN-2.2 Launcher probe + flow wiring + docs** — forge.cmd python3
   probe (D-0018, with the two text-assertion updates), init/adopt/upgrade
   Windows remediation tails, getting-started + docs/windows.md,
   windows-hook-gates selector additions.
   Scope: `forge.cmd`, `factory/scripts/forge_cli/{scaffold,adopt,upgrade}.py`,
   `docs/getting-started.md`, `docs/windows.md`, `docs/degraded-mode.md`,
   `.github/workflows/factory-scaffold.yml`, `factory/tests/test_gates.py`.

## Risks

- **CI cannot prove the UAC path** (runners are already admin; RunAs
  succeeds silently): the batching INVARIANT is proven by argv-recording
  fakes (exactly one elevation-shaped call); the real elevation pass runs
  once on the affected client's machine and is recorded as functional
  evidence — grilled settlement carried over from the spec gate.
- **Managed machines that block winget/user-scope installs**: honest red
  rows with named fixes; no policy-evasion attempts.
- **Partial convergence** (git installs, python refused): idempotent —
  re-running --fix finishes the job; the convergence test covers the
  mixed state.
- **Sandbox constraints on workers** (recorded lessons): delegated workers
  cannot run `ps`-dependent tests (canonical suite runs here) and cannot
  edit `.claude/.codex` (not in scope this story); briefs carry both lessons
  automatically via applies-to matching.
- **RECURRING classes at upgrade.py** (repository-escape x3): WIN-2.2
  touches upgrade.py's TAIL only (post-write_manifest remediation call,
  no copy-path changes). Tripwire per WORKFLOW.md stands: any
  repository-escape re-flag escalates to the queued hard-link/TOCTOU
  consolidation instead of riding this story.

## Verify Plan

- `verify.py` with the pinned `.envrc` commands (never ad hoc).
- Focused selectors locally (macOS): faked-installer batching (exactly-one-
  elevation), winget-absent red row, PATH-refresh convergence, python-row/
  fast_status agreement, forge.cmd text assertions.
- Full gate suite green (xdist, permissive environment).
- windows-hook-gates green on the PR with the new node ids in its selector.
- Functional (AC 1, real elevation): affected client's Windows machine —
  `forge doctor --fix` on a box missing Git/Python → green, ≤1 UAC confirm;
  recorded via `record_test_from_json.py --kind functional`.
- D-0018 resolved on plan approval (`forge defer resolve` pointing here).

## Implementation Assumptions

<!-- Made during implementation, NOT part of the approved plan. Dev: review these before merge; promote any that matter to docs/decisions/. -->
- 2026-08-12: Windows remediation uses the winget package Python.Python.3.12 because it is a maintained release satisfying the required Python 3.10 minimum.
- 2026-08-12: Windows python winget pin corrected to Python.Python.3.14: 3.12 is security-only per the Python lifecycle; 3.14 is the current bugfix line with winget manifests. Supersedes A-0009's 3.12 rationale (orchestrator's earlier confirmation was factually stale).
