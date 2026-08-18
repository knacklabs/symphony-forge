---
issue: FORGE-CFS-1
title: Story state stops conflicting across PRs
status: approved
saved: 2026-08-15T14:17:54+00:00
story: FORGE-CFS-1
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
  - 0040-windows-user-scope-first-elevation-deferred
  - 0041-sandboxed-workers-default
  - 0042-psutil-cross-platform-process-model
  - 0044-accountable-engineering-loop
  - 0045-conflict-free-story-state
---

# FORGE-CFS-1 story plan — Story state stops conflicting across PRs

(Authored in plan mode 2026-08-15 after the operator's pre-draft rounds: existing `.factory/history/` stays read-only legacy; the worktree-local run pointer lives at `.git/forge/run.json`. Runs in parallel with the approval-integrity story; operator chose gates-first landing, so this branch rebases once over that story's new gate fields before its own PR.)

## Problem

Every pair of overlapping story PRs conflicts by construction (decision 0045's evidence: PR #104/#107 needed two hook-wedge recoveries, human-run resolutions, and an ours-strategy merge). Causes: singleton evidence files every story rewrites; `pr_ready`'s archive move inviting rename detection; `events.jsonl` behind an unversionable union driver; hooks that crash on conflicted state and refuse the git-native commands that would resolve it.

## Scope / Non-goals

**In scope (spec `conflict-free-story-state`, confirmed; decision 0045, accepted):** story-scoped evidence under `.factory/stories/<KEY>/…` from intake onward; `pr_ready` ships in place (no archive move); one event per file replacing `events.jsonl` appends; worktree-local active-story pointer at `.git/forge/run.json` with phase derived from story artifacts; auto `roadmap heal` after merges in `forge next`; the mid-merge hook carve-out (git-native resolution of exactly the unmerged paths; static deny-list fallback when `factory_lib`/state is unparseable); migration at next intake; `forge upgrade` carries it to clients.

**Non-goals:** rewriting `.factory/history/` (read-only legacy, operator round); roadmap.json stays a single file; no new merge drivers; the approval-integrity story's gate fields (rebase over them at landing, don't implement here).

## Acceptance Criteria

The six recorded roadmap ACs (zero overlapping paths for concurrent stories + conflict-free merge simulation; in-place `pr_ready` with history readable; per-event files with legacy reader; worktree-local pointer with no tracked run.json authority; auto-heal after merge; hook carve-out + deny-list fallback), with the two operator pre-draft choices binding the design.

## Technical Approach

- **Story-scoped paths (`factory_lib.py` path helpers):** one `story_dir(root, key)` helper; recorders, gates, `task_frontier_state`, board, and `pr_ready` resolve task-scoped artifacts through it. New stories write `.factory/stories/<KEY>/…`; readers fall back to legacy locations (live singletons and `history/`) for existing data.
- **Run pointer (`.git/forge/run.json`):** intake writes the pointer beside the existing protected authority (same `git_control_dir` helpers); phase state derives from the story dir's artifacts; the tracked `.factory/run.json` is no longer written for new stories (kept readable for legacy).
- **Events (`events.py`):** `append_event` writes `.factory/stories/<KEY>/events/<ts>-<slug>.json` (0022 pattern, like lessons); `forge history` and the board read both formats; the union-driver dependency is dropped from docs.
- **In-place ship (`pr_ready.py`):** mark shipped inside the story dir; no moves — rename-detection strands die; roadmap done-flip unchanged.
- **Auto-heal (`phase.py`):** `forge next` detects a merge commit at HEAD with roadmap divergence and runs the heal before routing.
- **Hook carve-out (`pre_tool_use.py`):** when the index has unmerged entries, permit `git checkout --ours/--theirs`, `git rm`, `git add` scoped to exactly those paths (still refusing content hand-writes); wrap the hook's imports/state reads so an unparseable `factory_lib` or state file engages a minimal static deny-list instead of crashing (lessons: factory-merge-resolution-needs-a-path, the #104 wedge).
- **Migration + vendoring:** next `intake` on a legacy repo starts the new layout without touching old artifacts; `forge upgrade` ships the change to client repos.

Reuse: `git_control_dir`/protected-state helpers, per-record lessons layout, `roadmap heal`, repo-kind classification.

## Decisions

- Operator rounds recorded: read-only legacy history; `.git/forge/run.json` pointer. Everything else derives from spec + 0045 + 0022. No new decisions expected.

## Surface Impact

| Surface | Class | Notes |
|---|---|---|
| Runtime behavior | Changed | recorders/gates write story-scoped paths; pr_ready ships in place; hook carve-out |
| API | N-A | none |
| Data/schema | Changed | story-dir layout, per-event files, untracked run pointer; legacy layouts stay readable |
| CLI/ops | Changed | forge next auto-heal; no new commands |
| UI | Changed | board reads both layouts |
| Docs | Changed | WORKFLOW evidence-layout section, degraded-mode notes, 0022 cross-reference |
| Tests | Changed | merge-simulation test, dual-layout readers, carve-out matrix |

## Task Decomposition

Skeletal, readable ids, contracts JIT:

1. **story-scoped-evidence** — path helper + recorders/gates write and read the story dir with legacy fallback.
2. **run-pointer-untracked** — `.git/forge/run.json` pointer; phase derives from artifacts; legacy read path.
3. **per-event-files** — event writer + dual-format history/board readers.
4. **ship-in-place** — pr_ready without moves; board/history read shipped story dirs.
5. **merge-survivable-hooks** — unmerged-path carve-out + deny-list fallback + auto-heal routing.
6. **migration-and-vendor** — intake cutover on legacy repos; forge upgrade carry; docs sweep; the merge-simulation gate test proving two concurrent stories produce zero overlapping `.factory` paths.

## Risks

- **Blast radius:** every recorder and gate touches paths — the story-scoped helper must be the ONLY resolution point or layouts fork. Reviewer focus on single-source path resolution.
- **Parallel story:** approval-integrity adds fields to files this story relocates; gates-first landing (operator round) means one rebase here before PR.
- **Hook carve-out safety:** scoped strictly to unmerged index paths; a carve-out that leaks to merged paths would reopen the write lock — the test matrix must prove refusal outside the unmerged set.
- **Self-application:** this story's own mid-flight state lives in the old layout until the cutover task; intake-time migration is deliberately the LAST switch flipped.

## Verify Plan

- Per-task selections; full `verify.py` at closeout; `check_dual_runtime.py` throughout.
- The merge-simulation test: two fixture stories recorded concurrently in sibling worktrees merge into one base with zero `.factory` conflicts.
- Carve-out matrix: with a synthetic unmerged index, git-native resolution passes for exactly those paths and refuses others; broken `factory_lib` engages the deny-list fallback instead of crashing.

## Implementation Assumptions

<!-- Made during implementation, NOT part of the approved plan. Dev: review these before merge; promote any that matter to docs/decisions/. -->
- 2026-08-15: A story directory created by intake is the marker for story-scoped writes; without it, an active legacy story continues using live singletons.
