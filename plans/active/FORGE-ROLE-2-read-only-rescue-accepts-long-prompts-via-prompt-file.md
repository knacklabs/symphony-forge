---
issue: FORGE-ROLE-2
title: Read-only rescue accepts long prompts via prompt-file
status: approved
saved: 2026-08-12T18:02:33+00:00
story: FORGE-ROLE-2
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

# FORGE-ROLE-2 — Read-only rescue accepts long prompts via prompt-file

## Problem

The companion guard (`factory/scripts/pre_tool_use.py`,
`_companion_readonly_launch_ok()` at :576) admits direct read-only
companion calls for verbs {status, task, task-resume-candidate} with flags
{--model, --effort, --json} only; `--prompt-file` is explicitly
default-denied (:594-603). Real exploration briefs are multi-paragraph;
inline argv can't carry them and heredoc wrapping is (rightly) refused as
shell-shaped. So the anytime read-only rescue contract holds only for
short prompts — found dogfooding FORGE-WIN-1 exploration. The companion
runtime already parses `--prompt-file`; only the guard refuses the route.

## Scope / Non-goals

In scope: `factory/scripts/pre_tool_use.py` (guard admission +
containment), `factory/tests/test_gates.py` (extend the three guard tests,
keep regressions). Live verification of the file route by the
orchestrator after implementation.

Non-goals: no write-path change (delegate untouched); no companion-runtime
change (it already parses the flag); no plugin-file edits (installed user
state — the rescue agent already forwards runtime flags); no new verbs
(the observed `result`-verb denial is ledgered as a deferral, not scope).

## Acceptance Criteria

- The guard admits `node … codex-companion.mjs task … --prompt-file <path>`
  in the read-only lane ONLY when: verb is `task`, the flag has exactly one
  value, and the value is a repo-relative path to an existing regular file
  whose fully resolved target stays below the resolved repo root.
- Refused: absolute paths, `..` traversal, dangling paths, directories,
  symlinks resolving outside the repo, duplicate/missing values, the flag
  on `status`/`task-resume-candidate`, and every currently-refused shape
  (shell syntax, wrappers, write flags) — regressions stay green.
- A multi-paragraph brief reaches Codex read-only through the file route,
  live-verified end to end.
- Full gate suite green.

## Technical Approach

1. `pre_tool_use.py`: replace the explicit `--prompt-file` default-deny
   (:594-603) with task-verb-only admission inside
   `_companion_readonly_launch_ok()`: consume exactly one value, validate
   containment (existing regular file; `Path.resolve()` under
   `root.resolve()`; internal symlinks acceptable under resolved
   containment). Every failure mode falls through to the existing refusal
   message so nothing gets quieter.
2. `test_gates.py`: extend `test_hook_allows_readonly_companion_task_launch`
   (:4820) with the valid prompt-file shape; convert the prompt-file case in
   `test_hook_denies_file_and_cwd_overrides_in_readonly_lane` (:12674) into
   the containment matrix (absolute, traversal, external symlink, dangling,
   directory, duplicate value, wrong verb); keep
   `test_companion_guard_admits_read_only_and_refuses_write_shapes` (:4593)
   and the laundering/wrapper/expansion regressions (:4760, :12710, :12726)
   intact.
3. After the stage lands: orchestrator live-verifies by writing a
   multi-paragraph brief file and running the direct read-only
   `task --prompt-file` invocation; the result is recorded in the automated
   testing artifact summary.

## Decisions

No new decision record: this implements the boundary decision 0037 already
draws (read-only direct calls pass; writes route to delegate), narrowing a
default-deny to a validated admission. Deferral to ledger: the companion
`result` verb is not allowlisted, so fetching a completed run's output
falls back to log-tailing — revisit when it next bites.

## Surface Impact

One guard function gains a validated flag; no CLI surface, schema, or
client-repo change. Vendored `pre_tool_use.py` reaches clients on the next
`forge upgrade` vendoring cycle as usual.

## Task Decomposition

One bounded task, ROLE2-T1 (see recorded decomposition): guard admission +
test matrix land together; the live verification is an orchestrator step
after the stage, not a second task.

## Risks

- Containment subtleties (symlinked repo root on macOS /tmp, resolved vs
  lexical paths): mitigated by resolving BOTH sides and comparing with
  `Path.is_relative_to`; the test matrix pins each failure mode.
- Guard loosening regression risk: every admission is task-verb-scoped and
  value-validated; the refuse-everything-else structure is unchanged, and
  the existing refusal tests must stay green unmodified.
- The plugin's rescue agent may not forward `--prompt-file` until its next
  release: the guard change still unblocks direct invocations (the
  documented fallback), so the story's contract is satisfiable now.

## Verify Plan

- `uv run --with pytest python -m pytest factory/tests/test_gates.py -q -k
  "companion or readonly_lane"` for the focused matrix;
  full suite + `verify.py` before review.
- Live check: direct read-only `task --prompt-file <multi-paragraph brief>`
  invocation succeeds and the same argv with a traversal path is refused.
