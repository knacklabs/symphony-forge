---
decisions_reviewed:
  - 0001-determinism-contract
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
  - 0046-scoped-layout-activation-ordering
  - 0047-task-level-worktree-and-pr
---

# Plan: Upgrade preserves and truthfully reports doc-contract overwrites

Story: `upgrade-preserves-doc-contracts` · Spec: `docs/specs/legacy-upgrade.md` · Issue: GitHub #112

## Problem

`cmd_upgrade` copies every `DOC_CONTRACTS` entry (11 harness doc files, incl.
`docs/architecture/README.md`, defined `scaffold.py:38`) into the client with
`shutil.copy2`, wholesale (`upgrade.py:527-533`). The completion report
(`upgrade.py:712-717`) says only `", doc contracts"` under **Replaced** and lists
the contracts' parent dirs (`docs/architecture/`, `docs/product/`,
`docs/decisions/`, `docs/context/`, `docs/specs/`) under **"Untouched
(project-owned)"** via `PROJECT_OWNED`. A client that appended project content to
a contract file has it overwritten while the summary reports that directory as
left alone. Issue #112 records a real upgrade (`8f1d053 → 689563a`) that replaced
a 26-line project HLD-index in `docs/architecture/README.md` (51 → 25 lines) with
the report saying the dir was untouched — invisible unless the operator diffs
that exact file by hand.

## Scope / Non-goals

**In scope:** truthful reporting (name the replaced contract paths; stop implying
their dirs are fully untouched); a divergence **warning** that names any contract
whose client file differs from the new template and points the operator at `git
diff` before committing.

**Non-goals (rejected in the requirements grill and the plan review):**
- *`.orig` (or any) backup file* — redundant and bloat-prone. `forge upgrade`
  requires a clean target tree (the dirty-gate; only `--force` bypasses it), so
  the client's prior contract content is already committed and recoverable via
  `git diff` / `HEAD`. A `.orig` per contract on every upgrade would add up to 11
  transient files (committed = repo bloat; gitignored = clutter) to re-store
  content git already holds. The warning + git is leaner and loses nothing in the
  clean-tree case. (`--force` on a dirty tree already caveats "uncommitted files
  were not searched" — the operator's explicit risk.)
- *Marked project-block merge* (issue #3) — deferred; needs a delimiter
  convention across all 11 contracts + template edits.
- *Agent/LLM reconciliation inside upgrade* — breaks the deterministic,
  auditable, companion-free vendoring contract; a separate opt-in follow-up if
  wanted.

## Acceptance Criteria

From the roadmap story `upgrade-preserves-doc-contracts`:
1. The upgrade report names each replaced doc-contract destination path, and no
   longer implies a directory whose contract file was overwritten is fully
   untouched.
2. When a client's doc-contract file differs from the new template, the upgrade
   names it and warns — pointing the operator at `git diff` (prior content is
   committed; upgrade requires a clean tree) — so divergence is never reported as
   "untouched"; no backup files are created.
3. Regression test: upgrading a client whose doc-contract README differs from the
   template names it replaced and emits the divergence warning, while an identical
   unedited file is not warned and no `.orig` files appear.

## Technical Approach

**Divergence detection** — in the `DOC_CONTRACTS` loop (`upgrade.py:527-533`),
per contract whose `src` exists:
- Append `dst_rel` to `replaced_contracts`.
- If `dst.is_file() and not dst.is_symlink()` **and** `dst.read_bytes() !=
  src.read_bytes()`: append `dst_rel` to `diverged_contracts`.
- Only a **regular file** is read/compared. A symlink or non-file at the contract
  path is an unexpected topology (the `repository-escape` recurring class on this
  file) — `read_bytes()` follows a link, so the guard keeps the compare from
  reading outside the target, per the `never-resolve-client-paths-through-the-worktree`
  lesson. No new write and no `.orig` is added, so the copy path is unchanged.

**Truthful report** (`upgrade.py:712-717`):
- Drop `", doc contracts"` from the generic "Replaced" line; add a dedicated line
  `Replaced doc contracts: <sorted replaced_contracts>`.
- Append to the "Untouched (project-owned)" line a qualifier so the doc dirs no
  longer imply their contract file was untouched (e.g. `(doc-contract files in
  these dirs are harness-owned — see "Replaced doc contracts" above)`).
- If `diverged_contracts`: print a `WARNING:` naming each, and directing the
  operator to `git diff <path>` before committing — their prior version is in git
  (clean-tree required); move any project-specific content into a project-owned
  sibling file (the issue #112 workaround).

Comparison baseline = the new shipped template (`src`). Because there is no
backup file, an unedited client whose contract the harness legitimately updated
sees only an informative warning line ("differs from your version — review `git
diff`"), which is a correct and useful thing to say about a harness doc update —
not bloat.

## Decisions

**No new decision records** (operator-confirmed). The deterministic detect +
truthful-report + git-as-backup approach *implements* the confirmed
`legacy-upgrade.md` spec ("one command, no residue"; "the migration modifies no
project-owned file" silently; "stale references reported, never rewritten") and
adds no writes, so the **Path Boundary Invariant (0028)** is honored by the
read-guard alone. The design forks — backup vs preserve-in-place vs agent-merge,
compare-vs-new-vs-old template, and `.orig` vs git-as-backup — were put to the
operator and resolved in the recorded requirements grill and the plan review.
Rejected alternatives: status-quo full overwrite (the bug); preserve-in-place
(client silently misses harness updates); agent-merge (breaks
determinism/auditability); `.orig` backup (redundant with git, bloat-prone).

## Surface Impact

| Surface | Class | Note |
|---|---|---|
| runtime behavior | Changed | upgrade now reads each contract to detect divergence; copy behavior itself unchanged; no new files written |
| CLI / ops | Changed | completion report names replaced contracts, qualifies "Untouched", and warns on divergence pointing at `git diff` |
| API | Unchanged by design | no signatures change; all internal to `cmd_upgrade` |
| data / schema | N-A | no persisted schema touched |
| docs | Unchanged by design | `DOC_CONTRACTS` set and spec intent unchanged; only report/behavior |
| tests | Changed | new regression test in `factory/tests/test_gates.py` |
| UI | N-A | CLI tool, no UI |

No `Deferred` rows (non-goals are scoped out in §2, not deferred surfaces).

## Task Decomposition

**Single task** (bounded, one disjoint write scope — detection and report are one
coherent change to `cmd_upgrade`):

- **T1 · upgrade-doc-contract-safety** — `upgrade.py`: divergence detection +
  truthful report + warning; `factory/tests/test_gates.py`: the regression test.
  - `write_scope`: `factory/scripts/forge_cli/upgrade.py`,
    `factory/tests/test_gates.py`
  - traces to AC 1, 2, 3.

## Risks

- **Read follows a symlink** at a contract path (`repository-escape` RECURRING x3
  @ `upgrade.py`): mitigated by the `is_file() and not is_symlink()` guard before
  `read_bytes()`; no write is added, so there is no `.orig` escape surface.
  **TRIPWIRE (decision 0005):** if autoreview flags `repository-escape` or
  `reviewed-separately` again on this change, escalate per WORKFLOW.md Recurring
  Findings — do not patch a fourth time.
- **`--force` on a dirty tree**: uncommitted contract edits are overwritten and
  not in git. Out of scope — the existing `--force` report caveat ("uncommitted
  files were not searched") owns this; the divergence warning still fires for
  committed-but-diverged contracts.
- **Test portability**: honor the `fake-os.name` lesson — the test uses a real
  `tmp_path` client, never monkeypatches `os.name`.

## Verify Plan

- New `factory/tests/test_gates.py` test: build a tmp client where
  `docs/architecture/README.md` differs from the template and a second contract
  is byte-identical to it; run the upgrade path; assert (a) the report lists both
  under "Replaced doc contracts", (b) the divergence WARNING names the edited
  contract and not the identical one, (c) no `.orig` file exists anywhere under
  the client.
- `python3 factory/scripts/verify.py` (runs the gate suite).
- `python3 factory/scripts/check_dual_runtime.py` clean.
- Manual: the completion report no longer lists a replaced contract's directory as
  unqualified "Untouched (project-owned)".
