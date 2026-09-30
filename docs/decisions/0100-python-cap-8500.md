---
status: accepted
confirmed_by: "Ravi Kiran Vemula"
date: 2026-09-30
stories: []
supersedes: "0099-python-cap-8000"
---

# Forge's Python cap is 8,500

## Context

Decision 0099 raised the cap to 8,000 lines on 2026-09-29. By 2026-09-30 the v1.2.0 stories had
used that room: Python stood at the cap, a trim found too little dead code to free more, and the
fix that runs Forge's own repo on its current code, `forge land` and the cold reader ranking its
findings still need room.

## Decision

The cap still counts only Python files under `src/forge`, and it is 8,500. The owner chose this on
2026-09-30 over a trim story first and over a smaller raise to 8,200.

## Consequences

- About 500 lines of room for the planned work; each task still keeps its own code lean.
- The planned split of the busiest files should remove duplicated code.
- The 1,200-line module limit and the command limit are unchanged.
- Raising the cap again still needs an accepted decision.
