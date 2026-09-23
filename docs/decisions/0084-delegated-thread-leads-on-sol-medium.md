---
status: accepted
confirmed_by: "Ravi Kiran Vemula"
date: 2026-09-23
stories: [FORGE-COORD-1]
---

# Delegated Codex threads lead on Sol medium with Luna max subagents

## Context

Decision 0083 routes the implementation child roles (`coder`, `frontend`, `lite`,
`refactorer`, `tester`, `worker`) to `gpt-6-luna` at `max`. `harness.yaml` also
pins the `implementation` and `modes.lite` blocks to Luna/max, and `forge
delegate` / `forge fix` pass that pin as the delegated Codex thread's MAIN model
(`pinned_run_config` / `mode_run_config` in `forge_cli/delegate.py`).

That makes the Claude path differ from native Codex. A native thread is started
by the user on Sol and spawns Luna/max subagents (`.codex/config.toml`:
`multi_agent = true`, `default_subagent_model = "gpt-6-luna"`,
`default_subagent_reasoning_effort = "max"`). A delegated thread instead runs
Luna/max as its lead: it reads the full brief, plans, edits, and verifies alone.
On FORGE-COORD-1 LEAN-WORKFLOW (2026-09-23) three Luna-led fix threads spawned no
subagents at all, and round 1 shipped three regressions that existing tests and
checks caught (a dropped authority read, native `plans/` patches denied, a stale
encoding pin), plus two out-of-brief pauses. Those are planning and
self-verification misses, the work 0083 assigns to Sol, not typing misses.

## Decision

The delegated Codex thread is a task lead: `harness.yaml` `implementation` and
`modes.lite` pin `gpt-6-sol` at `medium`. The lead reads, plans, and verifies,
and delegates the edits to Luna/max subagents through the existing
`.codex/config.toml` defaults. Decision 0083's child-role routing is unchanged:
implementation roles stay Luna/max, exploration Sol/medium, and planning, grills,
review and functional checks Sol/high.

## Consequences

The lead thread's tokens move from Luna to Sol/medium; the edit-heavy tokens stay
on Luna through subagents. Delegated threads and native threads now share one
lead/child topology.

Briefs must direct the lead to delegate edits to `worker`/`coder` subagents and to
run the existing tests of every module it touches (lesson: fix-round briefs).
If Sol/medium leads prove too costly or no better, revert these two pins rather
than the child-role registry.

No Forge lane selects Luna at `low`, and the retired-model guard is unchanged.
