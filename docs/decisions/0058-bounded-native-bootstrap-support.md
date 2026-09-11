---
status: accepted
confirmed_by: "User (Codex conversation)"
date: 2026-09-08
stories: [FORGE-COORD-1]
---

# Bounded native bootstrap support with complete task reviews

## Context
The prepared native candidate has a 339,858-byte complete bootstrap patch,
above the existing review limit. Main-derived task targets lack native question
and worker support. Requiring those targets for all cleanup predecessors while
reserving native support for the final single task creates a delivery cycle.

The user explicitly answered “Allow the bounded native bootstrap amendment
(Recommended)” to the main conversation's request to use the isolated native
candidate for bounded bootstrap tasks and split prepared changes into complete,
independently reviewed support PRs. This is an actual human decision, not a
synchronous question-tool receipt or a task approval.

## Decision
Permit a bounded native-only bootstrap route using the existing isolated
candidate, and divide the prepared changes into complete, independently
reviewed support PRs. For those explicitly scoped tasks, amend Decision0047's
main-only starting rule and the single parity-task allocation in the current
spec/plan; retain genuine approvals, delegated writes, review limits, actual
merge ordering and release checks.

## Consequences
- Validate the exact task scopes, target preparation, baselines and complete
  review boundaries before implementation. This acceptance does not establish
  that a proposed procedure works or approve a story/task plan.
- Treat the candidate runtime as unshipped preparation. Preserve its original
  bytes and actual provenance; unchanged bootstrap is not a worker contribution.
  Assign every prepared change to a complete support-task review or the final
  complete activation review. Do not ship omitted or partially reviewed bytes.
- Keep normal native question identity, real answer matching, registered worker
  admission, scope, launch, completion, verification and independent autoreview
  requirements. No coordinator-write exception, fake evidence, companion/Claude
  fallback or larger review limit is introduced.
- Preserve actual predecessor markers on main and sequential merge ordering.
  Do not call an unmerged task shipped or infer merge approval from this decision.
- Native write-hook activation and legitimate worker admission still land
  together. Full mandatory quality activation and required live platform proof
  still precede parity shipping; review-only drafts retain explicit limitations.
- Reconcile the spec, roadmap criterion and delivery plan with this bounded
  amendment using their existing revision, grill and approval procedures.
  Decisions0047,0053 and0056 otherwise remain in force; this does not introduce
  a general worktree or coordinator framework.
