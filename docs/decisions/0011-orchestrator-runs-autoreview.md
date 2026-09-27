---
status: superseded
superseded_by: 0093-lean-forge-rebuild
confirmed_by: "vrknetha"
date: 2026-07-24
stories: []
---

# Orchestrator Runs Autoreview

## Context
Review was specified as "ONE autoreview pass in Codex". In practice the
Codex review job loads the very same autoreview skill inside a nested Codex
session — the orchestrator delegates to a wrapper that re-triggers the skill
one indirection deeper, adding latency and a second runtime without adding
signal. Observed during FORGE-INIT-1 (2026-07-24), where five review rounds
each paid the wrapper cost. Directed by the maintainer in-session.

## Decision
The orchestrating session (Claude) runs the autoreview skill DIRECTLY — for
both the per-stage local pass and the ONE branch-wide review pass. After
every `/codex:rescue` implementation, the orchestrator loops autoreview →
fix → re-review on the uncommitted diff until it reports no findings; only
a clean diff commits. Review is never handed to a Codex review job; nested
reviewers stay forbidden.

## Consequences
One runtime fewer per review round; the orchestrator owns review quality
end-to-end and cannot commit around open findings. The reviewer-focus and
three-lens contract (`.agents/prompts/reviewer.md`) is unchanged — who runs
it changed, not what it checks. AGENTS.md, `.claude/CLAUDE.md`, and
WORKFLOW.md §stage-loop updated to match.
