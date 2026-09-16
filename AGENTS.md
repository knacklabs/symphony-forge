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

## Mandatory Read Order

1. `WORKFLOW.md`
2. `docs/FACTORY.md`
3. `docs/QUALITY.md` and `docs/ROLES.md`
4. `harness.yaml`
5. `constitution/README.md`
6. `docs/product/BRIEF.md`
7. `docs/architecture/` and confirmed capability specs under `docs/specs/`
8. active decisions — `./forge decision list --active`, not raw `docs/decisions/`
9. the derived roadmap, active plan, and decomposition artifacts

## Runtime Modes

Either Claude Code or native Codex coordinates discovery, planning, decisions,
and orchestration through the same Forge phase engine. The active coordinator
owns the human conversation; admitted Codex workers execute bounded
exploration, implementation, testing, and review. Both runtimes produce the
same `.factory` contract.

Protected implementation writes run through `./forge delegate`. The
orchestrating session releases ONE three-lens pass per task with `./forge
review <task-id>` (Codex-run, never a nested companion job; recorded as that
task's proof under accepted 0011, 0054 and 0069), watches it, and loops it until
clean, delegating fixes back to Codex. A five-file `forge mode degraded` window
is the ledgered outage exception.

## Phase Contract

Follow `WORKFLOW.md` for discovery through PR delivery, including native
approval, task execution, proof and review. Sign-off requires confirmed specs
and a derived roadmap; implementation requires an approved plan and recorded decomposition.

## Prompt and Agent Use

Prompt files under `factory/prompts/` are phase contracts. They are invoked explicitly by the parent session; hooks only load context and enforce gates. In Codex Desktop, keep one user-facing coordinator and separate task-owner chats/worktrees; follow the [shared Forge guidance](factory/skills/forge.md#codex-desktop-one-main-chat-separate-task-chats) for parallel tasks, monitoring, and ownership recovery.

Use the host's structured request tool for every user-facing question it permits. In Codex Default mode, use `request_user_input` for all optional questions; ask approvals and permissions directly in chat when the host reserves them for that channel, and state that restriction. When an approval gate is waiting, end the update with a direct approval question that names the exact artifact or digest.

Default specialist set:
- `planner-high`
- `docs-decomposer`
- `functional-checker` (user-facing tasks only)
- autoreview skill (review — three lenses, one run; 0078)

Testing has no separate agent: the implementer writes and records the tests.

## Reasoning Defaults

Main model/reasoning are host/user choices. Forge pins:
`.codex/config.toml`, `.codex/agents/*.toml`, `harness.yaml`; exploration Sol/low; planning/decomposition/architecture/grilling Sol/high;
implementation/review fixes reuse the active Sol/medium implementer; formal Lite Luna/max; formal review/functional checks Sol/high.

## Deterministic Commands

Devs speak intents; the `/forge` skill maps them to these commands.
Lost? `./forge next` prints the current phase and exact next actions.

```bash
python3 factory/scripts/intake.py --issue ENG-123 --title "Feature title"
python3 factory/scripts/record_decomposition_from_json.py --input /tmp/decomposition.json
python3 factory/scripts/update_run.py --phase awaiting-approval --plan-status awaiting-approval
python3 factory/scripts/verify.py
python3 factory/scripts/record_test_from_json.py --kind automated --input /tmp/automated.json
python3 factory/scripts/record_review_from_json.py --aspect quality --input /tmp/quality.json
./forge outcome set "<what changed and what someone can now do>"
python3 factory/scripts/pr_ready.py
```

## Hard Gates

Task proof lives in `.factory/stories/<key>/tasks/<id>/`:
`verify.json`, `tests.json`, and `reviews/selected.json` with its immutable
selected-generation lineage. Fixed lens files are diagnostic or migration
input only. Plan, `run.json` and
`decomposition.json` stay story-scoped. Review inputs and local/CI/board proof checks follow `docs/specs/dual-coordinator-parity.md`.

A story ships with every task marker and clean proof on trunk.
Closeout never re-verifies. Story proof is only `outcome.json`
(`./forge outcome set`).

## Non-Negotiables

- Constitution binds every executor/environment: follow/cite `constitution/README.md`; never re-derive. Approval locks the contract to PR open; all later changes need human authorization: shipped → new task; done/unshipped → `forge task reopen`; active → amend + re-grill; never reshuffle the graph unilaterally.
- Every executor applies Ponytail to code edits: YAGNI → reuse → stdlib → native → installed dep → one line → minimum viable. Preserve validation, error handling, security, accessibility. Brief-inlined; review-enforced; no recording gate.
- Keep tasks bounded and capability-driven; plans bind one roadmap story and attest all active decisions.
- The session write lock is always armed: delegate locked writes; use `forge mode degraded` only during a companion outage.
- Do not decompose by document file or arbitrary file count, nor bypass `verify.py` with ad hoc validation commands.
- Evidence enters `.factory/` only via schema-validated recorders (pinned `generated_by`), never by hand. Review publication and stamping must validate the meaning bound in the immutable prompt hash. Preserve the approval-path and captured-context boundaries in `docs/specs/dual-coordinator-parity.md`; cold proof binds the launched result bytes.
- Narration budget (conduct §8): one line per state change; findings and refusals always in full; process chatter never.
- Follow [bounded recovery](docs/QUALITY.md#bounded-recovery) in every phase; repeated unchanged failures need a diagnosed, tested fix before another model run.
- Use one integrated `./forge task close <id>` proof/review/finish cycle: preflight launch, review bounds, and required-test paths before expensive proof; recheck mutable state at finish; run only one full factory suite at a time on a shared host.
- Review = ONE three-lens pass PER TASK via `./forge review <id>`, run by Codex, looped until clean (review → delegate fixes → re-review) and recorded before `pr-ready` under accepted 0011, 0054 and 0069; never nested reviewers.
- Each leaf task owns a worktree and PR; dependency-ready tasks may parallelize only when their measured scopes are disjoint. Delegation/proof commands are trusted inputs; observed descendant cleanup is not hostile-code containment.
- Keep the template repo independent of any client-specific source repo.
- Do not keep long policy blocks in `AGENTS.md`; move them into docs.
