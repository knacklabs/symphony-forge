---
status: accepted
confirmed_by: "User (Codex conversation)"
date: 2026-09-08
stories: [FORGE-COORD-1]
---

# Native questions and task proof preserve one workflow

## Context
The dual-coordinator audit exposed a gap between the requested task-level proof
and older once-per-story wording, and an option-only question rule that lost
free-text answers. The user explicitly directed free-text acceptance, native
question tools and no forced manual Plan-mode switch. Through the structured
scope questions, the user selected “Include shared repairs” and “Review PR
first”, then explicitly authorized the bounded question-tool bootstrap repair.
This record codifies those choices; it introduces no additional user decision.

## Decision
Both coordinators use their native question tools: Claude AskUserQuestion and
Codex request_user_input where the runtime permits the intended interaction.
Accept a single nonblank free-text answer as well as an offered option, keeping
the exact submitted text, event/question identity, story eligibility and
single-use consumption. A response is not automatically plan approval. Forge
does not impose a manual Plan-mode switch; actual host tool restrictions still
apply and missing completed-event delivery cannot be fabricated.

Implement the selected shared repairs: avoid invalidating a plan grill solely
because managed save metadata changed; deliver required skills through existing
phase launchers and canonical prompts; enforce existing per-task verify, tests,
three review lenses and conditional functional proof before normal task PR
readiness. Review includes the complete approved task plan and its actual task
evidence, and repeats with delegated fixes until no actionable findings remain.

A draft PR for review and green CI may precede unavailable platform observations,
with every gap declared. It grants no task-ready marker, shipped status or full
platform certification. Normal task readiness and final release retain their
proof requirements.

## Consequences
This amends only the older once-per-story proof timing in Decisions0001/0007
and Decision0047's closeout consequence. Stage-local certification remains,
each task carries its own proof, and story closeout consumes shipped task proof
without replacing the task reviews. The task-worktree, marker-on-main and human
merge rules remain. Proposed Decision0049 is not accepted by this amendment.

Decision0053's prohibition on relaxed round matching continues to prohibit
relaxing exact event/question/submitted-text matching, story eligibility and
replay prevention; it does not prohibit free text. Both coordinator routes keep
the same worker models, independent review ownership and normal approvals.
Recorded consumption is not permission to bypass current story eligibility.

The explicitly authorized question bootstrap is pre-stage work with focused
tests and independent review; it cannot supply a normal task's delegated
contribution. The remaining shared repairs follow the bounded approved task
route. No new coordinator framework, evidence family, expiry timer or synthetic
approval is authorized.
