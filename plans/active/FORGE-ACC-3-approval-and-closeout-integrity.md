---
issue: FORGE-ACC-3
title: Approval and closeout integrity
status: approved
saved: 2026-08-19T04:53:46+00:00
story: FORGE-ACC-3
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
  - 0046-scoped-layout-activation-ordering
---

# FORGE-ACC-3 story plan — Approval and closeout integrity

Authored fresh off main @8f1d053 after FORGE-CFS-1 (#109) merged: this story
now BUILDS ON the story-scoped layout rather than coordinating with it in
parallel. Approval is a `forge task approve` recorder command; the hygiene-pin
redesign and both review debts are in scope.

## Problem

The loop's front half is mechanical (skeletal frontier, proof-carrying grills,
derived grounding, budgets — shipped by ACC-1/ACC-2). Approval and closeout are
still convention: an approved plan can be edited and silently re-legitimized on
re-record; a task's operator approval lives implicitly in chat, not as a
refused-without artifact stamped AFTER the grill; nothing interrogates the
confirmed spec against repo reality before a plan is drafted; the per-stage
local review records nothing and gates nothing; `stage done` accepts
uncommitted work; the three review lenses need not be one coherent run over the
branch brief; closeout artifacts can record in any order; a lite/quickfix/
degraded write window can open mid-stage. Sol's audit named all of these; the
spec's ACC-3 block (operator-amended twice) fixes their shapes.

## Scope / Non-goals

**In scope:** the eight roadmap ACs (approved-plan digest binding; post-grill
`approved_by` stamp expanded to a deterministic per-task loop
(grill -> plan-in-plan-mode -> `forge task approve` -> stage start); pre-draft requirements round; local-review stamp +
commit-before-done; coherent one-run branch review; ordered closeout with
clean-tree `pr_ready`; write-window refusal during active stages) plus the
operator-added scope: content-fingerprint hygiene pins, griller.md
`criteria_map` payload example (a dict now), and reconciling the spec's
zero-rounds wording with the rounds-or-citation recorder rule.

**Non-goals:** re-litigating CFS-1's story-scoped layout (merged; this story's
gates READ its `.factory/stories/<KEY>/` shapes but change no layout).
Lite/quickfix/degraded window internals unchanged beyond the mid-stage-open
refusal.

## Acceptance Criteria

The eight recorded roadmap ACs, plus:
9. `check_encoding_hygiene.py` pins by content fingerprint (path + normalized
   construct text + occurrence index), so insertions above a site no longer
   break scaffold-check; existing pins (incl. the FORGE-CFS-1 CI-fix line pins)
   migrate mechanically.
10. `factory/prompts/griller.md` shows the recorded task-grill payload shape
    (dict `criteria_map`, `rounds` with {question, options, chosen},
    `citations`); the spec's zero-rounds sentence is reconciled to the
    rounds-or-citation coverage rule.

## Technical Approach

- **Plan binding (`forge_cli/plans.py`, `factory_lib.py`):** approved
  `plan save` stores `approved_plan_sha256 = plan_digest_without_assumptions`
  in the approval marker; `record_decomposition_from_json.py` and
  `stage start` refuse when the live plan's digest differs from the APPROVED
  one; `plan approve` refuses without a fresh matching `--gate plan` grill.
- **Per-task plan-mode-approval gate (`forge_cli/tasks.py`, `forge.py`, recorder, `factory_lib.py`, `phase.py`, `grill.json`):** the operator's non-negotiable per-task loop, made deterministic (Codex-validated minimal design). Each task's plan is authored IN PLAN MODE and stored at `.factory/stories/<KEY>/task-plans/<id>.md` (via `evidence_path`) - not in `plans/active/`, not in the decomposition. New `forge task plan save <id> --from <path>` persists it (approval metadata stays OUT of the Markdown so stamping does not change its digest). New `forge task approve <id> --by "<name>"` refuses unless the task grill exists, passes, and is fresh, then stamps `approved_task_plan_sha256 = plan_digest_without_assumptions(plan)`, `approved_by`, `approved_at` into the grill record. Extend `require_ready_task(root, id, *, require_approval=True)` right after `require_task_grill`: task-plan exists, grill fresh, approval fields present, stored digest == current plan digest; `stage start` and write `delegate` already call this shared seam (no new local logic); `forge task approve` calls it with `require_approval=False`. Do NOT add the task-plan digest to `grounding_digest` (grill precedes plan authoring, so it would stale the grill). `task_frontier_state` derives (no new stored status): author-contract -> grill -> author-task-plan -> await-approval -> stage-start -> delegate; `phase.py` maps each to one [dev] action; `task_rows` uses the same predicates. A re-grill clears prior approval; an edited plan routes back to approval. Audited human attestation per 0029 - no crypto/signing/daemon.
- **Pre-draft requirements round (`forge_cli/phase.py`, recorder):** the
  planning branch's first action becomes a requirements re-grill of the story's
  confirmed spec against current repo state — a story-scoped grill
  (`.factory/stories/<KEY>/grills/requirements.json`, digest over spec body +
  product tree); `plan save` refuses without a fresh pass. Rounds via
  AskUserQuestion.
- **Local-review stamp + commit-before-done (`stages.py`, review recorder):**
  `record_review_from_json.py --aspect stage-local` writes a clean-review
  stamp into `stages.json` bound to {stage id, task digest, composed-brief sha,
  baseline, pre-commit product diff digest}; `stage done` refuses a
  missing/stale stamp, any uncommitted/staged product change, or an empty
  committed delta. The stamp is a gate token, not a fourth review artifact
  (0011 stands).
- **Coherent branch review (`review_brief.py`, review recorder,
  `pr_ready.py`):** `review-brief --all` mints `review_run_id` embedding
  the brief sha + branch diff digest; each lens artifact echoes all three and
  matches current branch state; `pr_ready` refuses lens sets that disagree.
- **Ordered closeout (`update_run.py`, `phase.py`, recorders,
  `pr_ready.py`):** shared `require_all_stages_done()`; prerequisite chain
  stages -> verify -> branch review -> functional (when `user_facing`) ->
  outcome -> `pr_ready` (verify gates before review, per AGENTS.md + reviewer.md); `pr_ready` additionally requires a clean product
  worktree/index, repo-kind-aware evidence exclusions, and the outcome stamp on
  the evidence commit. `quickfix/lite/degraded start` refuses while any stage
  is active.
- **Hygiene content pins (`check_encoding_hygiene.py`):** allowlists become
  {path, construct-fingerprint} (sha over normalized line text + occurrence
  index); the checker resolves fingerprints to lines at run time; a migration
  helper rewrites existing pins once (including the CFS-1 CI-fix pins).
- **Docs:** griller.md payload example; spec wording reconcile; WORKFLOW
  closeout order.

Reuse (all present on main @8f1d053): `plan_digest_without_assumptions`,
`grounding_digest`, `product_tree_digest`, `task_frontier_state`,
`require_ready_task`, `review_budget`.

## Decisions

Implements the accepted 0044 (accountable-engineering-loop) + 0045/0046
(conflict-free-story-state, now merged) lineage; the closeout order
(stages -> review -> verify) was operator-sanctioned in the spec amendment
round. The stage-local stamp deliberately does NOT create a fourth review
artifact (0011). All active decisions 0001-0046 reviewed; none conflict.

## Surface Impact

| Surface | Class | Notes |
|---|---|---|
| Runtime behavior | Changed | new refusals at plan approve/save, task approve, stage done, recorders, pr_ready, window start |
| API | Unchanged-by-design | no external API |
| Data/schema | Changed | grill record gains approved_by/approved_at; stages.json gains review stamp; review artifacts gain run binding; requirements grill artifact |
| CLI/ops | Changed | new `forge task approve`; `forge next` gains await-approval and requirements states |
| UI | Changed | board task rows show await-approval (shared derivation) |
| Docs | Changed | griller.md, WORKFLOW.md, spec wording |
| Tests | Changed | new gate coverage per task; hygiene-pin migration |

## Task Decomposition

Skeletal list, readable ids, contracts JIT:

1. **plan-approval-binding** — approved-plan digest stored and rederived;
   approve requires a fresh grill (AC 1).
2. **task-plan-approval-gate** — per-task plan file + `forge task plan save` + `forge task approve` (binds plan digest, stamps grill) + `require_ready_task` refusal (grill AND approval) + `task_frontier_state` routing author-contract->grill->author-task-plan->await-approval->stage-start (AC 2; operator's deterministic per-task loop).
3. **pre-draft-requirements-round** — requirements grill artifact + planning
   routing + plan-save gate (AC 3).
4. **local-review-stamp** — stage-local stamp recorder + commit-before-done
   refusals at stage done (AC 4).
5. **coherent-branch-review** — review_run_id binding across brief and lenses +
   pr_ready coherence (AC 5).
6. **ordered-closeout** — stage-completion gate, prerequisite chain, clean-tree
   pr_ready, mid-stage window refusal (ACs 6-7).
7. **hygiene-content-pins-and-doc-debts** — fingerprint pins + migration +
   griller.md/spec wording (ACs 9-10).

## Risks

- **Self-application:** this story runs under everything it builds; from task 2
  onward its own stage starts require the operator approval stamp (the
  dogfooding proof).
- **First new-layout story:** FORGE-ACC-3 is the first story intaken under
  CFS-1's activated layout — its evidence is story-scoped and its run pointer
  untracked (validated at intake). Its gates must read the story-scoped
  `.factory/stories/<KEY>/` shapes via CFS-1's evidence_path/story_dir helpers,
  not hardcoded singletons; each task's reviewer_focus enforces this.
- **Closeout order stays verify -> review** (grill 2026-08-19): the plan does
  NOT flip the order; ordered-closeout enforces stages -> verify -> branch
  review -> outcome, matching AGENTS.md and reviewer.md. No doc sweep of the
  "after verify" line needed.
- **Windows:** new digests reuse newline-stable helpers; no raw-byte hashing
  anywhere new.

## Verify Plan

- Per-task selections + full `verify.py` at closeout; `check_dual_runtime.py`
  throughout; `check_encoding_hygiene.py` before pr_ready (lesson: verify.py
  does not run it).
- Live self-check: from task 2 onward, every stage start in this story requires
  the recorded approval stamp.
- Hygiene: migrated pins survive a synthetic insertion test (add a line above a
  pinned site -> checker still passes).
