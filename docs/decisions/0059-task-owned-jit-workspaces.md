---
status: accepted
confirmed_by: "User (Codex conversation)"
date: 2026-09-09
stories: [FORGE-COORD-1]
---

# Task-owned JIT workspaces with dependency-ready scheduling

## Context

The developer asked for main to own story planning and grilling, followed by
one task conversation and worktree that owns detailed task planning through
its PR and green CI. Both Claude with its Codex companion and native Codex
must preserve the same approvals, worker policy and shipping gates.

Main at `221ab02` includes dependency-ready task scheduling from PR #191.
The implementation already checks effective dependencies and disjoint active
scopes. Older sequential and single-frontier clauses in Decisions0007,0018,
0021,0032,0044 and0047 do not describe that implementation. Decision0047 also
requires a detailed task plan and grill before creating the task worktree,
which prevents the task from owning that planning step.

This proposal reconciles those specific clauses. It does not accept itself,
approve the story/task graph, or admit any prepared native candidate.

## Decision

Main owns the story plan, independent story grill, frozen decomposition,
scheduling and all human questions. A task owns its detailed JIT contract,
independent task grill, implementation, tests, verification, autoreview and
fix loop, PR and green CI in one task worktree. Codex Desktop uses one
authorized app task for that owner; Claude remains one coordinator managing
the same Forge workspaces and Codex companion workers. CLI operation uses
available local coordination capabilities without requiring Desktop controls.

Create or attach the task workspace after story approval and before detailed
task planning. Require the current approved story and matching decomposition,
the correct story/task identity, refreshed exact trunk baseline and all
effective dependency markers on trunk. Normal attachment requires a clean,
unowned, registered worktree from the same Git common directory. Workspace
creation grants no product-write authority. Stage start and delegation retain
all existing JIT-contract, task-plan, grill, approval and admission checks.

Preserve the implemented dependency semantics: omitted or empty dependencies
fall back to the immediate predecessor; a nonempty explicit list selects the
stated dependencies. Dependency-ready tasks may run concurrently in distinct
worktrees only while their protected scopes are disjoint. The approved task
IDs, order and dependency graph remain frozen. A task may enrich only its own
permitted execution fields and must not rewrite sibling or completed contracts.

Progress is read from each verified owner using story plus task identity.
Unmerged sibling work is never copied into a task PR as completed work. Trunk
integration preserves the owning contract and stage baseline, refreshes other
rows from actual incorporated trunk, and retains the existing verification
and review after integration. Dependencies are satisfied by real shipped
markers, not by a child message, open PR, or successful CI alone. Human merge
ownership remains unchanged.

This amends only the sequential/index-order, single-frontier and
pre-worktree-JIT clauses in Decisions0007,0018,0021,0032,0044 and0047. Those
decisions remain active for all other requirements. Decision0058 remains the
narrow exception for separately scoped native bootstrap preparation; normal
attachment must not adopt a dirty or unrelated candidate using this decision.

## Consequences

- The task-start, JIT recorder and owner-reading paths need bounded changes;
  ordinary stage and write gates continue to enforce implementation readiness.
- The canonical Forge skill and both runtime pointers describe one lifecycle.
  Main presents the exact artifact and changes before asking a synchronous
  question, and task work pauses until its real answer. Host tool restrictions
  still apply; there is no async or fabricated-evidence fallback.
- Existing Forge launchers and harness model policy remain authoritative.
  Optional native read-only helpers grant no write or certification authority.
- Recovery reuses the actual owner and existing records. No new coordinator
  registry, evidence family, automatic merge authority or plan-mode requirement
  is introduced.
- The selected native-support and quality tasks can remain sequential because
  they overlap. This decision preserves dependency-ready scheduling generally;
  it does not force parallel execution where scopes or dependencies conflict.
