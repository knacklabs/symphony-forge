# AGENTS.md — Symphony Forge

## What This Repo Is

Symphony Forge is a dual-runtime software-factory template for turning in-repo architecture and decision docs into shipped applications.

It provides:
- planner-owned decomposition
- bounded implementation tasks
- deterministic verification
- schema-validated evidence recording
- autoreview-owned review
- PR-ready proof artifacts

## Context and Read Order

Read nearest `AGENTS.md`, active brief, binding decisions/contracts, and affected
source/tests. New or changed capabilities also read applicable architecture,
confirmed specs, product brief, active decisions, roadmap, plan, and decomposition.
Status, Lite, and prepared corrections skip unrelated canon; constitution and
accepted contracts bind every executor.

## Runtime Modes

Claude uses protected `codex-plugin-cc`; native Codex uses host `spawn_agent`. `forge delegate` validates and prepares briefs; native dispatch passes no model/reasoning override. Raw/nested `codex exec` and direct plugin shell launch are denied for manual delegation. Autoreview is an external black box and may use Codex or agents. Forge keeps task/worktree/scope/proof/PR gates without native process/PID/lifecycle lock or attribution.

## Phase Contract

Follow `WORKFLOW.md` for discovery through PR delivery and `docs/FACTORY.md`
for the factory reference. Sign-off requires confirmed specs and a derived
roadmap; implementation requires an approved plan and recorded decomposition.

## Prompt and Agent Use

Prompt files under `factory/prompts/` are phase contracts; hooks load context and enforce gates. Native Codex uses configured role subagents for task work and cold grills. Put each full descriptor and its context metadata in the actual spawn message, then record the exact grill result. See [shared Forge guidance](factory/skills/forge.md#codex-native-use-host-subagents).

Use the host's structured request tool for every supported user question. Claude
plan authority is a successful `ExitPlanMode`; Codex plan authority is the
digest-bound synchronous approval in `docs/specs/plan-approval.md`. Direct chat
never substitutes for plan authority.

Default specialist set:
- `planner-high`
- `docs-decomposer`
- `functional-checker` (user-facing tasks only)
- autoreview skill (review — three lenses, one run; 0078)

Testing has no separate agent: the implementer writes and records the tests.

## Reasoning Defaults

Main coordinator model/reasoning are user/host choices; native dispatch passes no override.
0083 routes Luna/max to routine work (implementation, tests, fixes, docs,
refactors); Sol/medium to exploration/tracing; Sol/high to planning,
decomposition, difficult diagnosis, independent grills, final functional checks.
Delegated/lite threads lead on Sol/medium; edits go to Luna/max subagents.
Formal review: unchanged external Autoreview
(internals own policy); no lane selects Luna/low. Native transport process-free;
no Forge lifecycle/authorship proof.

## Deterministic Commands

Devs speak intents; the `/forge` skill maps them to these commands.
Lost? `./forge next` prints the current phase and exact next actions.

```bash
python3 factory/scripts/intake.py --issue ENG-123 --title "Feature title"
python3 factory/scripts/record_decomposition_from_json.py --input /tmp/decomposition.json
python3 factory/scripts/update_run.py --phase awaiting-approval --plan-status awaiting-approval
./forge task close <task-id>
./forge outcome set "<what changed and what someone can now do>"
python3 factory/scripts/pr_ready.py
```

## Hard Gates

Task proof lives in `.factory/stories/<key>/tasks/<id>/`:
`verify.json`, `tests.json`, and `reviews/selected.json` with its immutable
selected-generation lineage. Those output files alone are not current authority:
their content-bound stage proof receipts and selected reviewed-meaning identity
must also match; see `docs/QUALITY.md`. Fixed lens files are diagnostic or
migration input only. Plan, `run.json` and
`decomposition.json` stay story-scoped. Review inputs and local/CI/board proof checks follow `docs/specs/dual-coordinator-parity.md`.

A story ships with every task marker and clean proof on trunk. Closeout never
re-verifies. Story proof is only `outcome.json` (`./forge outcome set`).

## Non-Negotiables

- Constitution binds every executor/environment: follow/cite `constitution/README.md`; never re-derive. Approval locks contract to PR open; material changes need human authorization: shipped → new task; done/unshipped → `forge task reopen`; active → amend + fresh native approval per `docs/QUALITY.md`; never reshuffle graph alone.
- Every executor applies Ponytail to code edits: YAGNI → reuse → stdlib → native → installed dep → one line → minimum viable. Keep validation, error handling, security, accessibility; brief-inlined, review-enforced; no recording gate.
- Bound tasks by capability; each plan binds one roadmap story and attests all active decisions.
- Plan, task-scope and protected-state gates stay armed. Claude uses its plugin companion and degraded outage valve; native uses host subagents without Forge process identity or lifecycle locks.
- Do not decompose by document file or arbitrary file count or bypass `verify.py` with ad hoc validation commands.
- Only schema-validated recorders write evidence into `.factory/`. Review publication validates immutable prompt meaning; preserve approval and captured-context boundaries in `docs/specs/dual-coordinator-parity.md`.
- Narration budget (conduct §8): one line per state change; findings and refusals always in full; process chatter never.
- Follow [bounded recovery](docs/QUALITY.md#bounded-recovery) in every phase; repeated unchanged failures need a diagnosed, tested fix before another model run.
- One integrated `./forge task close <id>` cycle owns proof/review/finish: preflight launch, review bounds and required-test paths before expensive proof; recheck mutable state at finish; one full factory suite at a time per shared host.
- ONE three-lens pass per task is owned by `./forge task close <id>`; only unchanged external Autoreview runs it. Loop review → delegate Luna/max fixes → re-review until clean; record before `pr-ready` per accepted 0011, 0054 and 0069. `./forge review <id>` is diagnostic/loop; its internal Codex/agent calls follow its own policy. Never review inline or nest reviewers.
- Each leaf task owns a worktree and PR; dependency-ready tasks parallelize only with disjoint measured scopes. Delegation/proof commands are trusted inputs; observed descendant cleanup is not hostile-code containment.
- Coordinate from the primary checkout on the default branch; approvals route by digest, while task edits need a task-worktree session; never `cd` outside a checkout.
- Keep the template repo independent of any client-specific source repo.
- Do not keep long policy blocks in `AGENTS.md`; move them into docs.
