---
status: accepted
confirmed_by: "Ravi Kiran Vemula"
date: 2026-09-28
stories: []
supersedes: ""
---

# The customer signs off a working prototype before stories

## Context

The earlier [decision 0014](0014-specs-before-signoff.md) required a derived roadmap before client
sign-off. That order lets stories exist before the customer has seen a working prototype. The owner
confirmed the opposite order in
[the prototype sign-off spec](../specs/prototype-signoff.md): discovery, prototype, strict review,
the customer's sign-off, then stories.

## Decision

In a client repo, the agent learns the customer's problem, builds and demos the smallest working
prototype through fixes, then has the whole prototype and its answers reviewed. The customer's
named person signs off before `forge roadmap add` or `forge story new`, including `--from-fix`.
Specs may still be saved and confirmed before sign-off. Forge's own repo is unaffected, and an
already accepted client sign-off stays valid.

This supersedes decision 0014's order: a derived roadmap is no longer required before sign-off.
Its requirement to confirm specs before sign-off remains; the roadmap is derived from those specs
after the customer signs off.

## Consequences

- Prototype work ships as fixes, with the same tests, review and pull request as other fixes.
- The answers page and reviewed prototype travel from the salesperson to the developer before
  story planning begins.
- A client repo without an accepted sign-off cannot add a roadmap story or create a story.
