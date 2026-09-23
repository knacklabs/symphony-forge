---
status: superseded
confirmed_by: "User (explicit native role routing correction, Codex conversation 2026-09-18)"
date: 2026-09-18
stories: [FORGE-COORD-1]
supersedes: 0074-user-selects-main-orchestrator-model
superseded_by: 0083-native-role-model-routing-on-gpt-6
---

# Native role model routing

## Context

Decision 0074 correctly left the main coordinator model under user and host
control, but it also pinned all ordinary native children to Sol. The user has
now selected a cheaper role-specific child policy: routine execution should use
Luna at maximum reasoning, repository exploration should use Terra at high
reasoning, and the few judgment-heavy gates should retain Sol at high
reasoning. Formal code review remains owned by the independently maintained
Autoreview skill.

## Decision

The repository continues to omit top-level coordinator model selectors. Native
child roles are pinned as follows:

- `coder`, `frontend`, `tester`, `refactorer`, `worker`, `lite`, and the
  default implementation child use `gpt-5.6-luna` with `max` reasoning.
- `explorer` uses `gpt-5.6-terra` with `high` reasoning for read-heavy
  exploration and dependency tracing.
- `architect`, `debugger`, `planner`, `planner-high`, `docs-decomposer`,
  `griller`, `security`, `performance`, and `functional-checker` use
  `gpt-5.6-sol` with `high` reasoning.

Routine implementation and automated tests use Luna/max. Diagnosed fixes return
to a Luna/max implementation role; `debugger` is for difficult diagnosis, not
the subsequent edit. Documentation edits and mechanical refactors are
execution work and use Luna/max. Native dispatch names the role and does not
duplicate model or reasoning overrides at the call site. Formal code review
stays exclusively with the unchanged, externally maintained Autoreview skill,
which may manage its own internal Codex or agent calls.

The main coordinator model and reasoning remain the user's and host's choice.
No Forge configuration may select Luna with low reasoning.

This keeps the prior native transport contract: `forge delegate` prepares and
validates the task descriptor, Main sends it to the host's role-based
`spawn_agent`, and Forge does not invoke `codex exec` or add process, session,
PID, ancestry, launch-token, foreground/background, status, cancellation,
resume, recovery, signal, lifecycle-metric, or authorship-attribution proof.
The host owns native subagent lifecycle.

## Consequences

Forge distributes the full role registry through init and upgrade. Upgrade
still recognizes exact retired profile hashes while preserving distinct
client-owned profiles. Configuration, harness guidance, role documentation and
tests assert the same routing. Effective runtime proof comes from fresh native
child metadata after the project registry is reloaded; static TOML checks alone
prove only the committed policy.
