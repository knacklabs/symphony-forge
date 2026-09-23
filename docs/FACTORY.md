# FACTORY.md

## Purpose

This document is the operating contract for the factory beyond the short root `AGENTS.md`.

## Runtime

Either Claude Code or native Codex may coordinate the same phase engine. Claude
dispatches Codex through `codex-plugin-cc`; native Codex uses role-based host
`spawn_agent` subagents. Native dispatch passes no model/reasoning override, so
the selected configured role's defaults apply. The active
coordinator owns the human conversation and orchestration. Both routes preserve
the same task scope and `.factory` contract, while native delivery makes no
Forge-managed process-attribution claim.

## Prompt Usage Model

Prompt files under `factory/prompts/` are explicit phase contracts.

They are used in three ways:
- `SessionStart` reports run state
- `PreToolUse` guards Bash commands at phase gates
- Claude's `Stop` hook enforces active-stage continuation while implementation
  artifacts are incomplete; native Codex `Stop` is advisory and host-owned.
- the parent Codex session explicitly loads the relevant phase prompt before acting
- custom agents use their own `.codex/agents/*.toml` instructions as role-specific prompts

Hooks are not the workflow engine. They only add guardrails and continuation logic.

## Factory Phases

0a. `discovery` — lightweight problem, stakeholder, and constraint discovery. It does not require `.factory` ceremony.
0b. `prototype` — prototype freely and save capability specs as they emerge. It does not require `.factory` ceremony.
0c. `roadmap` — confirm every spec, then derive epics and stories from them.
1. `planning`
2. `decomposing`
3. `awaiting-approval`
4. `implementing`
5. `testing`
6. `reviewing`
7. `functional-check`
8. `pr-ready`
9. `done` or `blocked`

The sign-off gate sits between roadmap derivation and planning, and fires ONCE
for the project. `record_signoff.py` requires at least one confirmed spec, a
derived roadmap with at least one story, and coverage of every confirmed spec.
It then pins that record in `harness.yaml` (`signoff_record:`); the gate is
derived from that committed pin rather than stored in `.factory/run.json`.

Phases at `planning` or later are refused by `update_run.py` and `pre_tool_use.py` until `client_signoff` is true.

## Recommended Specialist Set

Minimum set for a production run:
- `planner-high`
- `docs-decomposer`
- `functional-checker` (user-facing tasks only)
- the autoreview skill (one run, three review lenses)

The implementer writes, runs, and records the automated tests — there is no
separate tester agent. This is enough for planning, decomposition,
implementation support, testing, and isolated review. Add more agents only
when the repo has a repeated bottleneck that justifies another role.

## Reasoning Matrix

The user and host select the main coordinator model and reasoning; the
repository does not set either at the top level. Native dispatch names a
configured role and passes no model or reasoning override. Decision 0083
defines the role defaults:

- routine implementation, automated tests, diagnosed or review fixes,
  documentation edits, and mechanical refactors (`coder`, `frontend`,
  `tester`, `refactorer`, `worker`, the default implementation role, and
  bounded `lite`) use `gpt-6-luna` at `max` reasoning;
- read-heavy exploration and dependency tracing (`explorer`) use
  `gpt-6-sol` at `medium` reasoning;
- planning and decomposition (`architect`, `planner`, `planner-high`, and
  `docs-decomposer`), difficult diagnosis (`debugger`), independent grills
  (`griller`), and final functional checks (`functional-checker`) use
  `gpt-6-sol` at `high` reasoning;
- formal code review uses only the unchanged, externally maintained Autoreview
  skill. Its internal Codex or agent calls are its own policy and are not a
  Forge-native role override.

A difficult diagnosis returns its resolved edit to the Luna/max execution
role. The thread `forge delegate` or `forge fix` launches is the
task lead on `gpt-6-sol` at `medium` (the `implementation` and `modes.lite`
pins); it plans and verifies and hands the edits to Luna/max subagents.
No Forge or native configuration selects Luna with low reasoning.
Native transport remains process-free: Forge prepares the validated dispatch
descriptor, Main sends it to the host role, and the host owns subagent
lifecycle. Forge adds no process, session, PID, launch-token,
foreground/background, status, cancellation, resume, recovery, or
authorship-attribution proof.

## In-Repo Docs Contract

The generated application repo is self-contained.

Put source material directly in:
- `docs/product/BRIEF.md`
- `docs/architecture/`
- `docs/decisions/`

Use:
- `docs/product/README.md` for the product brief contract
- `docs/architecture/README.md` for the architecture doc contract
- `docs/decisions/README.md` for the decision record contract

Optional supporting docs can live in:
- `plans/`
- `docs/product/`
- `docs/operations/`

Planning and decomposition should read only the in-repo docs, not an external source repo path.

## Decomposition Rules

The planner owns decomposition.

Decompose by:
- capability
- runtime seam
- data boundary
- vertical slice

Do not decompose by:
- markdown file
- ADR count
- arbitrary file count
- implementation agent convenience

The first decomposition records the ordered task list. Each leaf initially
includes:
- id
- title
- objective
- non-empty acceptance criteria
- dependencies when needed; every dependency names an earlier task

Immediately before the next pending leaf, enter native Plan Mode per
`factory/prompts/planner.md` and author its execution contract against the
state left by completed tasks: write scope, exact acceptance criteria, verify
commands, required tests, and reviewer focus. Re-record the decomposition,
save the plan-mode result at `.factory/stories/<KEY>/task-plans/<id>.md`,
run one independent cold grill, record its complete finding dispositions and
amendment bridge, then record native human approval of the final digest. Run
`forge stage start <id>`, then `forge delegate <id>`. Under native Codex, use
the returned canonical brief and dispatch data to spawn the matching configured
role through the host; the command records a preparation row including any
narrowed scope, and Forge does not invoke `codex exec`. Under Claude, the
command launches the protected plugin companion. Do not guess later-task
execution detail. `forge next` routes this loop one action at a time.

If an already approved plan is amended before stage start, record the amendment
bridge against the existing cold proof and return directly to exact native
approval of the amended digest; do not launch a second cold grill solely for
changed bytes.

For that native plan grill, `./forge grill run --gate plan --file <plan-file>`
prepares one descriptor bound to the exact artifact. Main includes the complete
descriptor and all context metadata in the actual `spawn_agent` message to the
configured `griller` role, then records its exact JSON with `python3
factory/scripts/record_grill_from_json.py --gate plan --input <grill-json>
--input-digest <plan-file> --cold-result <path> --preparation-id <id>`. A
native task grill uses `./forge grill run --gate task --task <id>` and
`python3 factory/scripts/record_grill_from_json.py --gate task --task <id>
--input <grill-json> --cold-result <path> --preparation-id <id>`; task gates
have no `--input-digest`. Claude retains its command-managed cold-reader
lifecycle.

Raw/direct/nested `codex exec` and direct plugin shell launch are off-contract
and hook-denied for general or manual delegation in both runtimes. The
authenticated Forge-managed autoreview helper is an externally maintained
black box and may invoke Codex or agents internally. Native writes still
require the active task, matching worktree and effective scope.

Forge applies no native process/session/PID registration,
foreground/background policy, or status/cancel/resume/recovery restriction.
Native host features stay available as designed, and stage close does not
require launch-process proof. The task scope, diff, tests, deterministic verify,
independent review and PR gates remain unchanged.

Each task closes through `forge task close <id>`: after implementation and
focused checks, commit the product changes; `close` runs the declared proof
once for that close and records it as the task's `verify.json` and `tests.json`.
A later close reuses a passing proof only when its complete command,
environment, tool, distribution, generated-input, and product identities
match; unknown command shapes stay conservative and run again (0079). It
runs one three-lens review only when the product delta is not already stamped,
and checks the complete task-owned automated proof before it measures and
closes the stage, writes the task marker, pushes and opens the PR. For a
`user_facing: true` task, close stops until the functional checker records its
proof; record that proof, then rerun `./forge task close <id>` so the unchanged
selected review is reused and the stage is sealed. The lenses run concurrently
by default; blocking findings are fixed in one delegated batch, committed, and
`close` is rerun. Wait for that PR's CI and merge before starting the next task.
Once every task marker and its proof are on trunk, record the story outcome and
run `pr_ready.py`; no second story review or verify is required. Follow
`docs/QUALITY.md` bounded recovery when progress stalls.

Store the decomposition in `.factory/stories/<key>/decomposition.json` — that
story-scoped artifact is canonical. Mirroring into a tracker (Linear, GitHub
Issues, Jira) is optional.
Order is derived, never authored (decision 0021): the array is the execution
sequence and a task's `dependencies` may only name an earlier task.

## AGENTS Hygiene

Root `AGENTS.md` should stay near 100 lines.

Mechanically enforce:
- size cap
- required headings
- linked-doc existence
- no large duplicated policy blocks

Maintenance cadence:
- per PR: lint AGENTS and docs links
- weekly: stale rule scan
- monthly: compact overgrown instructions
