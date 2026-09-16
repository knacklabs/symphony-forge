---
status: superseded
confirmed_by: "User (explicit model policy, Claude plugin parity and committed team configuration instructions, Codex conversation 2026-09-10/11)"
date: 2026-09-11
stories: [FORGE-COORD-1]
supersedes: 0062-luna-max-exploration-and-implementation
superseded_by: 0074-user-selects-main-orchestrator-model
---

# Sol-specialized workflow models with Luna Max Lite

## Context

The user replaced the prior model policy across Symphony Forge. The committed harness still selected Terra for exploration and grills and Luna/max for ordinary implementation, while the supported launcher exposed no per-run model override. That made the first policy correction impossible through a worker already selected by the desired policy.

The orchestrator opened degraded window Q-0130-305e for the one-file `harness.yaml` bootstrap. A Sol/medium host agent changed only that file and the resulting selectors validated, but desktop `apply_patch` did not register the file in the window ledger. The orchestrator therefore abandoned the window with the real tracking limitation instead of claiming completed degraded proof. The retained diff is reviewed and proved through the amended task's normal Sol/high grill, Sol/medium registered worker, verification and formal review.

## Decision

Use these current execution lanes:

- read-only exploration: `gpt-5.6-sol` at low;
- planning, decomposition, architecture, plan validation and grills: `gpt-5.6-sol` at high;
- all implementation, technical test verification and autoreview fixes: `gpt-5.6-sol` at medium, except the formal Lite lane below;
- formal Lite: `gpt-5.6-luna` at max;
- formal autoreview: `gpt-5.6-sol` at high through the installed autoreview skill;
- functional checking: `gpt-5.6-sol` at high.

No new execution actor may be selected with Terra. The currently executable project profiles and planner definitions make deferral false, so First owns the complete additional policy overlay: owning harness/launcher selectors, every active profile and guidance reference, all 15 committed team agent definitions, exact init/upgrade distribution proof, and same-plugin Luna/max doctor compatibility. This new-request overlay does not reassign any original prepared hunk; the amended ownership graph retains all original 40 path/hunk allocations and records the overlay separately. This decision supersedes Decision 0062. It amends only the model-selection clause of Decision 0031; 0031's Lite ledger, five-file bound, review and close contract remain in force. Historical plans, launch rows, reports and transcripts retain the models that actually produced them and do not become current selector authority.

This also amends only Decision 0057's instruction to remove the three `planner-high`, `docs-decomposer`, and `functional-checker` definitions and omit them from delivery. Those definitions remain in the 15-agent team and ship through the existing distribution paths. Decision 0057's synchronous-question requirements remain active as narrowed by accepted Decision 0064, and its roadmap-edit, logical-role, coordinator, and gate requirements remain active.

This also amends only Decision 0065's instruction to preserve the first native task's existing write scope, and the matching scope limit in `plans/lessons/20260910T170240-0000-first-native-scope-correction-authorization-170240173755.json`, for the later, explicitly user-requested model/team-policy overlay. First may add the owning selector, profile, guidance, agent, distribution, doctor, and selector-regression paths required by that overlay while preserving every original prepared path/hunk allocation, the source/target binding, and the eight-task graph. All other Decision 0065 obligations remain active.

Commit `.codex/config.toml`, `.codex/explore.config.toml` and concise `.codex/agents/*.toml` definitions as team policy. Forge init copies the complete agent tree; upgrade uses its existing same-name harness refresh and preserves distinct client-added agent files, without a new TOML merge or provenance mechanism. Claude coordination continues to use the same `codex-plugin-cc` route, including Luna/max Lite; `forge doctor` must prove max support or repair only an exact known official installation and otherwise fail before mutation.

## Consequences

The amended First task re-grills at Sol/high and produces a distinct registered Sol/medium contribution and current-plan C8 receipt. The implementer returns actual receipt paths and identities; after exit the root orchestrator alone copies the current transcript/source-check files into the external audit directory, leaving all original C8 files immutable. Its remaining work updates the selector regressions and confirms the existing uncommitted digest-cache repair; the small worker-admission ledger scan is consciously retained as a non-blocking 20 KB/12-row cost rather than expanded into a new index. The original Luna/max C8 launch, receipt and transcript remain unchanged history. First owns the complete current model-policy migration. `LEAN-WORKFLOW` retains its original workflow simplification plus the separately discovered PR-link event-staging fix. Shared consumes Decision0070 rather than owning Remaining0062 model selection; Portable preserves and refreshes the team registry during later client rollout rather than retiring it. No selector monkeypatch, lower-level launch, model downgrade, fabricated outage, untracked manual plugin-cache workaround or task-graph change is permitted.
