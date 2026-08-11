---
issue: FORGE-WIN-1
title: Zero-setup Windows support: the fail-open core
status: approved
saved: 2026-08-11T17:35:04+00:00
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
  - 0038-portable-fail-closed-hooks
---

# Plan — FORGE-WIN-1: The fail-open core (narrowed; grilled 2026-08-11)

> Story FORGE-WIN-1, epic `windows-zero-setup`, spec
> `docs/specs/windows-zero-setup.md`. Branch
> `feat/FORGE-WIN-1-zero-setup-windows-support`. Exploration by Codex
> rescue read-only (the restored route's first production run). Scope
> narrowed with the human: WIN-1 = the fail-open core; auto-install
> (WIN-2), delegate-on-Windows (WIN-3), and sandbox tightening (WIN-SBX)
> become sibling stories added at approval.

## Problem

Every vendored hook registration pins `/usr/bin/python3`
(`.claude/settings.json:9,19,30,39,49`; `.codex/hooks.json:9,21,32`) — a
path absent on Windows — and Claude Code treats a non-2 hook exit as
non-blocking, so on Windows every gate this week built silently disarms:
no lockout, no belt, no session context. `./forge` is sh-only with no
native shim (its `py -3` fallback is unreachable without a POSIX shell).
`forge doctor` never executes a registered hook, so the breakage is
invisible; no CI job runs Windows. Fail-open, undetected, on every client
a Windows dev touches.

## Scope / Non-goals

**In scope:** one interpreter-resolution point for all hook commands
(both runtimes); a native Windows shim for `forge`; `forge doctor`
hook-health that EXECUTES each registered hook command and reds when one
cannot run (wired into `forge next`'s first action on a broken clone);
a `windows-latest` CI job running the lockout gate tests + hook-health;
roadmap AC narrowing + the three sibling stories; a spec decomposition
note recording the split.

**Non-goals (sibling stories, not dropped):** doctor `--fix`
auto-installing Git/Python with UAC (WIN-2); `delegate.py`'s Windows
process model — `fcntl`/`ps`/`killpg`/`preexec_fn` are POSIX-only, so
delegation itself stays sh-gated until WIN-3; `.codex/config.toml`
`sandbox_mode = "danger-full-access"` tightening (WIN-SBX — own
verification, human-ruled). Vendor-integrity's `.codex/hooks.json`
hashing gap rides WIN-SBX's diff (same file family).

## Acceptance Criteria

1. Hook commands in both runtime configs resolve their interpreter
   through ONE shared point that works on macOS, Linux, and Windows
   Git Bash (`py -3` → `python3` → `python` order), and **fail closed
   within reach of a working shell**: an unresolvable interpreter exits 2
   (blocking), never 127-and-vanish. Honest limit, stated: with no POSIX
   sh at all, the hook layer cannot self-arm — detection (AC3/AC4) is the
   net there.
2. `forge.cmd` (native shim) lets cmd/PowerShell users run `forge` with
   zero setup; the sh entrypoint is unchanged for POSIX.
3. `forge doctor` gains hook-health: it loads both runtime configs,
   executes each registered command with a benign payload, and reports a
   named RED check per hook that cannot run; `forge next` on a
   hook-broken clone names `forge doctor` as its first step. `doctor
   --fast` stays cheap (existence checks only).
4. A `windows-latest` job (in the harness-internal CI, not vendored)
   runs the lockout/window/guard gate tests plus doctor hook-health
   green — proving the armed path on Windows, not assuming it.
5. Roadmap: WIN-1's ACs narrowed to this core; WIN-2/WIN-3/WIN-SBX added
   as pending siblings on the epic with the spun-out ACs; the spec's
   Decomposition section records the split (doc note, approval-time).
6. All vendored surfaces ride existing lists (`COPY_CLAUDE`,
   `COPY_CODEX`, `forge` in `COPY_FILES` — `forge.cmd` joins it);
   hygiene caps and the full suite stay green.

## Technical Approach

- **Resolution point:** hook commands become
  `sh -c '"$(git rev-parse --show-toplevel)/forge" hook <name>'` — a new
  thin `forge hook <name>` passthrough (stdin→script, exit code
  preserved) so interpreter fallback lives ONLY in the `forge`
  entrypoint, which already carries the `py -3` chain. The worker owns
  the exact form; the contract binds: one resolution point, fail-closed
  exit 2 on unresolvable, byte-identical behavior on POSIX.
- **`forge.cmd`:** a minimal batch shim delegating to Git Bash's sh when
  present, else `py -3`/`python` directly against `factory/scripts/forge.py`.
- **Doctor hook-health:** new check family in `doctor.py` executing each
  registered command with a no-op JSON payload on stdin and asserting
  exit 0/2 semantics; red rows name the hook and the failing command.
  `phase.py` prepends the doctor step when hook-health last failed
  (state via the existing doctor plumbing, not a new ledger).
- **CI:** `windows-latest` job in `factory-scaffold.yml`'s harness-only
  section (is_harness gate) — runs the focused lockout/guard selectors
  plus `forge doctor` hook-health; notes in-job which POSIX-only tests
  are skipped on Windows (skip markers, enumerated, not silent).
- **Delegated, per 0037:** one task; my hands touch plan artifacts and
  approval-time roadmap/spec notes only.

## Decisions

No new records: fail-closed hook semantics and the split execute the
confirmed spec under 0037's regime; the sibling spin-outs keep the spec
as their source. (WIN-SBX will need its own decision when it flips the
sandbox default — noted for that story, not this one.)

## Surface Impact

| Surface | Class | Notes |
|---|---|---|
| Runtime behavior | Changed | hook resolution, forge hook passthrough, doctor checks |
| API | N-A | — |
| Data/schema | Unchanged by design | no artifact changes |
| CLI/ops | Changed | forge.cmd; forge hook; doctor hook-health rows |
| UI | N-A | — |
| Docs | Changed | spec decomposition note; roadmap AC narrowing |
| Tests | Changed | hook-health + shim tests; windows CI job; enumerated skips |

## Task Decomposition

One bounded task: **FORGE-WIN-1.1 — resolution point + shim + doctor
hook-health + windows CI** (write scope: `.claude/settings.json`,
`.codex/hooks.json`, `forge`, `forge.cmd`, `factory/scripts/forge.py`,
`forge_cli/doctor.py`, `forge_cli/phase.py`, `forge_cli/scaffold.py`,
`.github/workflows/factory-scaffold.yml`, `factory/tests/test_gates.py`).

## Risks

- **Hook-command changes can brick THIS session's own gates** — the
  worker edits the live hook configs; the contract requires POSIX
  behavior byte-identical and the full suite green before the session
  continues the loop under the new commands (the story tests itself on
  us again).
- **Windows runner variance** — Git Bash exists on windows-latest, but
  `py` vs `python` availability varies; the CI job pins what it uses and
  doctor's red rows are the client-side truth.
- **Fail-open remains possible with no shell at all** — stated in AC1;
  WIN-2's installer story is the eventual answer, detection is today's.
- **dual-runtime parity check** — hook command edits must keep
  `check_dual_runtime` green (event sets unchanged; commands may differ
  in text but scripts must exist).

## Verify Plan

- Gate tests: new hook-health/shim tests + the full suite via
  `verify.py`; `check_dual_runtime`; hygiene caps.
- **Live self-test on POSIX:** after the hook-config change lands, this
  session's next product-write attempt must still DENY (lockout armed
  under the new resolution path) and a recorder must still work.
- **CI:** the PR's windows-latest job green is the story's Windows
  proof; its ubuntu jobs prove no POSIX regression.
