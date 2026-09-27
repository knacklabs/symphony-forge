---
status: superseded
superseded_by: 0093-lean-forge-rebuild
confirmed_by: "vrknetha"
date: 2026-07-24
stories: []
---

# Plan save refuses unresolved contradictions with active decisions

## Context

Contradictions between a new plan and the accepted decision corpus were
caught only if a worker noticed at implementation time and raised a
signal; nothing forced the check during planning, so plans could silently
diverge from decisions. Confirmed in chat (workflow-enforcement design,
2026-07-24): the check belongs at the plan-save commit point.

## Decision

`forge plan save` refuses while any contradiction signal is open, and
requires the plan's frontmatter to list every currently-active decision id
in `decisions_reviewed` (unknown or superseded ids refuse). A conflict is
resolved only by superseding the decision (`forge decision new
--supersedes`) or raising and resolving a contradiction signal — never by
silent divergence. Plans also carry a `story` key binding them to a
roadmap item.

## Consequences

- The planner must load and reconcile the live decision corpus before a
  plan can be approved; the grill gains a contradiction lens.
- Reviewing decisions is an attestation, not proof of understanding — the
  grill remains the interrogation that catches shallow reviews.
- Plans become joinable to roadmap stories, enabling the plan list and
  lifecycle board views of implemented-vs-pending work.
