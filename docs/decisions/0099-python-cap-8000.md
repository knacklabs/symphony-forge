---
status: superseded
confirmed_by: "Ravi Kiran Vemula"
date: 2026-09-29
stories: []
supersedes: "0096-python-cap-7500"
superseded_by: 0100-python-cap-8500
---

# Forge's Python cap is 8,000

## Context

Decision 0096 raised the cap to 7,500 lines. By 2026-09-29 the live-app, sign-off, salesperson and
review work had used that room: Python stood at the cap, and the approved cold-read loop, short
plan and edge-case read for fixes still need a few hundred lines.

## Decision

The cap still counts only Python files under `src/forge`, and it is 8,000. The owner chose this on
2026-09-29 over trimming first and making every approved part wait.

## Consequences

- About 500 lines of room for the approved stories; each task still keeps its own code lean.
- The planned split of the busiest files should remove duplicated code; the count is reported at
  the v1.2.0 release.
- The 1,200-line module limit and the command limit are unchanged.
- Raising the cap again still needs an accepted decision.
