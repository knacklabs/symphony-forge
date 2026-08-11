---
issue: FORGE-WIN-1
title: Zero-setup Windows support
status: approved
saved: 2026-08-11T06:58:26+00:00
story: FORGE-WIN-1
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
---

# FORGE-WIN-1 — Zero-setup Windows support

## Problem

Windows client sessions degrade: Claude stops executing shell commands and
asks the human to run them. Root causes, evidenced 2026-08-11 and pinned in
the confirmed spec `docs/specs/windows-zero-setup.md`:

1. Every hook in the vendored `.claude/settings.json` (5 commands) pins
   `/usr/bin/python3`, which does not exist on Windows (Git Bash ships no
   Python). All hooks fail; a non-2 hook exit is non-blocking in Claude Code,
   so the always-armed write lockout silently disarms, session context never
   loads, and per-call hook errors train the model off the Bash tool. The
   fail-open hole is latent on EVERY platform. Exploration found the same
   defect in `.codex/hooks.json` (3 commands) — in scope, since
   `check_dual_runtime.py` demands hook parity between the two runtimes.
2. `./forge` is sh-only; without Git for Windows, Claude Code shells via
   PowerShell where it cannot run — and Claude Code's Bash tool itself
   requires Git Bash.
3. Codex CLI native Windows is unstable (openai/codex #24098, #26158, #2549,
   #12496); known-good practice is `windows.sandbox="unelevated"` +
   workspace-write.

The spec's grilled settlements bind this plan: one consolidated UAC confirm;
Codex Windows flags ride the delegation (never `~/.codex/config.toml`); a
`windows-latest` CI job; `forge next` as the self-heal trigger.

Today's gate tests cannot see the hole: `factory/tests/test_gates.py` invokes
hooks via `[sys.executable, .../pre_tool_use.py]` (line 37), never the command
string registered in settings.json — the tests pass with a broken
settings.json. That is exactly why the spec demands a doctor check that
executes the registered command verbatim.

## Scope / Non-goals

In scope — exactly the story's seven acceptance criteria: portable hook
interpreter in BOTH runtime hook files, doctor hook-health (fail-closed
detectability, all platforms), doctor `--fix` Windows remediation,
delegation-borne sandbox config, `forge next` Windows preflight,
init/adopt/upgrade propagation, windows-latest CI.

Out of scope, deliberately:

- **No cmd/PowerShell port of `./forge`** — Git Bash is the supported shell
  (Claude Code requires it for its Bash tool). Spec boundary.
- **No WSL2 installation** (admin + reboot); documented alternative only.
- **No user-global file writes** — `~/.codex/config.toml` untouched (grilled).
- **No fixing Codex CLI upstream bugs** — pin known-good config, surface
  named failures.
- **No general POSIX→Windows port of the whole test suite** — the CI job
  covers the lockout gate tests and doctor hook-health (the ACs); other
  suites join when a criterion needs them.
- **No changes to the codex-plugin-cc companion itself** — it is an external
  installed plugin; if the sandbox seam requires an upstream change we defer
  with a trigger (see Risks), we do not fork it.

## Acceptance Criteria

The seven criteria on roadmap item FORGE-WIN-1 (source of truth:
`plans/roadmap.json`), summarized:

1. Hooks execute on Windows/Git Bash; `pre_tool_use.py` denies product writes
   identically to macOS/Linux.
2. `forge doctor` executes every registered hook command verbatim on any
   platform; unrunnable → named red check.
3. Windows missing Git/Python: `doctor --fix` converges green, zero typed
   setup, at most one consolidated elevation confirm.
4. Recorded delegate invocation on Windows shows the injected sandbox flags;
   no user-global config mutation.
5. `forge next` on a hook-broken Windows clone names `doctor --fix` first.
6. init/adopt/upgrade each leave a client hook-healthy on Windows; upgrade
   replaces pinned-interpreter settings.
7. windows-latest CI runs lockout gate tests + doctor hook-health green.

## Technical Approach

Seams verified by read-only exploration 2026-08-11.

- **Portable hook commands** — `.claude/settings.json` (5 entries) and
  `.codex/hooks.json` (3 entries): replace `/usr/bin/python3` with
  `"$(command -v python3 || command -v python)"`, keeping
  `"$(git rev-parse --show-toplevel)/factory/scripts/<script>.py"` unchanged.
  sh command substitution is valid in Git Bash/macOS/Linux (hooks run under
  Git Bash on Windows). The `factory/scripts/<name>.py` literal must survive:
  `check_dual_runtime.check_hook_registration` (check_dual_runtime.py:324)
  regex-extracts script paths from the command string — restructuring to a
  wrapper would silently drop that protection. This mirrors the repo's own
  `./forge` launcher pattern (python3→python→py, version-gated) minus the
  `py -3` leg, which cannot ride one substitution; doctor + `--fix` cover
  that residue (real Python on PATH).
- **Doctor hook-health check** — new `_check` in `forge_cli/doctor.py`
  (pattern: `_check()` at doctor.py:202, appended in `cmd_doctor`): parse
  both hook files, execute each registered command verbatim through `sh -c`
  with a synthetic harmless payload on stdin (a read-only Bash tool_use
  JSON), expect clean exit. Red check names the failing command and the fix.
  This — not vendor integrity — is what makes a stale client visibly red:
  `check_vendor_integrity.py` hashes settings.json against the client's OWN
  manifest, so an un-upgraded client stays green there by construction.
- **Fast preflight variant** — a subprocess-free sibling of
  `doctor.fast_status()` (doctor.py:220, already consumed by
  session_start.py): parse hook files + `shutil.which` resolution only.
  Wired into `phase.cmd_next` (phase.py:16) at the TOP of the preflight
  block (before open-signals at phase.py:38) so a broken Windows clone
  prints `doctor --fix` as step 1 — spec settlement. Full verbatim execution
  stays doctor-only (next must stay fast).
- **Windows `--fix`** — extend the existing `--fix` branches in `cmd_doctor`
  (pattern: `_install_direnv` dispatching on `_platform_name()`,
  doctor.py:334/507): detect missing Git-for-Windows/Python ≥3.10, install
  via `winget` through the existing `run_quiet` list-argv convention,
  batching anything elevation-bound into ONE consolidated confirm. Never
  touches user-global Codex config.
- **Delegation-borne sandbox config** — the argv is built in
  `delegate.launch_companion` (delegate.py:952-959) and targets the plugin
  companion (`node codex-companion.mjs task ...`), NOT `codex` directly; the
  installed companion (1.0.6) exposes NO config passthrough on `task`
  (usage: only --background/--write/--resume*/--model/--effort). So stage
  WIN-1.3 starts with a bounded read-only verification of the companion's
  sandbox seam, with ranked fallbacks — each still zero-user-setup:
  1. newer companion accepts passthrough → append platform-conditional flags
     in `launch_companion` (they land in `.factory/delegations.jsonl` via the
     existing `argv`+`argv_sha256` recording for free — AC 4's evidence);
  2. companion's own config store (its `setup`/`setConfig` surface) supports
     sandbox mode → `doctor --fix` invokes it (agent-run, plugin-owned state,
     not a user-global file we hand-edit);
  3. no seam → `./forge defer add` with trigger "companion exposes sandbox
     config", document the gap in the Windows doc, and delegate still runs
     with the companion's defaults.
  `pinned_run_config` (delegate.py:773) already documents why config must
  ride the invocation — same rationale.
- **CI** — new harness-only workflow `.github/workflows/windows-gates.yml`
  (windows-latest, setup-python 3.11, pytest the lockout/hook-health subset)
  and NOT added to scaffold's `COPY_WORKFLOWS`, so no client repo pays for
  it (client machines are covered by local doctor, not client CI). Chosen
  over a guarded job inside the vendored `factory-scaffold.yml` to avoid
  shipping dead YAML to clients and disturbing the `scaffold-check`
  branch-protection context that `doctor --fix` registers (doctor.py:305).
  Gate tests already invoke hooks via `sys.executable` (test_gates.py:37) —
  interpreter-portable by construction.
- **Docs** — `docs/windows.md`: supported path = Git for Windows + Git Bash;
  agent-handled remediation flow; WSL2 escape hatch; codex sandbox flags
  rationale + upstream issue links. Cross-referenced from degraded-mode.md
  and the getting-started §.
- **Propagation** — zero new machinery: settings.json/hooks.json are copied
  verbatim from repo root by scaffold `COPY_CLAUDE`/`COPY_CODEX`
  (scaffold.py:17/530-544), adopt (adopt.py:221), and upgrade
  `CLAUDE_HARNESS_OWNED`/`COPY_CODEX` (upgrade.py:39-42/491-509) — fix the
  two root files and all three paths ship them. Add propagation tests
  asserting a scaffolded/upgraded target carries the portable command.
  Ordering constraint honored: doctor remediation mutates no vendored files,
  so it stays clear of the `write_manifest` ordering (scaffold.py:586,
  upgrade.py:694).

## Decisions

- NEW: `0038-portable-fail-closed-hooks` (record before decomposition):
  registered hook commands must be host-portable (PATH-resolved interpreter,
  sh-compatible, `factory/scripts/*.py` token preserved) and their
  executability machine-proven by doctor on every platform — a hook that
  cannot run is a red check, never silence. Records rejected alternatives:
  pinned absolute interpreter (today's defect), a committed shim script or
  `forge hook` subcommand (both drop the literal script token
  check_dual_runtime's protection keys on), `$CLAUDE_PROJECT_DIR`
  (worktree ambiguity vs `git rev-parse`).
- The companion sandbox seam choice (fallback 1/2/3 above) is made inside
  WIN-1.3 by evidence, recorded as an assumption (`forge plan assume`) when
  made; it does not need its own decision record unless fallback 3 fires
  (then the deferral + a decision documenting the gap).
- All other choices derive from the confirmed spec's grilled settlements.

## Surface Impact

| Surface | Class | Note |
|---|---|---|
| Runtime behavior | Changed | hooks resolve interpreter at runtime; delegate may gain Windows flags; forge next gains preflight step |
| API | N-A | no service surface |
| Data/schema | Unchanged by design | no new artifacts; doctor emits existing check shape; delegations.jsonl schema unchanged (argv already recorded) |
| CLI/ops | Changed | doctor hook-health + Windows --fix; next preflight line |
| UI | N-A | board untouched |
| Docs | Changed | docs/windows.md + cross-refs |
| Tests | Changed | hook-health + propagation gate tests; windows-gates.yml CI job |

## Task Decomposition

(Story-level stages; task contracts authored JIT per 0032; disjoint write
scopes per lesson decomposition-shared-function-scope.)

1. **WIN-1.1 Portable fail-closed hooks** — `.claude/settings.json` +
   `.codex/hooks.json` command change; doctor hook-health check (verbatim
   execution, all platforms) + fast static variant; check_dual_runtime
   parity intact; gate tests: red-check-on-unrunnable, hook-command-executes,
   propagation (scaffold/upgrade target carries portable command). Write
   scope includes decision 0038.
2. **WIN-1.2 Windows remediation + preflight** — doctor `--fix` winget path
   with single-confirm elevation batching; `forge next` preflight wiring;
   `docs/windows.md`. Depends on WIN-1.1's fast check.
3. **WIN-1.3 Sandbox seam + CI** — companion seam verification (read-only)
   then fallback 1/2/3 implementation + assumption record;
   `windows-gates.yml`; delegate evidence assertion test.

## Risks

- **Companion seam may not exist (fallback 3)**: AC 4 then lands as a
  recorded deferral + documented gap instead of injected flags. This is the
  honest bound — the companion is external (scope boundary). Mitigation
  ordering puts the seam check FIRST in WIN-1.3 so the story's remaining
  ACs never wait on it.
- **Gate tests POSIX-coupled on windows-latest**: hook invocation is already
  `sys.executable`-based; residual couplings (paths, `signal` import at
  test_gates.py:19) get fixed where cheap; any Windows-skipped test carries
  a named reason, and the lockout deny/allow tests themselves MUST run
  (AC 7 is not satisfiable by skipping them).
- **CI cannot exercise the UAC path** (runners pre-provisioned + headless):
  detection/batching logic unit-tested with installer calls faked; the real
  elevation pass runs ONCE on the affected client's machine (grilled,
  2026-08-11) and is recorded via `record_test_from_json.py --kind
  functional`.
- **RECURRING classes at upgrade.py** (`repository-escape`,
  `reviewed-separately`): this story adds NO new cross-repo copy code (rides
  existing COPY_CLAUDE/COPY_CODEX/GATE trees). Tripwire per WORKFLOW.md: if
  review flags repository-escape again near the propagation tests, escalate
  to the queued hard-link/TOCTOU consolidation story instead of patching
  here.
- **Frozen gate surface (0009)**: `forge` and `.claude/settings.json` are
  GATE_FILES; the change re-arms via the normal `write_manifest` path in
  init/adopt/upgrade. `.codex/hooks.json` is NOT currently a GATE_FILE —
  adding it is tempting but out of scope (would change client gate surface);
  noted for the 0038 decision text.
- **String assertions in test_gates.py** (lines ~5263/5566/5918/7819 assert
  literal `python3 factory/scripts/...` in workflow YAML/templates): our
  change touches settings.json commands, not those templates — but WIN-1.1's
  tests must not introduce new literal-interpreter assertions.

## Verify Plan

- `python3 factory/scripts/verify.py` (never ad hoc).
- Gate tests locally (macOS): hook-health red-check when command unrunnable
  (temporarily broken PATH in test env), green on healthy; lockout parity;
  propagation tests.
- PR CI green including the new `windows-gates.yml` (windows-latest job:
  lockout gate-test subset + doctor hook-health against the checked-out
  repo).
- Manual sanity (macOS): `forge doctor` hook-health green; `forge next`
  unchanged on healthy clones.
- Functional (AC 3): affected client's real Windows machine — upgrade, then
  agent runs `forge doctor --fix`; converges green, ≤1 elevation confirm;
  recorded `--kind functional`.
