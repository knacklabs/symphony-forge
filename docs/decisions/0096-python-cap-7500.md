---
status: superseded
confirmed_by: "Ravi Kiran Vemula"
date: 2026-09-28
stories: []
supersedes: "0094-python-only-line-cap"
superseded_by: 0099-python-cap-8000
---

# Forge's Python cap is 7,500

## Context

Decision 0094 capped Forge's Python at 7,000 lines, leaving about 490 lines of room. By the evening
of 2026-09-28 the prototype, salesperson, design and review work had used most of it: Python stood at
6,915, and five approved tasks still add code (the sign-off review, design routing, merging until
sign-off, the lighter prototype review and the platform reminder in `forge next`).

## Decision

The cap counts only Python files under `src/forge`, as 0094 set, and it is 7,500. The owner chose
this on 2026-09-28 over keeping 7,000 with a central trim, and over making each task free its own
lines.

## Consequences

- About 585 lines of room for the approved stories; each task still keeps its own code lean.
- The 1,200-line module limit and the command limit are unchanged.
- Raising the cap again still needs an accepted decision.
