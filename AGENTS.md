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

Claude Code coordinates discovery, planning, decisions, and orchestration through `codex-plugin-cc`. Its hook always denies product and canon writes; planning exploration is delegated to Codex read-only runs.

Codex executes exploration, implementation, testing, and review. `./forge delegate` is the sole normal write path; a five-file `forge mode degraded` window is the ledgered outage exception. The `.factory` artifacts are required in either route.

## Phase Contract

0a. run lightweight discovery without `.factory` ceremony
0b. prototype freely; save and confirm specs as capabilities emerge
0c. derive the roadmap from confirmed specs
1. record client sign-off (the spec/roadmap gate is checked now)
2. plan one roadmap story and record its ordered task list
3. wait for approval
4. per task: plan-mode JIT contract → re-record → grill → stage start → `./forge delegate`; measure under 0018
5. run deterministic verify
6. run one autoreview pass (three lenses: quality, performance, security)
7. run the functional check when the decomposition says `user_facing: true`
8. record the shipped outcome, then mark PR ready

Recording sign-off requires confirmed specs plus a derived roadmap. Later
phases require sign-off; implementation also requires a plan and decomposition.

## Prompt and Agent Use

Prompt files under `factory/prompts/` are phase contracts. They are invoked explicitly by the parent session; hooks only load context and enforce gates.

Default specialist set:
- `planner-high`
- `docs-decomposer`
- `functional-checker` (user-facing tasks only)
- the autoreview skill (review — all three lenses, one run)

Testing has no separate agent: the implementer writes and records the tests.

## Reasoning Defaults

- planning / decomposition / architecture reconciliation: `high`
- read-only rescue (`/codex:rescue`, no `--write`) — reads only what its brief names, never the whole read order: `gpt-5.6-terra` @ `high` for code exploration, `gpt-5.6-sol` @ `xhigh` for plan validation / debugging / root-cause (the hard-thinking lane, not the default)
- implementation: `gpt-5.6-sol` @ `medium` (`high` for migrations/cross-domain/security)
- review and testing agents: explicit per-agent overrides

Do not default the entire repo to `high` reasoning for every task.

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

A task is not PR-ready until all of these exist:
- approved plan
- `.factory/run.json`
- `.factory/decomposition.json`
- `.factory/verify.json`
- `.factory/tests.json`
- `.factory/reviews/{quality,performance,security}.json`
- `.factory/outcome.json` (what the story delivered — `./forge outcome set`)

## Non-Negotiables

- The constitution binds HOW code is written (not just conduct) for EVERY executor — Claude, Codex, or any subagent, any environment: follow the `constitution/README.md` coding standards at implement/grill/review, cite them, never re-derive. Approval then LOCKS the contract until the PR opens — any post-approval change stops for the human (done+shipped is immutable → new task; done-but-unshipped → `forge task reopen`; active → amend + re-grill); never reshuffle the graph on your own authority.
- Keep tasks bounded and capability-driven; plans bind one roadmap story and attest all active decisions.
- The session write lock is always armed: delegate locked writes; use `forge mode degraded` only during a companion outage.
- Do not decompose by document file or arbitrary file count.
- Do not bypass `verify.py` with ad hoc validation commands.
- Evidence enters `.factory/` only via schema-validated recorders (pinned `generated_by`), never by hand.
- Narration budget (conduct §8): one line per state change; findings and refusals always in full; process chatter never.
- Review = ONE autoreview pass by the orchestrating session (0011); never a Codex review job, never nested reviewers.
- One worktree/story; sequential tasks; dependency-ready stories may parallelize (0002). Delegation/proof commands are trusted inputs; observed descendant cleanup is not hostile-code containment.
- Keep the template repo independent of any client-specific source repo.
- Do not keep long policy blocks in `AGENTS.md`; move them into docs.
