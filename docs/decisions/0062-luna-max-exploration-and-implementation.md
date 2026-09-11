---
status: accepted
confirmed_by: "User (Codex conversation)"
date: 2026-09-09
stories: [FORGE-COORD-1]
supersedes: 0003-model-tiers-terra-explore-sol-implement
---

# Luna Max for exploration and implementation

## Context

The user accepted Luna Max for routine implementation and explicitly added
exploration on 9 September 2026. The user also confirmed that autoreview owns
its model selection. The choice prioritizes cost while retaining the existing
independent review and verification requirements; benchmark results do not
establish equal accuracy or lower token use in this workflow.

## Decision

Use `gpt-5.6-luna` with `max` reasoning for code exploration and routine
implementation. Exploration is explicitly read-only; implementation continues
through the admitted Forge writer route. The main conversation's model remains
selectable. Autoreview selects its own model without a duplicate Forge pin.

The existing grill, Lite, validation/debugging and specialist settings retain
their own authority. A different model for a difficult task is an explicit
choice, not an automatic retry or new execution route.

## Consequences

Replace Decision 0003's exploration and implementation defaults in the owning
configuration and its live instructions. Model choice does not relax scope,
approval, testing, review or delivery gates. Compare finished-task cost including
review corrections when assessing the default. Prepared settings changes still
need their normal review and PR ownership before shipping.
