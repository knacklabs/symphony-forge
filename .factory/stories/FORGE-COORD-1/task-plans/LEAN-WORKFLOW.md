---
story: FORGE-COORD-1
task: LEAN-WORKFLOW
title: Native Plan Mode approval, narrowed delegation, proof reuse, and Lean migration
status: draft
design_review: required
design_review_rationale: "Lean changes approval authority, permission and hook enforcement, migration and deletion behavior, public CLI, evidence schema/state receipts, and lifecycle state boundaries; the design must be reviewed before execution."
source_worktree: /Users/dev/Workdir/symphony-forge-native-dogfood-FORGE-COORD-1-LEAN-PLANNING
source_head_observed: 6ae2dea1b7417fff4c9c3fc3552488a8378aacd4
recovery_plan: /Users/dev/.codex/plans/symphony-forge+coord-1-recovery-lean-and-legacy-removal+20260912T192559IST.md
decisions_reviewed:
  - 0001-determinism-contract
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
  - 0048-plan-mode-and-grill-provenance
  - 0050-plan-authoring-is-mode-agnostic
  - 0052-approval-to-pr-is-the-agents
  - 0053-interchangeable-coordinator-shared-forge-contract
  - 0054-native-questions-and-task-proof
  - 0055-enforced-static-quality-baseline
  - 0056-staged-quality-baseline-rollout
  - 0057-coordinator-operation-simplification
  - 0058-bounded-native-bootstrap-support
  - 0059-task-owned-jit-workspaces
  - 0060-child-signal-mask-restoration
  - 0061-host-native-human-interaction
  - 0063-first-native-task-workspace-bootstrap
  - 0064-lean-delivery-and-durable-history
  - 0065-ci-platform-evidence
  - 0066-closeout-binds-to-the-diff
  - 0067-rounds-rebind-to-their-gate
  - 0068-worker-commands-may-reach-the-network
  - 0069-combined-review-generation
  - 0072-staged-platform-proof
  - 0073-grill-round-reuse-and-empty-frontier-coexist
  - 0074-user-selects-main-orchestrator-model
---

## Problem

`LEAN-WORKFLOW` is the second PR in the approved three-PR recovery sequence. After `NATIVE-FOREGROUND-ACTIVATE` lands, Forge still makes a coordinator repeat ceremony that should be native to Plan Mode: separate requirements grills, minimum human grill rounds, manual plan/task approval commands, board-based approval instructions, a second unchanged plan save, and repeated proof/review work when every input is unchanged. The result is slow and brittle: approved work asks again, workers cannot take narrower bounded retries, and old formats remain executable in normal runtime.

Lean must install the simpler workflow for both Claude and Codex without weakening Forge's real gates. A plan is authored in native Plan Mode, cold-grilled once, repaired against repository facts, shown exactly, approved through the host's native approval path, recorded by one shared approval recorder, and then allowed to continue through the existing task lifecycle. Lean also owns repeatable narrowed delegation, content-bound reuse of successful proof, the committed hook/profile changes named in the recovery plan, and the one-time migration for the formats Lean removes.

There is one branch-owned post-merge failure in scope. `.github/workflows/pr-link.yml` now reads `load_events()` and `forge pr-link` writes `.factory/events/<id>.json`, but the workflow still stages `.factory/events.jsonl`. That left the already-merged `FORGE-CFS-1` and `FORGE-ACC-3` stories without durable `pr-linked` events on main. Read-only evidence shows `FORGE-CFS-1` shipped in GitHub PR `knacklabs/symphony-forge#109` and `FORGE-ACC-3` shipped in `knacklabs/symphony-forge#110`; Lean must repair the workflow and backfill only those verified links through `forge pr-link`, never by hand-writing event JSON or inventing provenance.

## Scope / Non-goals

In scope:

- Native Plan Mode approval for story and task plans across Claude and Codex, using one shared approval recorder with thin runtime adapters. This overrides older Decisions 0029, 0054, and 0061 only for the exact approved recovery path; no new decision is introduced. The recorder derives exactly one eligible awaiting story/task artifact from the current frontier, binds the consumed event to runtime, stable session/event identity, plan kind/story/task, and current digest, and atomically refuses zero candidates, multiple candidates, replay, or missing stable identity.
- Removal from the normal flow of the separate requirements grill, minimum grill-round counts, fake closure questions, old round ledgers as authority, manual story/task approval commands, board-based approval instructions, and second unchanged plan save. This conflicts with older spec42/Decision 0073 Shared wording and current old-round tests; the approved recovery PR2 explicitly removes them, so Lean proves one independent cold grill plus full finding disposition without compulsory human rounds or frontier fake while preserving cold-read/finding-disposition proof. Anti-loop binding: cold proof binds the exact original input it reviewed; ordered one-to-one finding/resolution/source dispositions plus explained amendments bind that cold input to the final artifact digest; final human approval binds the final digest. The completed requirements cold-read adds three exact dispositions to that bridge: strengthen context snapshot security with same-user access and native Windows DACL proof; define independent migration coverage with a separate raw no-follow directory-entry walk and exact once classification comparison; qualify preservation with clean-target dirty refusal, no `--force` bypass, project-owned settings/profile preservation, and byte/hash-matching Forge-owned replacement only. Never claim the cold reader saw amended bytes, never require a second cold model call solely because resolving findings changed them, and refuse any unexplained out-of-disposition change. No synthetic closing question, silence, or agent-set `frontier_empty` grants authority; an empty map is valid only when there were no findings. Substantive signoff, epic, and human approval gates remain.
- One authored task brief shape carrying objective, acceptance criteria, capability boundary, public API/data changes, and security/migration/rollout decisions.
- `./forge delegate <task-id> --scope <repo-path> [--scope <repo-path> ...]`, where every supplied scope is a proper subset of the effective approved `write_scope`, is stored in the existing delegation `write_scope`, is bound into brief/launch identity, and is enforced by hooks. A single approved file path is a valid subset member; omitting `--scope` keeps the full approved effective scope.
- Content-bound close reuse for successful tests, `verify.py`, and selected review with proof-type-specific identity stored in existing stage state per the approved recovery plan/task contract: tests bind product bytes plus exact test command, selectors, test configuration, and tool versions; verify binds product bytes plus verify argv, config, tool versions, and generated semantic inputs; selected review keeps Decision 0066's stamp-token delta binding but must also match the current reviewed-meaning identity: approved semantic task-brief digest, effective acceptance/security/migration semantics, substantive automated evidence, review instructions/helper/config, and product delta.
- Committed hook/config changes only: Claude PreToolUse `Bash`, edit tools, `AskUserQuestion`; Claude PostToolUse `AskUserQuestion` and successful `ExitPlanMode`; Codex PreToolUse `Bash`, `apply_patch`, synchronous `request_user_input`; Codex PostToolUse synchronous `request_user_input`; `.codex/config.toml` replaces `codex_hooks = true` with `hooks = true`.
- Profile cleanup: retain only `.codex/agents/planner-high.toml`, `.codex/agents/docs-decomposer.toml`, and `.codex/agents/functional-checker.toml`; delete the 12 harness-owned profiles named in the recovery plan and remove their registry entries while preserving client-added profiles during upgrade. This conflicts with older accepted Decision 0074 text and older active-plan/test expectations, but the user later explicitly instructed the coordinating thread to override earlier decisions and approved the recovery PR2 exact three-profile target; that direct later instruction controls this task contract.
- One-time `forge upgrade` migration for the formats Lean removes: requirements and plan grill records, grill-round ledgers, embedded task approvals, story approval markers, fixed lens proof, legacy stage stamps, old hook flag, and current 15-agent installation state. The migration requires a clean target before any write; `--force` cannot bypass this migration's dirty-tree refusal, so dirty state is preserved by zero-write refusal.
- Normal-runtime deletion of readers, writers, schemas, commands, tests, and docs for the Lean-replaced formats after the migration validates and reads back current outputs, including PR2-owned ceremony-target, grill-round, plan-mode-marker, requirements-grill, manual-approval, direct fixed-proof fallback, and closeout proof-authority surfaces. Independent migration coverage is mechanical: the primary pass uses the per-family migration discoverers/classifiers, while the second pass is a separate no-follow raw directory-entry walk over fixed legacy roots/exact parents that does not call or reuse those discoverers or classifiers; it emits normalized path/type/identity for every entry, requires each raw candidate classified exactly once, and compares count, classifications, and digest under the same exclusion before writes or pointer commits.
- The `pr-link.yml` supported current per-event staging repair and verified recorder-generated backfill for `FORGE-CFS-1 -> knacklabs/symphony-forge#109` and `FORGE-ACC-3 -> knacklabs/symphony-forge#110`, only so current board CI becomes honest before Portable migrates the event family.

Out of scope:

- Reimplementing Decision 0069 combined-review generation. First owns it; Lean consumes selected proof and only adds reuse/migration behavior around it.
- Native background lifecycle, detached helpers, cancellation/status/resume/explore, structured logs, and process-tree recovery. `NATIVE-LIFECYCLE` owns those.
- Structured-question identity expansion beyond the completed synchronous events needed for Lean approval. `SHARED-COORDINATOR-JOURNEY` owns broader question identity; the approved recovery PR2 overrides older empty-frontier and compulsory-round proof as normal-flow requirements for this task.
- Later Native and Shared capabilities stay with their existing owners. Lean and the amended Portable PR3 must not mark them complete, import them as prerequisites, or use them to justify widening this task.
- The pending recovery chain after First is `LEAN-WORKFLOW -> PORTABLE-DELIVERY-MIGRATION -> NATIVE-LIFECYCLE -> SHARED-COORDINATOR-JOURNEY -> FORMAT -> QUALITY -> INTEGRATION`. Amend existing rows only: Portable depends on Lean, Native depends on Portable, Format depends on Shared, and Shared/Quality/Integration keep their existing dependencies otherwise. After PR3, the recovery program is complete but `FORGE-COORD-1` remains active with five pending skeletal future tasks; none of those future rows becomes PR3 scope.
- Repository-wide legacy layout migration and fallback removal that PR3 owns: root story singletons, tracked `.factory/run.json`, aggregate stages, the full event family (`.factory/events/<id>.json`, `.factory/events.jsonl`, and any historical bundles) into one append-only event log per story, `plans/quickfixes.jsonl`, `plans/lessons.jsonl`, old history layouts, broad missing-field compatibility, old `.agents` runtime references, native argv/continuation compatibility, old `stage start --trunk`, and normal-runtime `run forge upgrade` refusal for all remaining old data. PR3 remains the existing pending `PORTABLE-DELIVERY-MIGRATION` row, amended in place and moved immediately after `LEAN-WORKFLOW`; do not create a new task, PR, or decision. Lean may touch `factory/scripts/forge_cli/audit.py` only for Lean-owned audit signals around removed ceremony/proof formats, not for PR3's broad compatibility audit. Fixed-review migration, normal fixed-file fallback retirement, the candidate-universe/lock/safety/publication path, and harness-owned profile pruning transfer into Lean once; Portable owns only the other remaining legacy families and preserves the resulting three-profile Forge registry plus client-modified and client-added profiles. Old `.agents` relocation must never reinstall the retired twelve Forge-owned profiles.
- Fabricating or marking `predates_outcome_contract` for `FORGE-CFS-1` or `FORGE-ACC-3`. Those stories have real merged PR evidence, so the only permitted repair is a verified `forge pr-link`.
- Changing global Claude or Codex user configuration.
- External client rollout. That remains later in the recovery sequence.

## Acceptance Criteria

1. Native approval is the normal path: a story or task plan can be authored in native Plan Mode, cold-grilled once, corrected for repository-answerable findings, displayed exactly, approved in native Plan Mode, recorded with the exact digest, and continued without the second unchanged save or manual `plan approve` / `task approve` command in the ordinary flow.
2. Claude and Codex approval adapters share one recorder and one digest model. Claude accepts only successful `ExitPlanMode`; Codex accepts only the exact synchronous `Approve plan / Request changes / Stop` approval question. The recorder derives exactly one eligible awaiting story/task artifact from the current frontier and binds the consumed event to runtime, stable session/event identity, plan kind/story/task, and current digest. Zero candidates, multiple candidates, replay, missing stable completion/event identity, stale digests, cancellation, wrong runtime, async acknowledgements, unsupported payloads, and ordinary optional clarification events refuse. Attribution is `human-via-Claude` or `human-via-Codex` plus runtime/session/event identity; the implementation must not invent a display name.
3. The separate requirements grill, minimum round floors, forced closure questions, board-based approval instruction, and fake `frontier_empty` questions disappear from normal runtime. Cold-reader findings still require explicit disposition, and material human choices still use the host-permitted channel. Cold proof binds the exact original input it reviewed; ordered one-to-one finding/resolution/source dispositions plus explained amendments bind that cold input to the final artifact digest; final human approval binds the final digest. Never claim the cold reader saw amended bytes, never require a second cold model call solely because resolving findings changed them, and refuse unexplained out-of-disposition changes.
4. `./forge delegate <task-id> --scope ...` can narrow a write launch to proper subsets of the effective approved scope, records that narrowed scope in the existing delegation `write_scope`, binds it into launch identity/brief, and hook admission refuses writes outside the narrowed scope. Selecting an approved exact file path is valid; omitting `--scope` keeps the full approved effective scope. It creates no second scope ledger.
5. Tests, verification, and selected review reuse only when their own content-bound identity proves every relevant input for that proof type is unchanged. Tests rerun for changed product bytes, test command, selector, test config, or test tool version. Verify reruns for changed product bytes, verify argv, verify config, verify tool version, or generated semantic input. Selected review remains Decision 0066 stamp-token delta-bound, but its selected generation must still match the current reviewed-meaning identity: approved semantic task-brief digest, effective acceptance/security/migration semantics, substantive automated evidence, review instructions/helper/config, and product delta. Changes to any reviewed-meaning component force review; only explicitly canonicalized recorder bookkeeping and timestamps may reuse while preserving immutable original input/raw provenance.
6. The one-time Lean migration refuses before writing unless the target checkout is clean and the complete inventory is unambiguous, well-formed, non-linked, non-partial, non-conflicting, hash-bound, and mechanically covered. `--force` cannot bypass this migration's dirty-tree refusal; dirty state is preserved by zero-write refusal. The primary pass uses the per-family migration discoverers/classifiers. The second pass is a separate no-follow raw directory-entry walk over fixed legacy roots and exact parents; it does not call or reuse those discoverers or classifiers, emits normalized path/type/identity for every entry, requires each raw candidate classified exactly once, and compares count, classifications, and digest under the same exclusion before writes or pointer commits. It builds current outputs in a temporary area, validates them, publishes and reads them back, installs the new runtime, records `.factory/migrations/lean-workflow-v2.json`, and only then deletes migrated old artifacts. Byte-identical retry passes; unequal partial retry refuses.
7. Active old review proof requires a fresh combined review. Sealed fixed-lens proof may become `origin=upgrade` selected proof only when exact source hashes and marker/sealed identity are preserved and the independent raw coverage pass matches the primary classification universe. Normal runtime never falls back to fixed lens files after Lean migration.
8. Hook/config/profile state matches the recovery plan: committed Claude/Codex hook matrices are tested, `.codex/config.toml` uses `hooks = true`, `codex_hooks = true` is gone, only the three retained Forge-owned custom agents remain, and upgrade preserves project-owned settings outside the exact harness inventory, all client-added profiles, and client-modified same-name profiles. It deletes or replaces only byte/hash-matching known Forge-owned installed files. Unknown, mixed, or hash-mismatched same-name rows classify as preserved or invalid explicitly, never silently overwrite. This later recovery instruction is the narrow exception to old Decision 0074 same-name refresh.
9. `pr-link.yml` stages the actual current per-event file(s) produced by `forge pr-link`, updates the `[skip ci]` comment/status description from `events.jsonl` to current per-event `.factory/events/`, keeps the same same-repo/workflow-run/scaffold-check guard, and makes no claim to own the later canonical per-story event-log migration.
10. The branch backfills only the two verified missed links by running the existing recorder command: `./forge pr-link FORGE-CFS-1 knacklabs/symphony-forge#109` and `./forge pr-link FORGE-ACC-3 knacklabs/symphony-forge#110`. The resulting per-event files are generated recorder output, not hand-authored JSON. After those links, `python3 factory/scripts/check_board_complete.py` no longer fails on these two stories. The separate `forge project audit` pending-story spec gaps remain outside Lean.
11. Normal runtime no longer accepts Lean-removed data shapes. Unmigrated Lean-era old formats print one action: run `forge upgrade`. PR3-owned legacy families still use their existing compatibility until PR3.
12. All documentation and prompt text agree with the implemented runtime. Long canon is not duplicated into `AGENTS.md`; docs point to canonical contracts.

## Technical Approach

Recommendation: keep this as one `LEAN-WORKFLOW` task with staged acceptance checkpoints, not split it into many micro-tasks. The recovery plan explicitly assigns the cross-cutting approval/migration/runtime cleanup to Lean, and splitting inside the task would duplicate the same approval, hook, migration, and proof-reuse surfaces. The scope is large but bounded by named files and staged required tests. The finalized legacy audit adds the PR2-owned ceremony, audit, closeout, round-schema, plan-marker, regrill-scope, and getting-started surfaces because they directly own the formats Lean removes or the user-facing instructions Lean changes.

The implementation should reuse existing seams rather than invent a new authority system:

- Approval records continue to live in story-scoped protected evidence; only the producer changes from manual commands to native approval adapters.
- `factory/scripts/forge_cli/approval.py` owns the shared approval recorder/module so Claude and Codex adapters cannot drift. It owns current-frontier eligibility, event consumption, replay refusal, and human-via-runtime attribution.
- Delegation narrowing reuses the existing task `write_scope`, delegation row, brief composition, launch identity, and hook admission checks.
- Close reuse stores proof-type-specific receipts in existing stage state with refusal reasons rather than adding a standalone cache service or new proof schema.
- Migration lives under `forge upgrade` because that is already the one-time compatibility boundary for clients and old state.
- `forge pr-link` remains the sole event writer for PR links.

### Workflow

1. Start only after `NATIVE-FOREGROUND-ACTIVATE` is merged to trunk, post-merge checks are green, and `LEAN-WORKFLOW` is the active frontier from `./forge next`.
2. Re-record the `LEAN-WORKFLOW` task contract with the write scope, required tests, verification commands, reviewer focus, amended objective, and the twelve acceptance criteria / plan contracts below. Preserve only task id, title, dependency on First, and `user_facing: false`; the objective and acceptance criteria change now to carry the full recovery PR2 scope.
3. Run the task grill against this plan and the current worktree. Any finding that changes write scope, acceptance criteria, security boundary, migration behavior, or task order requires amendment and re-approval before delegation.
4. Stage A implements native approval flow and hook/config changes. It proves exact current-frontier eligibility, zero/multiple-candidate refusal, replay refusal, stable runtime/session/event identity binding, missing-identity fail-closed behavior, stale/wrong/canceled/async refusal, human-via-runtime attribution, and successful Claude/Codex approval recording the same digest.
5. Stage B implements narrowed delegation, hook enforcement, and the mandatory `--context-file` boundary. It proves proper-subset validation, exact approved file selection, no-flag full effective scope, launch identity binding, brief rendering, write denial outside narrowed scope, and secure context-file handling. The context snapshot security invariant is read/write/delete accessible only to the effective current user and the launched same-user process: POSIX proves owned directory/file, `0700`/`0600`, and no links; native Windows proves an inheritance-disabled protected DACL granting access only to the current user SID, verifies actual owner/DACL after create/reopen before launch and stale cleanup, and refuses unchanged for any extra allow ACE, unverifiable ACL, reparse/link, or identity drift.
6. Stage C implements proof reuse. It proves exact unchanged proof-type inputs skip successful checks, every uncertain or changed relevant input reruns, selected review matches current reviewed meaning, and explicitly canonicalized recorder bookkeeping/timestamps can reuse without mutating immutable original input/raw provenance.
7. Stage D implements Lean migration in `forge upgrade`, refuses dirty targets before writing with no `--force` bypass, proves independent raw coverage against per-family classifications, validates in a temporary area, publishes/readbacks current outputs, records `.factory/migrations/lean-workflow-v2.json`, preserves project-owned settings/client-added/client-modified profiles, deletes or replaces only byte/hash-matching Forge-owned installed files, and removes only Lean-replaced runtime readers.
8. Stage E removes obsolete profiles/config references and updates docs/prompts to match runtime.
9. Stage F fixes `pr-link.yml`, then backfills the two verified missed PR links through `forge pr-link` on the implementation branch.
10. Run focused selectors after each stage, then run `verify.py`, `check_dual_runtime.py`, `check_encoding_hygiene.py`, `git diff --check`, and the real Claude/Codex Plan Mode smoke tests before review.

### Exact write scope and budgets

The proposed `write_scope` has 93 entries: 91 source/config/test paths, `.factory/migrations/lean-workflow-v2.json` for the self-migration manifest, and `.factory/events/` for recorder-generated PR-link backfill only.

Source, config, docs, and prompts:

- `AGENTS.md`
- `WORKFLOW.md`
- `docs/FACTORY.md`
- `docs/QUALITY.md`
- `docs/ROLES.md`
- `docs/getting-started.md`
- `docs/architecture/dual-coordinator-parity.md`
- `docs/specs/dual-coordinator-parity.md`
- `docs/specs/plan-approval.md`
- `docs/specs/delegation-boundary.md`
- `docs/specs/conflict-free-story-state.md`
- `factory/skills/forge.md`
- `factory/prompts/planner.md`
- `factory/prompts/griller.md`
- `factory/prompts/decomposer.md`
- `factory/prompts/reviewer.md`
- `harness.yaml`
- `.codex/config.toml`
- `.codex/hooks.json`
- `.claude/settings.json`
- `.claude/CLAUDE.md`
- `.github/workflows/pr-link.yml`

Deleted harness-owned profiles:

- `.codex/agents/architect.toml`
- `.codex/agents/backend.toml`
- `.codex/agents/debugger.toml`
- `.codex/agents/explorer.toml`
- `.codex/agents/frontend.toml`
- `.codex/agents/griller.toml`
- `.codex/agents/lite.toml`
- `.codex/agents/performance.toml`
- `.codex/agents/planner.toml`
- `.codex/agents/refactorer.toml`
- `.codex/agents/security.toml`
- `.codex/agents/tester.toml`

Runtime and schema paths:

- `factory/scripts/forge.py`
- `factory/scripts/factory_lib.py`
- `factory/scripts/pre_tool_use.py`
- `factory/scripts/post_tool_use.py`
- `factory/scripts/check_dual_runtime.py`
- `factory/scripts/session_start.py`
- `factory/scripts/record_grill_from_json.py`
- `factory/scripts/grill_gates.py`
- `factory/scripts/record_decomposition_from_json.py`
- `factory/scripts/record_test_from_json.py`
- `factory/scripts/verify.py`
- `factory/scripts/check_task_proof.py`
- `factory/scripts/forge_cli/plans.py`
- `factory/scripts/forge_cli/tasks.py`
- `factory/scripts/forge_cli/phase.py`
- `factory/scripts/forge_cli/approval.py`
- `factory/scripts/forge_cli/ceremony.py`
- `factory/scripts/forge_cli/delegate.py`
- `factory/scripts/forge_cli/stages.py`
- `factory/scripts/forge_cli/grill.py`
- `factory/scripts/forge_cli/readiness.py`
- `factory/scripts/forge_cli/upgrade.py`
- `factory/scripts/forge_cli/audit.py`
- `factory/scripts/forge_cli/close.py`
- `factory/scripts/forge_cli/review.py`
- `factory/scripts/forge_cli/review_brief.py`
- `factory/scripts/forge_cli/signal.py`
- `factory/scripts/forge_cli/scaffold.py`
- `factory/scripts/forge_cli/doctor.py`
- `factory/scripts/forge_cli/board.py`
- `factory/scripts/forge_cli/codex_runtime.py`
- `factory/scripts/forge_cli/worker_admission.py`
- `factory/schemas/lean-workflow-migration.json`
- `factory/schemas/grill.json`
- `factory/schemas/grill-round.json`
- `factory/schemas/plan-mode-marker.json`

Tests:

- `factory/tests/test_gates.py`
- `factory/tests/test_native_setup.py`
- `factory/tests/test_one_grill.py`
- `factory/tests/test_board_approval_gate.py`
- `factory/tests/test_plan_against_reality.py`
- `factory/tests/test_gate_table_e2e.py`
- `factory/tests/test_grill_release.py`
- `factory/tests/test_ask_gate.py`
- `factory/tests/test_proof_read_path.py`
- `factory/tests/test_review_settled_contracts.py`
- `factory/tests/test_review_task_delta.py`
- `factory/tests/test_gate_table.py`
- `factory/tests/test_close_binds_to_the_diff.py`
- `factory/tests/test_worker_admission.py`
- `factory/tests/test_lean_workflow.py`
- `factory/tests/test_approval_hooks.py`
- `factory/tests/test_upgrade_lean_workflow.py`
- `factory/tests/test_delegate_scope.py`
- `factory/tests/test_proof_reuse.py`
- `factory/tests/test_pr_link_workflow.py`
- `factory/tests/test_regrill_scope.py`

Recorder-generated output:

- `.factory/migrations/lean-workflow-v2.json` for the self-migration manifest after migration readback validates.
- `.factory/events/` only for the two `forge pr-link` backfill records after PR evidence is verified.

Positive review budget: at most 96 changed files and 14500 added-plus-deleted lines. The budget includes up to two generated `.factory/events/*.json` files and allows one extra migration fixture file if the implementation proves a schema fixture is necessary. If the implementation needs any path outside the list above, more than 96 files, or more than 14500 changed lines, stop for a contract amendment instead of weakening coverage, reviving old ceremony, or moving PR3-wide compatibility into Lean.

Stage line budgets:

- Approval shared recorder/module, hook adapters, config/profile/ceremony cleanup: 3000 lines.
- Narrowed delegation, hook enforcement, and mandatory context-file security: 2200 lines.
- Proof receipts in existing stage state, reviewed-meaning identity, and selected-proof authority cleanup: 2200 lines.
- Lean upgrade migration and normal-runtime removal for Lean formats: 3000 lines.
- Docs/prompts/workflow/pr-link backfill wiring: 1400 lines.
- Focused tests and fixtures: 2700 lines.

### Mandatory context-file security boundary

Lean makes `--context-file` mandatory for helper-supplied context that crosses approval, delegation, review, or migration boundaries. The implementation sites already in scope are `factory/scripts/forge_cli/delegate.py`, `factory/scripts/forge_cli/worker_admission.py`, `factory/scripts/pre_tool_use.py`, `factory/scripts/post_tool_use.py`, and `factory/scripts/factory_lib.py`; no extra storage subsystem or schema is introduced. The boundary must prove no-follow ancestors and leaves, stable identity for every accepted context file, one handle/snapshot per launch, exact UTF-8 decoding and capacity limits, `0700` directory and `0600` file modes, deletion/stale cleanup, and metadata-only evidence in durable records. The helper receives a stable handle, not ambient filesystem authority.

### Migration and refusal behavior

The migration is `lean-workflow-v2`. It must:

1. Require a clean checkout before target writes.
2. Inventory all Lean-owned old formats before mutation: requirements/plan grill records, grill-round ledgers, embedded task approvals, story approval markers, fixed lens proof, legacy stage stamps, old hook flag, and current 15-agent installation state.
3. Hash every input and classify every candidate as eligible, excluded with reason, or invalid. Invalid rows block the whole migration.
4. Refuse symlink/reparse/linked/malformed/mixed/partial/conflicting candidates before writing.
5. Build current outputs in a temporary area and validate schemas before publication.
6. Publish with no-overwrite or byte-identical idempotent semantics, then read back every output.
7. Install the Lean runtime/config/profile state.
8. Record `.factory/migrations/lean-workflow-v2.json` with input inventory digest, output digest, installed runtime digest, and migration version.
9. Delete only migrated old Lean artifacts after readback proves current outputs are durable.
10. Treat byte-identical retry as success and unequal partial retry as refusal.

Active old review proof must be excluded and force a fresh ordinary review. Sealed fixed-lens proof migrates in Lean, once, to the Decision 0069 canonical `origin=upgrade` selected-generation representation with the full sealed-proof safety contract: complete inventory, exact source artifact hashes, marker/sealed identity, no symlink/linked/mixed/colliding input, immutable generation publication, pointer-last selection, byte-identical retry, unequal retry refusal, and readback before deleting old direct fixed proof. Normal runtime keeps that canonical selected-generation reader and removes only direct fixed-file/fallback authority. It must not read fixed-lens paths as proof, embedded approvals, old stage stamp conversion branches, requirements gate state, old ceremony ledgers, old plan-mode marker authority, or the old hook flag. Encountering those Lean-removed formats outside upgrade prints the action: run `forge upgrade`.

PR3 remains responsible for the other repository-wide migrations and fallback removals named in the recovery plan. Lean must not delete `evidence_path` legacy fallbacks, `run_state_path` tracked-run fallback, event JSONL reading, quickfix/lesson JSONL reading, history-layout readers, old `.agents` runtime migration, native argv/continuation compatibility, old `stage start --trunk`, or broad missing-field compatibility.

### Security boundaries

No host-global Claude or Codex configuration changes are allowed. Only committed repo config changes are in scope.

Native approval evidence is trusted only when it comes from the expected runtime event, a stable session/event identity, exactly one eligible awaiting story/task artifact derived from the current frontier, and the current approval-bound digest. Async acknowledgements, optional clarification calls, ordinary chat, wrong runtime payloads, reused or replayed events, zero/multiple candidates, missing stable identity, canceled answers, and unsupported event shapes cannot approve a plan. The audit trail attributes approval as `human-via-Claude` or `human-via-Codex` plus runtime/session/event identity; it never invents a display name.

`delegate --scope` is a narrowing primitive, never a widening primitive. Every supplied path must normalize to a proper subset of the effective approved `write_scope`; an approved exact file path is valid as one subset member, and no `--scope` flag means the full effective scope. Duplicate, escaping, absolute, parent-traversal, symlink-ambiguous, missing-owned, or root-equal scope selections refuse. Hooks must enforce the narrowed scope from the launch record, not from command text reconstructed later.

Migration uses path-boundary helpers and index-aware inspection before writes. Follow the recorded repository-escape lessons: do not resolve client/target paths through the worktree in a way that follows symlinks into another repo, and do not delete or overwrite before the full preflight passes.

Generated `.factory/events/` files for the two PR backfills are durable evidence and must be created only by `forge pr-link`. A hand-written JSON file, a guessed PR number, or a `predates_outcome_contract` marker for those stories is a violation.

### API and data changes

CLI:

- Add `./forge delegate <task-id> --scope <repo-path> [--scope <repo-path> ...]`.
- Remove manual approval commands from the ordinary routed flow after native approval is installed; compatibility, if retained for upgrade/migration diagnostics, must not be the normal path.
- Remove the separate requirements-grill route from `forge next` and plan save requirements after Lean migration.

Data:

- Add `.factory/migrations/lean-workflow-v2.json` as the generated manifest written by the self-migration.
- Store proof identity receipts for tests and verify in existing stage state only as needed for content-bound reuse. Test proof names product bytes, exact test command, selectors, test config, and tool versions. Verify proof names product bytes, verify argv, verify config, tool versions, and generated semantic inputs. Selected-review proof keeps the Decision 0066 stamp-token delta binding and also records the reviewed-meaning identity: approved semantic task-brief digest, effective acceptance/security/migration semantics, substantive automated evidence, review instructions/helper/config, and product delta. Reuse preserves immutable original input/raw provenance and may canonicalize only recorder bookkeeping/timestamps.
- Replace fixed review lens runtime authority with selected generation authority only. Fixed lens files are migration inputs, not fallback proof; the retained runtime reader is the Decision 0069 `origin=upgrade` selected-generation reader.
- Use the currently supported `.factory/events/*.json` output only for Lean's two PR-link backfills and workflow staging repair. Lean adds no event-family migration and no future canonical event reader; Portable later moves `.factory/events/<id>.json`, `.factory/events.jsonl`, and any historical bundles into one append-only event log per story.

Configuration:

- `.codex/config.toml`: `hooks = true`; no `codex_hooks = true`.
- `.codex/hooks.json` and `.claude/settings.json`: exact hook matrices from the recovery plan.
- `.claude/CLAUDE.md`: approval routing text changes to point at the native approval path and shared recorder.
- `.codex/agents/`: retain only `planner-high`, `docs-decomposer`, and `functional-checker` in this repo after Lean, per the user's later explicit recovery approval overriding earlier profile expectations. Preserve First shipped row/history and accepted Decision 0074 text; Lean changes the installed Forge-owned profile set, not the historical decision record. Preserve project-owned settings outside the exact harness inventory, all client-added profiles, and client-modified same-name profiles. Delete or replace only byte/hash-matching known Forge-owned installed files; unknown, mixed, or hash-mismatched same-name rows classify as preserved or invalid explicitly, never silently overwrite. Portable later consumes that canonical three-profile registry and preserves client-modified and client-added profiles; old `.agents` relocation must never reinstall the retired twelve.
- Native approval storage: reuse the existing story plan-approval marker and task grill approval fields through `factory/scripts/forge_cli/approval.py`. Migration changes producer and shape only as necessary for the new native events, then deletes old manual producers/commands only after current readers consume the same validated authority. Replay consumption is atomic on runtime/session/event identity plus plan kind/story/task/current digest; no new artifact or schema is introduced.

## Decisions

No new decisions.

The choices in this plan are derivable from the accepted corpus and the approved recovery plan/task contract:

- Decision 0064 authorizes Lean delivery, fewer repeated ceremonies, durable task proof, genuine combined review, complete review inputs, and one-time migration behavior.
- Decision 0069 assigns combined review generation to the already-shipped First work; Lean consumes it.
- Decision 0073 governs round reuse and carries the later empty-frontier exception without reviving superseded 0051/0071 wording.
- Decision 0074 keeps main coordinator model selection with the user/host while preserving Forge-managed worker lanes.
- The approved recovery plan/task contract supplies the exact native-approval exception to Decisions 0029, 0054, and 0061 and the content-bound close-reuse clarification for Decision 0066; this introduces no new decision record and no new proof schema or artifact.
- Decisions 0022, 0045, and the CFS history explain why Lean must repair the current per-event PR-link workflow/backfills; the later explicit user instruction controls without a new decision and makes Portable's future canonical target one append-only event log per story plus a canonical unattributed sink for idless/unattributable legacy rows, explicitly superseding only the old event-bundle and dual-reader portions of Decision 0064 lines 61-68, confirmed spec lines 100/119, and conflict-free spec lines 63-64 during Portable implementation.
- Decisions 0017, 0033, and the Board backfill history require real PR evidence and forbid fabricated links.

## Surface Impact

| Surface | Impact | Reason |
|---|---|---|
| Runtime behavior | Changed | Native approval, no requirements grill, proof reuse, narrowed delegation, and Lean-migrated normal runtime change the lifecycle. |
| API | Changed | `forge delegate` gains repeatable `--scope`; ordinary manual approval commands leave the normal route. |
| Data/schema | Changed | Adds Lean migration manifest and stage-state proof receipts; migrates/removes Lean-owned old formats; writes two verified current per-event PR links only for board honesty before Portable's event-family migration. |
| CLI/ops | Changed | `forge next`, `forge upgrade`, `forge delegate`, hook setup, doctor/setup checks, and PR-link workflow behavior change. |
| UI | N-A | No user-facing UI task; `user_facing: false`. Board text may update only to remove stale approval guidance. |
| Docs | Changed | Workflow, Forge docs, specs, prompts, skill text, and AGENTS pointers must describe the installed runtime. |
| Tests | Changed | Focused new and existing selectors cover approval, scopes, reuse, migration, hooks/profiles, and PR-link staging. |

### Follow-on Portable PR3 boundary

The existing `PORTABLE-DELIVERY-MIGRATION` row, not Lean, owns the exact remaining non-review recovery PR3 legacy-family migration list, the whole event family migration to one append-only event log per story plus the canonical unattributed sink for idless/unattributable legacy rows, isolated `upgrade_migrations.py`, PR3 safety checks, Linux/Windows proof, setup/doctor choice UX, and configured external-client rollout prerequisite. Portable preserves decision/spec history and updates only the superseded old bundle/dual-reader text during implementation. It starts after Lean's fixed-proof migration, fixed-file fallback retirement, and profile-pruning outputs exist; it must not duplicate fixed-review migration or 15-profile obligations, and it preserves client-modified/client-added profiles. Future Native, Shared, Format, Quality, and Integration rows stay skeletal until their own turn.

### Acceptance contract binding

Amend the executable `LEAN-WORKFLOW` task contract now. The task objective becomes: install recovery PR2 by replacing repeated approval/round ceremony with native approval, one cold grill with complete finding disposition, narrowed delegation, mandatory context-file security, content-bound close reuse in existing stage state, Lean-owned migration/deletion for removed formats including sealed fixed-proof migration, three-profile Forge registry reduction, PR-link workflow repair/backfill only for current board honesty, docs/spec/architecture/runtime alignment, and the amended Portable PR3 handoff for the whole event family. Preserve only the task id, title, dependency on First, and `user_facing: false`.

The task `acceptance_criteria` must be exactly these twelve numbered criteria, and `plan_contracts` must bind them one-to-one:

1. Native approval path: story/task plans approve through the supported Claude and Codex native approval events, not the old manual/board route.
2. Shared recorder identity: the shared approval recorder binds exactly one current-frontier candidate, current digest, runtime, stable session/event identity, plan kind/story/task, replay refusal, and `human-via-Claude` / `human-via-Codex` attribution.
3. Ceremony removal: requirements grill, round floors, old round ledgers as authority, fake frontier questions, second unchanged save, and manual plan/task approval leave normal runtime; Lean preserves one independent cold grill plus complete finding disposition, including the three requirements cold-read gap dispositions for context snapshot security, independent migration coverage, and clean-target preservation, explained amendment bridge to the final artifact digest, final human approval on that digest, and refusal for unexplained out-of-disposition changes.
4. Narrowed delegation: `forge delegate --scope` is a proper-subset narrowing feature, exact approved files are valid subset members, no flag keeps full effective scope, and hook admission enforces the narrowed launch identity.
5. Content-bound close reuse: test/verify receipts and selected-review reviewed-meaning identity reuse only when their proof-type inputs match; substantive acceptance/security/migration/evidence/review-instruction/product-delta changes force review, while canonicalized bookkeeping/timestamp changes preserve immutable original provenance.
6. Lean migration: `forge upgrade` performs clean-checkout preflight with no `--force` bypass, full inventory/hash/classification, independent raw no-follow coverage over fixed legacy roots/exact parents, temp build, validation, publish/readback, idempotent retry, unequal partial refusal, generated `.factory/migrations/lean-workflow-v2.json`, profile/settings preservation, and deletion only after durable current outputs exist.
7. Fixed-proof migration: Lean migrates sealed fixed-lens proof once into canonical `origin=upgrade` selected generations with the full sealed-proof safety contract, while active old proof requires a fresh review and normal runtime never uses direct fixed-file fallback authority.
8. Hook/config/profile target: committed Claude/Codex hook matrices, `.codex/config.toml`, `.claude/CLAUDE.md`, and profile installation match the recovery target; only three Forge-owned profiles remain while client-modified/client-added profiles are preserved.
9. PR-link workflow staging: `.github/workflows/pr-link.yml` stages current per-event `.factory/events/` files and updates its status/comment wording without returning to `.factory/events.jsonl` writes, while Portable owns the future canonical per-story event log.
10. Verified PR-link backfill: only verified PR #109 and #110 links are backfilled through `forge pr-link`, producing recorder-generated event files and clearing those board-completeness failures without touching unrelated spec gaps.
11. Normal-runtime refusal: Lean-removed old formats outside upgrade produce `run forge upgrade` guidance; PR3-owned legacy families stay compatible until Portable handles them.
12. Docs/runtime agreement: workflow, docs, specs, prompts, skills, architecture text, reviewer focus, required tests, and design-review status agree with the implemented runtime without duplicating long canon in `AGENTS.md`.

## Task Decomposition

Single task: `LEAN-WORKFLOW`, depends on `NATIVE-FOREGROUND-ACTIVATE`, `user_facing: false`. The task objective and `acceptance_criteria` are amended per the twelve criteria in `Acceptance contract binding`, and `plan_contracts` binds criteria 1-12 in the same order. No extra Lean task, PR, or decision is introduced.

Reviewer focus:

- Prove the new flow removes ceremony only where native approval/proof identity replaces it. No real gate may disappear without an equivalent current authority check.
- Confirm `delegate --scope` is a proper-subset narrowing feature, not a bypass; exact approved files are valid subset members and no flag keeps full effective scope.
- Confirm proof reuse is content-bound and fail-closed, including reviewed-meaning invalidation and immutable original input/raw provenance on reuse.
- Confirm migration has full preflight, no `--force` dirty bypass, independent raw no-follow coverage over fixed legacy roots/exact parents, temp validation, readback, idempotent retry, unequal-partial refusal, a generated `.factory/migrations/lean-workflow-v2.json` manifest, Lean-owned fixed-proof migration and fixed-file fallback retirement that Portable must not duplicate, and harness-owned profile pruning that Portable consumes rather than redoing.
- Confirm PR3-owned legacy compatibility and full event-family migration remain in Portable, not Lean.
- Confirm `pr-link.yml` stages current per-event records and the two existing missing links are recorder-generated from verified PR evidence, without adding canonical event-log migration to Lean.
- Confirm docs/prompts match runtime and do not duplicate long canon in `AGENTS.md`.
- Confirm the task decomposition objective and `acceptance_criteria` are amended now and match the twelve plan contracts one-to-one.
- Confirm mandatory `--context-file` security: same-user read/write/delete access only, no-follow, stable identity, one handle/snapshot, UTF-8/capacity, POSIX `0700`/`0600`, native Windows protected DACL with only the current user SID, reopen owner/DACL verification before launch and stale cleanup, refusal for extra allow ACEs/unverifiable ACL/reparse/link/identity drift, and metadata-only evidence.

Staged acceptance:

- A0: Active decisions, findings patterns, lessons, and First merged state checked before stage start.
- A1: Native approval flow passes the shared approval module tests, focused approval hook tests, stable-identity/replay tests, and smoke tests for Claude and Codex.
- A2: Delegation scope narrowing and mandatory `--context-file` pass proper-subset, exact-file, no-flag full-scope, launch identity, hook admission, no-follow, stable-identity, mode, capacity, cleanup, and metadata-only evidence tests.
- A3: Proof reuse passes unchanged-input reuse, changed/unknown-input rerun, proof-type-specific identity, reviewed-meaning invalidation, immutable-provenance preservation, and bookkeeping-only reuse tests.
- A4: Lean migration passes clean-checkout, invalid-input, temp-build, readback, idempotent retry, unequal-partial refusal, active-review-fresh-review, Lean-owned sealed-proof-upgrade, generated-manifest, and normal-runtime-refusal tests.
- A5: Hook/config/profile state passes dual-runtime, doctor/setup, init/upgrade preservation, and agent deletion tests.
- A6: PR-link workflow content pins pass; verified backfill creates two per-file events; `check_board_complete.py` passes for `FORGE-CFS-1` and `FORGE-ACC-3`.
- A7: `verify.py`, `check_dual_runtime.py`, `check_encoding_hygiene.py`, `git diff --check`, and real native Plan Mode smokes pass.
- A8: One normal combined three-lens review is clean after focused tests and verification.

## Risks

- The task is broad because the recovery plan assigns the approval workflow, migration, config/profile cleanup, narrowed delegation, legacy-audit PR2 surfaces, and PR-link failure to Lean. The positive budget is therefore intentionally larger than older Lean drafts. If the measured diff exceeds it, stop for amendment.
- Removing requirements grills, old round floors, old ledgers, and manual approvals can accidentally erase authority. The implementation must replace every removed check with native approval, one cold grill with complete finding disposition, or recorded digest proof before deleting the old gate. The user-approved recovery PR2 overrides older round/profile expectations for this task.
- Proof reuse can become a fake pass if it omits the inputs relevant to that proof type: test selectors/config/tool versions for tests, verify argv/config/generated semantic inputs for verify, or reviewed-meaning identity for selected review. Unknown means rerun. Bookkeeping-only reuse is allowed only for explicitly canonicalized recorder bookkeeping/timestamps; acceptance, security, migration, automated evidence, review instruction/helper/config, product-delta, or semantic task-brief changes force review.
- Migration and runtime deletion can strand old clients. Keep PR3-owned broad compatibility for the event family and other legacy families in the existing `PORTABLE-DELIVERY-MIGRATION` row immediately after Lean, prove old Lean-owned formats migrate before deletion, and ensure Portable starts from Lean canonical outputs rather than duplicating fixed-review/profile migration.
- Hook payload parity is not guaranteed by docs. The implementation must prove the real Codex synchronous payload before claiming parity.
- `.factory/events/` backfill is legitimate only because PR #109 and #110 are verified merged PRs. If GitHub evidence cannot be reproduced during implementation, stop and report the contradiction instead of linking or marking predates.
- `forge project audit` will still report unrelated pending-story spec gaps after the two PR links are repaired. Lean should not widen to fix those cards.
- Existing recurring findings `repository-escape` and `reviewed-separately` touch upgrade and review-adjacent code. Lean must audit every changed target-write path through boundary helpers and keep review/proof generation current; any fourth occurrence escalates per Decision 0005.

## Verify Plan

Use task-local uv storage:

```sh
export UV_CACHE_DIR=/tmp/forge-lean-uv-cache
export UV_TOOL_DIR=/tmp/forge-lean-uv-tools
```

Focused required pytest selectors:

```sh
uv run --python 3.11 --with pytest --with psutil python -m pytest \
  factory/tests/test_approval_hooks.py \
  factory/tests/test_approval_hooks.py::test_native_approval_refuses_zero_multiple_candidates_replay_and_missing_identity \
  factory/tests/test_approval_hooks.py::test_native_approval_records_human_via_runtime_identity_without_display_name \
  factory/tests/test_approval_hooks.py::test_native_approval_reuses_existing_story_and_task_approval_storage \
  --junitxml=.factory/tmp/lean-approval-hooks.junit.xml
```

```sh
uv run --python 3.11 --with pytest --with psutil python -m pytest \
  factory/tests/test_lean_workflow.py::test_native_plan_mode_approval_records_exact_digest_for_claude_exit_plan_mode \
  factory/tests/test_lean_workflow.py::test_native_plan_mode_approval_records_exact_digest_for_codex_sync_approval \
  factory/tests/test_lean_workflow.py::test_native_approval_refuses_stale_wrong_runtime_canceled_async_and_unsupported_payloads \
  factory/tests/test_lean_workflow.py::test_normal_flow_no_longer_requires_requirements_grill_manual_approval_or_second_save \
  --junitxml=.factory/tmp/lean-native-approval.junit.xml
```

```sh
uv run --python 3.11 --with pytest --with psutil python -m pytest \
  factory/tests/test_delegate_scope.py::test_delegate_scope_must_be_strict_subset_of_approved_write_scope \
  factory/tests/test_delegate_scope.py::test_delegate_scope_is_bound_to_brief_launch_identity_and_existing_write_scope \
  factory/tests/test_delegate_scope.py::test_hook_refuses_write_outside_narrowed_delegate_scope \
  factory/tests/test_gates.py::test_delegate_brief_carries_criteria_and_scope \
  factory/tests/test_worker_admission.py::test_native_worker_patch_add_update_delete_and_move_is_admitted \
  factory/tests/test_delegate_scope.py::test_context_file_security_no_follow_modes_identity_capacity_and_cleanup \
  factory/tests/test_delegate_scope.py::test_context_file_native_windows_protected_dacl_owner_reopen_and_stale_cleanup \
  factory/tests/test_worker_admission.py::test_context_file_launch_uses_one_handle_snapshot_and_metadata_only_evidence \
  --junitxml=.factory/tmp/lean-delegate-scope.junit.xml
```

```sh
uv run --python 3.11 --with pytest --with psutil python -m pytest \
  factory/tests/test_proof_reuse.py::test_unchanged_test_verify_and_selected_review_inputs_reuse_success_without_rerun \
  factory/tests/test_proof_reuse.py::test_changed_unknown_partial_or_generated_output_identity_forces_fresh_run \
  factory/tests/test_proof_reuse.py::test_reuse_identity_is_proof_type_specific_and_reviewed_meaning_bound \
  factory/tests/test_proof_reuse.py::test_selected_review_reuses_for_bookkeeping_only_changes_and_preserves_original_provenance \
  factory/tests/test_proof_reuse.py::test_selected_review_reruns_for_changed_acceptance_security_migration_or_evidence \
  factory/tests/test_review_settled_contracts.py::test_selected_upgrade_generation_requires_exact_sealed_binding \
  factory/tests/test_review_task_delta.py::test_selected_review_reviewed_meaning_includes_ci_generated_outputs_and_review_instructions \
  factory/tests/test_review_task_delta.py::test_selected_review_reruns_for_substantive_automated_evidence_change \
  --junitxml=.factory/tmp/lean-proof-reuse.junit.xml
```

```sh
uv run --python 3.11 --with pytest --with psutil python -m pytest \
  factory/tests/test_upgrade_lean_workflow.py::test_lean_migration_refuses_dirty_checkout_before_writing \
  factory/tests/test_upgrade_lean_workflow.py::test_lean_migration_force_cannot_bypass_dirty_tree_refusal \
  factory/tests/test_upgrade_lean_workflow.py::test_lean_migration_independent_raw_walk_covers_each_candidate_exactly_once \
  factory/tests/test_upgrade_lean_workflow.py::test_lean_migration_inventories_hashes_temp_validates_publishes_and_reads_back \
  factory/tests/test_upgrade_lean_workflow.py::test_lean_migration_refuses_malformed_mixed_partial_conflicting_or_linked_inputs \
  factory/tests/test_upgrade_lean_workflow.py::test_lean_migration_is_idempotent_for_byte_identical_retry_and_refuses_unequal_partial_retry \
  factory/tests/test_upgrade_lean_workflow.py::test_lean_migration_forces_fresh_review_for_active_old_proof_and_migrates_only_exact_sealed_proof \
  factory/tests/test_upgrade_lean_workflow.py::test_normal_runtime_refuses_lean_removed_formats_with_upgrade_guidance \
  --junitxml=.factory/tmp/lean-upgrade-migration.junit.xml
```

```sh
uv run --python 3.11 --with pytest --with psutil python -m pytest \
  factory/tests/test_native_setup.py::test_codex_hook_readiness_requires_exact_enabled_trusted_source \
  factory/tests/test_native_setup.py::test_codex_hook_readiness_accepts_only_identical_inherited_worktree_hooks \
  factory/tests/test_native_setup.py::test_model_policy_selects_sol_work_and_luna_lite \
  factory/tests/test_gate_table.py::test_active_model_policy_has_no_forbidden_execution_surface \
  factory/tests/test_gates.py::test_project_agents_init_upgrade_and_preserve_client_additions \
  factory/tests/test_native_setup.py::test_recovery_profile_override_keeps_only_three_forge_profiles \
  factory/tests/test_gates.py::test_upgrade_preserves_client_profiles_while_removing_retired_forge_profiles \
  factory/tests/test_gates.py::test_upgrade_preserves_project_settings_and_refuses_unknown_same_name_profile_rows \
  --junitxml=.factory/tmp/lean-hooks-profiles.junit.xml
```

```sh
uv run --python 3.11 --with pytest --with psutil python -m pytest \
  factory/tests/test_pr_link_workflow.py::test_pr_link_workflow_stages_per_event_files_not_legacy_jsonl \
  factory/tests/test_pr_link_workflow.py::test_pr_link_workflow_status_description_names_per_event_link_commit \
  factory/tests/test_pr_link_workflow.py::test_verified_forge_acc3_and_cfs1_pr_links_make_board_complete \
  factory/tests/test_pr_link_workflow.py::test_pr_link_backfill_remains_current_per_event_until_portable_migrates \
  factory/tests/test_gates.py::test_pr_link_event_survives_a_clone_with_no_remote \
  factory/tests/test_gates.py::test_forge_history_shows_the_pr_link \
  factory/tests/test_gates.py::test_signal_ruling_hydration_survives_lean_lifecycle_state_changes \
  factory/tests/test_review_task_delta.py::test_generated_review_inputs_are_included_in_reviewed_meaning \
  --junitxml=.factory/tmp/lean-pr-link.junit.xml
```

```sh
uv run --python 3.11 --with pytest --with psutil python -m pytest \
  factory/tests/test_regrill_scope.py \
  --junitxml=.factory/tmp/lean-regrill-scope.junit.xml
```

```sh
uv run --python 3.11 --with pytest --with psutil python -m pytest \
  factory/tests/test_lean_workflow.py::test_one_cold_grill_full_disposition_replaces_round_floors_and_frontier_fake \
  factory/tests/test_lean_workflow.py::test_recovery_override_removes_round_ledgers_without_losing_cold_read_proof \
  factory/tests/test_plan_against_reality.py::test_lean_docs_match_single_cold_grill_runtime \
  factory/tests/test_board_approval_gate.py::test_native_approval_no_longer_routes_through_board_or_manual_approve \
  --junitxml=.factory/tmp/lean-docs-prompts.junit.xml
```

Required non-pytest checks:

```sh
uv run --python 3.11 --with pytest --with psutil python factory/scripts/verify.py
python3 factory/scripts/check_dual_runtime.py
python3 factory/scripts/check_encoding_hygiene.py
python3 factory/scripts/check_board_complete.py
git diff --check
```

Manual and live checks:

- Run a real Claude Plan Mode approval smoke: author a disposable plan fixture, approve via successful `ExitPlanMode`, and verify the recorder binds the exact digest, stable completion/event identity, runtime/session identity, plan kind/story/task, current frontier candidate, and `human-via-Claude` attribution.
- Run a real Codex synchronous `request_user_input` approval smoke with the exact `Approve plan / Request changes / Stop` options and verify the recorder binds stable completion/event identity, runtime/session identity, plan kind/story/task, current frontier candidate, current digest, and `human-via-Codex` attribution; stale/canceled/request-changes/missing-identity paths refuse.
- Verify `gh pr view 109` and `gh pr view 110` still show merged PRs for `FORGE-CFS-1` and `FORGE-ACC-3` before running the two `forge pr-link` commands.
- Verify `check_board_complete.py` failure before backfill names only those two missing PR links, and after backfill no longer names them.
- Verify `forge project audit --repo .` still reports the unrelated pending-story spec gaps separately; do not make Lean fix them.

### Manual Verification

1. From a clean Lean worktree after First is on trunk, run `git rev-parse HEAD` and confirm it is the post-First merge base for this task, not the old First worktree.
2. Open the rendered task brief and confirm it contains objective, acceptance criteria, capability boundary, public API/data changes, security boundaries, migration/refusal behavior, rollout/backfill behavior, exact `write_scope`, and this verify plan.
3. Exercise the new human flow in both hosts:
   - Claude: enter Plan Mode, produce a small plan fixture, approve with `ExitPlanMode`, then confirm the recorded approval digest matches the displayed plan body and the record includes stable runtime/session/event identity, plan kind/story/task, current-frontier candidate identity, and `human-via-Claude` attribution.
   - Codex: use synchronous `request_user_input` with `Approve plan / Request changes / Stop`; approve once, reject once, and cancel once; confirm only the approval writes a current digest and records stable runtime/session/event identity, plan kind/story/task, current-frontier candidate identity, and `human-via-Codex` attribution. Missing stable completion/event identity fails closed.
4. Run `./forge delegate LEAN-WORKFLOW --scope factory/scripts/forge_cli/delegate.py --print-only` after the stage is active and confirm the approved exact file is accepted as a narrowed subset. Then run the same print-only command with no `--scope` and confirm the brief and launch row carry the full effective approved scope.
5. Attempt a write outside the narrowed scope through the hook fixture and confirm it refuses with the narrowed path set in the message.
6. Run one test proof, one verify proof, and one selected-review proof twice without relevant changes and confirm the second close reuses successful proof and spends no unnecessary check/model work. Then change a test selector/config/tool version, a verify argv/config/generated semantic input, and each selected-review reviewed-meaning component: approved semantic task brief, effective acceptance/security/migration semantics, substantive automated evidence, review instruction/helper/config, and product delta. Confirm only the affected proof type reruns. Change only explicitly canonicalized recorder bookkeeping/timestamps and confirm a current Decision 0066 selected generation may reuse while preserving immutable original input/raw provenance.
7. Run Lean migration on fixture repos covering clean success, dirty checkout refusal, `--force` dirty refusal, independent raw-walk coverage mismatch, malformed input, active old proof, sealed fixed proof, byte-identical retry, unequal partial retry, generated manifest readback, profile/settings preservation, unknown same-name row refusal/classification, and old-format normal runtime refusal. Confirm sealed fixed proof becomes only `origin=upgrade` selected-generation proof and that direct fixed/fallback proof no longer certifies closeout.
8. Inspect `.codex/config.toml`, `.codex/hooks.json`, `.claude/settings.json`, and `.codex/agents/` in the final diff. Confirm `codex_hooks = true` is gone, `hooks = true` is present, hook matchers match the recovery plan, the 12 retired profile files are deleted, and the 3 retained profiles remain.
9. Confirm `.github/workflows/pr-link.yml` stages `.factory/events/*.json` or `.factory/events/` and no longer stages `.factory/events.jsonl`.
10. Verify PR evidence live:
    - `gh pr view 109 --json number,title,mergedAt,url,headRefName`
    - `gh pr view 110 --json number,title,mergedAt,url,headRefName`
11. Run:
    - `./forge pr-link FORGE-CFS-1 knacklabs/symphony-forge#109`
    - `./forge pr-link FORGE-ACC-3 knacklabs/symphony-forge#110`
    Then inspect that two new `.factory/events/<id>.json` files contain `event: pr-linked`, the correct story, and the verified reference.
12. Run `python3 factory/scripts/check_board_complete.py`; it must not name `FORGE-CFS-1` or `FORGE-ACC-3`.
13. Exercise `--context-file` with a valid file, symlinked ancestor, symlinked leaf, oversized UTF-8 file, invalid UTF-8, stale handle, deletion cleanup, and native Windows ACL cases. Confirm accepted context records only metadata; POSIX uses owned `0700`/`0600` non-links; native Windows creates and reopens an inheritance-disabled protected DACL granting only the current user SID; and every extra allow ACE, unverifiable ACL, reparse/link, owner/identity drift, or same-user mismatch refuses unchanged with no durable authority.
14. Inspect the final task contract and confirm the `LEAN-WORKFLOW` objective is amended for the full recovery PR2 scope, `acceptance_criteria` contains exactly the twelve numbered criteria in this plan, and `plan_contracts` binds those criteria one-to-one.
15. Inspect the amended roadmap/decomposition proposal before recording: pending chain is First -> Lean -> Portable(PR3) -> Native -> Shared -> Format -> Quality -> Integration; Portable depends on Lean, Native on Portable, Format on Shared, and Shared/Quality/Integration otherwise preserve existing dependencies. `PORTABLE-DELIVERY-MIGRATION` remains the existing PR3 owner immediately after Lean, First history and Decision 0074 text are preserved, fixed-review migration/profile pruning appear only in Lean, old `.agents` relocation cannot reinstall retired profiles, and later Native/Shared owners are not marked complete or required for PR3. Portable keeps its non-overlap setup/doctor choice UX and owns the whole event-family migration to one append-only event log per story plus canonical unattributed sink, with configured external-client rollout still prerequisite and no duplicate Integration event-bundle obligation. It must explicitly supersede only the old bundle/dual-reader portions and never fabricate IDs, story links, or attribution for idless legacy rows.

<!-- forge:contract -->
## Contract (recorded)

Rendered by the harness from the recorded decomposition; edit the decomposition, not this block. It is excluded from the plan's approval and grill digests, so a re-render never stales either.

**Objective.** install recovery PR2 by replacing repeated approval/round ceremony with native approval, one cold grill with complete finding disposition, narrowed delegation, mandatory context-file security, content-bound close reuse in existing stage state, Lean-owned migration/deletion for removed formats including sealed fixed-proof migration, three-profile Forge registry reduction, PR-link workflow repair/backfill, docs/spec/architecture/runtime alignment, and the amended Portable PR3 handoff.

**Acceptance criteria**

- Native approval path: story/task plans approve through the supported Claude and Codex native approval events, not the old manual/board route.
- Shared recorder identity: the shared approval recorder binds exactly one current-frontier candidate, current digest, runtime, stable session/event identity, plan kind/story/task, replay refusal, and `human-via-Claude` / `human-via-Codex` attribution.
- Ceremony removal: requirements grill, round floors, old round ledgers as authority, fake frontier questions, second unchanged save, and manual plan/task approval leave normal runtime; Lean preserves one independent cold grill plus complete finding disposition, including the three requirements cold-read gap dispositions for context snapshot security, independent migration coverage, and clean-target preservation, explained amendment bridge to the final artifact digest, final human approval on that digest, and refusal for unexplained out-of-disposition changes.
- Narrowed delegation: `forge delegate --scope` is a proper-subset narrowing feature, exact approved files are valid subset members, no flag keeps full effective scope, and hook admission enforces the narrowed launch identity.
- Content-bound close reuse: test/verify receipts and selected-review reviewed-meaning identity reuse only when their proof-type inputs match; substantive acceptance/security/migration/evidence/review-instruction/product-delta changes force review, while canonicalized bookkeeping/timestamp changes preserve immutable original provenance.
- Lean migration: `forge upgrade` performs clean-checkout preflight with no `--force` bypass, full inventory/hash/classification, independent raw no-follow coverage over fixed legacy roots/exact parents, temp build, validation, publish/readback, idempotent retry, unequal partial refusal, generated `.factory/migrations/lean-workflow-v2.json`, profile/settings preservation, and deletion only after durable current outputs exist.
- Fixed-proof migration: Lean migrates sealed fixed-lens proof once into canonical `origin=upgrade` selected generations with the full sealed-proof safety contract, while active old proof requires a fresh review and normal runtime never uses direct fixed-file fallback authority.
- Hook/config/profile target: committed Claude/Codex hook matrices, `.codex/config.toml`, `.claude/CLAUDE.md`, and profile installation match the recovery target; only three Forge-owned profiles remain while client-modified/client-added profiles are preserved.
- PR-link workflow staging: `.github/workflows/pr-link.yml` stages per-event `.factory/events/` files and updates its status/comment wording without returning to `.factory/events.jsonl` writes.
- Verified PR-link backfill: only verified PR #109 and #110 links are backfilled through `forge pr-link`, producing recorder-generated event files and clearing those board-completeness failures without touching unrelated spec gaps.
- Normal-runtime refusal: Lean-removed old formats outside upgrade produce `run forge upgrade` guidance; PR3-owned legacy families stay compatible until Portable handles them.
- Docs/runtime agreement: workflow, docs, specs, prompts, skills, architecture text, reviewer focus, required tests, and design-review status agree with the implemented runtime without duplicating long canon in `AGENTS.md`.

**Write scope** (what `stage done` measures the diff against)

- AGENTS.md
- WORKFLOW.md
- docs/FACTORY.md
- docs/QUALITY.md
- docs/ROLES.md
- docs/getting-started.md
- docs/architecture/dual-coordinator-parity.md
- docs/specs/dual-coordinator-parity.md
- docs/specs/plan-approval.md
- docs/specs/delegation-boundary.md
- docs/specs/conflict-free-story-state.md
- factory/skills/forge.md
- factory/prompts/planner.md
- factory/prompts/griller.md
- factory/prompts/decomposer.md
- factory/prompts/reviewer.md
- harness.yaml
- .codex/config.toml
- .codex/hooks.json
- .claude/settings.json
- .claude/CLAUDE.md
- .github/workflows/pr-link.yml
- .codex/agents/architect.toml
- .codex/agents/backend.toml
- .codex/agents/debugger.toml
- .codex/agents/explorer.toml
- .codex/agents/frontend.toml
- .codex/agents/griller.toml
- .codex/agents/lite.toml
- .codex/agents/performance.toml
- .codex/agents/planner.toml
- .codex/agents/refactorer.toml
- .codex/agents/security.toml
- .codex/agents/tester.toml
- factory/scripts/forge.py
- factory/scripts/factory_lib.py
- factory/scripts/pre_tool_use.py
- factory/scripts/post_tool_use.py
- factory/scripts/check_dual_runtime.py
- factory/scripts/session_start.py
- factory/scripts/record_grill_from_json.py
- factory/scripts/grill_gates.py
- factory/scripts/record_decomposition_from_json.py
- factory/scripts/record_test_from_json.py
- factory/scripts/verify.py
- factory/scripts/check_task_proof.py
- factory/scripts/forge_cli/plans.py
- factory/scripts/forge_cli/tasks.py
- factory/scripts/forge_cli/phase.py
- factory/scripts/forge_cli/approval.py
- factory/scripts/forge_cli/ceremony.py
- factory/scripts/forge_cli/delegate.py
- factory/scripts/forge_cli/stages.py
- factory/scripts/forge_cli/grill.py
- factory/scripts/forge_cli/readiness.py
- factory/scripts/forge_cli/upgrade.py
- factory/scripts/forge_cli/audit.py
- factory/scripts/forge_cli/close.py
- factory/scripts/forge_cli/review.py
- factory/scripts/forge_cli/review_brief.py
- factory/scripts/forge_cli/signal.py
- factory/scripts/forge_cli/scaffold.py
- factory/scripts/forge_cli/doctor.py
- factory/scripts/forge_cli/board.py
- factory/scripts/forge_cli/codex_runtime.py
- factory/scripts/forge_cli/worker_admission.py
- factory/schemas/lean-workflow-migration.json
- factory/schemas/grill.json
- factory/schemas/grill-round.json
- factory/schemas/plan-mode-marker.json
- factory/tests/test_gates.py
- factory/tests/test_native_setup.py
- factory/tests/test_one_grill.py
- factory/tests/test_round_provenance.py
- factory/tests/test_grill_carries_answers.py
- factory/tests/test_board_approval_gate.py
- factory/tests/test_plan_against_reality.py
- factory/tests/test_gate_table_e2e.py
- factory/tests/test_grill_release.py
- factory/tests/test_ask_gate.py
- factory/tests/test_proof_read_path.py
- factory/tests/test_review_settled_contracts.py
- factory/tests/test_review_task_delta.py
- factory/tests/test_gate_table.py
- factory/tests/test_close_binds_to_the_diff.py
- factory/tests/test_worker_admission.py
- factory/tests/test_lean_workflow.py
- factory/tests/test_approval_hooks.py
- factory/tests/test_upgrade_lean_workflow.py
- factory/tests/test_delegate_scope.py
- factory/tests/test_proof_reuse.py
- factory/tests/test_pr_link_workflow.py
- factory/tests/test_regrill_scope.py
- .factory/migrations/lean-workflow-v2.json
- .factory/events/
- factory/tests/test_grill_budget.py
- factory/tests/test_lifecycle_end_to_end.py
- factory/tests/test_review_lenses_in_parallel.py
- factory/tests/test_seal_measures.py
- factory/tests/test_stop_less_often.py
- .github/workflows/roadmap-gate.yml
- docs/decisions/0049-per-task-review-proof.md
- docs/decisions/0064-lean-delivery-and-durable-history.md
- plans/active/FORGE-WIN-3-delegation-runs-on-native-windows.md
- plans/active/upgrade-doc-contract-safety-task-plan.md
- factory/scripts/pr_ready.py
- factory/scripts/check_encoding_hygiene.py
- factory/tests/test_requirements_freshness.py
- factory/board/index.html
- .envrc
- factory/scripts/forge_cli/AGENTS.md
- .github/workflows/factory-scaffold.yml
- factory/tests/test_closeout_mode_from_markers.py
- factory/schemas/delegation.json

**Scope amendments** (measured paths the scope did not name, recorded with `forge stage amend-scope`)

- factory/scripts/record_review_from_json.py -- The public review-generation recorder validation in record_review_from_json.py is required for Lean selected-review input and current reviewed-meaning identity; it was omitted from the task write_scope while its reviewed-meaning caller changed. Stage measurement identified this exact single path, with no other scope addition.

**Required tests** (run by `stage done`)

- `test_native_approval_refuses_zero_multiple_candidates_replay_and_missing_identity` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_approval_hooks.py)
- `test_native_approval_records_human_via_runtime_identity_without_display_name` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_approval_hooks.py)
- `test_native_approval_reuses_existing_story_and_task_approval_storage` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_approval_hooks.py)
- `test_native_plan_mode_approval_records_exact_digest_for_claude_exit_plan_mode` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_lean_workflow.py)
- `test_native_plan_mode_approval_records_exact_digest_for_codex_sync_approval` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_lean_workflow.py)
- `test_native_approval_refuses_stale_wrong_runtime_canceled_async_and_unsupported_payloads` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_lean_workflow.py)
- `test_normal_flow_no_longer_requires_requirements_grill_manual_approval_or_second_save` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_lean_workflow.py)
- `test_delegate_scope_must_be_strict_subset_of_approved_write_scope` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_delegate_scope.py)
- `test_delegate_scope_is_bound_to_brief_launch_identity_and_existing_write_scope` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_delegate_scope.py)
- `test_hook_refuses_write_outside_narrowed_delegate_scope` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_delegate_scope.py)
- `test_delegate_brief_carries_criteria_and_scope` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_gates.py)
- `test_native_worker_patch_add_update_delete_and_move_is_admitted` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_worker_admission.py)
- `test_context_file_security_no_follow_modes_identity_capacity_and_cleanup` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_delegate_scope.py)
- `test_context_file_launch_uses_one_handle_snapshot_and_metadata_only_evidence` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_worker_admission.py)
- `test_unchanged_test_verify_and_selected_review_inputs_reuse_success_without_rerun` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_proof_reuse.py)
- `test_changed_unknown_partial_or_generated_output_identity_forces_fresh_run` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_proof_reuse.py)
- `test_reuse_identity_is_proof_type_specific_and_reviewed_meaning_bound` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_proof_reuse.py)
- `test_selected_review_reuses_for_bookkeeping_only_changes_and_preserves_original_provenance` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_proof_reuse.py)
- `test_selected_review_reruns_for_changed_acceptance_security_migration_or_evidence` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_proof_reuse.py)
- `test_selected_upgrade_generation_requires_exact_sealed_binding` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_review_settled_contracts.py)
- `test_selected_review_reviewed_meaning_includes_ci_generated_outputs_and_review_instructions` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_review_task_delta.py)
- `test_selected_review_reruns_for_substantive_automated_evidence_change` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_review_task_delta.py)
- `test_lean_migration_refuses_dirty_checkout_before_writing` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_upgrade_lean_workflow.py)
- `test_lean_migration_force_cannot_bypass_dirty_tree_refusal` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_upgrade_lean_workflow.py)
- `test_lean_migration_independent_raw_walk_covers_each_candidate_exactly_once` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_upgrade_lean_workflow.py)
- `test_lean_migration_inventories_hashes_temp_validates_publishes_and_reads_back` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_upgrade_lean_workflow.py)
- `test_lean_migration_refuses_malformed_mixed_partial_conflicting_or_linked_inputs` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_upgrade_lean_workflow.py)
- `test_lean_migration_is_idempotent_for_byte_identical_retry_and_refuses_unequal_partial_retry` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_upgrade_lean_workflow.py)
- `test_lean_migration_forces_fresh_review_for_active_old_proof_and_migrates_only_exact_sealed_proof` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_upgrade_lean_workflow.py)
- `test_normal_runtime_refuses_lean_removed_formats_with_upgrade_guidance` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_upgrade_lean_workflow.py)
- `test_codex_hook_readiness_requires_exact_enabled_trusted_source` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_native_setup.py)
- `test_codex_hook_readiness_accepts_only_identical_inherited_worktree_hooks` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_native_setup.py)
- `test_model_policy_selects_sol_work_and_luna_lite` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_native_setup.py)
- `test_active_model_policy_has_no_forbidden_execution_surface` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_gate_table.py)
- `test_project_agents_init_upgrade_and_preserve_client_additions` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_gates.py)
- `test_recovery_profile_override_keeps_only_three_forge_profiles` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_native_setup.py)
- `test_upgrade_preserves_client_profiles_while_removing_retired_forge_profiles` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_gates.py)
- `test_upgrade_preserves_project_settings_and_refuses_unknown_same_name_profile_rows` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_gates.py)
- `test_pr_link_workflow_stages_per_event_files_not_legacy_jsonl` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_pr_link_workflow.py)
- `test_pr_link_workflow_status_description_names_per_event_link_commit` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_pr_link_workflow.py)
- `test_verified_forge_acc3_and_cfs1_pr_links_make_board_complete` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_pr_link_workflow.py)
- `test_history_merges_legacy_and_per_file_events` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_gates.py)
- `test_pr_link_event_survives_a_clone_with_no_remote` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_gates.py)
- `test_forge_history_shows_the_pr_link` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_gates.py)
- `test_signal_ruling_hydration_survives_lean_lifecycle_state_changes` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_gates.py)
- `test_generated_review_inputs_are_included_in_reviewed_meaning` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_review_task_delta.py)
- `test_measurement_receipt_authenticates_its_native_launch_not_a_later_one` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools FORGE_REQUIRED_SELECTOR={id} uv run --python 3.11 --with pytest --with psutil python -m pytest {path} -o junit_family=legacy --junitxml={report}` (factory/tests/test_regrill_scope.py)
- `test_one_cold_grill_full_disposition_replaces_round_floors_and_frontier_fake` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_lean_workflow.py)
- `test_recovery_override_removes_round_ledgers_without_losing_cold_read_proof` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_lean_workflow.py)
- `test_lean_docs_match_single_cold_grill_runtime` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_plan_against_reality.py)
- `test_native_approval_no_longer_routes_through_board_or_manual_approve` -- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with psutil python -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}` (factory/tests/test_board_approval_gate.py)

**Verify commands**

- `UV_CACHE_DIR=/tmp/forge-lean-uv-cache UV_TOOL_DIR=/tmp/forge-lean-uv-tools uv run --python 3.11 --with pytest --with pytest-xdist --with psutil python factory/scripts/verify.py`
- `python3 factory/scripts/check_dual_runtime.py`
- `python3 factory/scripts/check_encoding_hygiene.py`
- `python3 factory/scripts/check_board_complete.py`
- `git diff --check`

**Review budget.** 99 files / 14500 lines -- Lean recovery PR2 spans native approval eligibility, context-file security including native Windows protected DACL proof, narrowed delegation, reviewed-meaning close reuse, clean-target and independently covered Lean migration/deletion including sealed fixed-proof migration, three-profile pruning with settings/profile preservation, PR-link repair, docs/runtime alignment, and the amended Portable PR3 handoff; stop for amendment if measured diff exceeds this budget. One-time 2026-09-15 amendment from 96 to 97 changed files solely for the existing factory-scaffold Windows PR job to run the native protected-DACL context-file selector; no product check is removed, and the 14,500-line ceiling and native Windows proof obligation remain. One-time current-main integration amendment from 97 to 99 changed files covers only the imported PR 219 closeout-marker fixture and the existing delegation schema field needed to seal terminal cold-result bytes; no proof or platform check is removed, and the 14,500-line ceiling remains.
<!-- /forge:contract -->
