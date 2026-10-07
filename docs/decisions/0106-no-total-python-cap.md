---
status: accepted
confirmed_by: "Ravi Kiran Vemula"
date: 2026-10-07
stories: []
supersedes: "0105-python-cap-12000"
---

# Forge has no total Python line ceiling

## Context

The total-lines ceiling had to be raised five times in two weeks and only stopped finished
work late. The owner chose to remove it on 2026-10-07.

## Decision

Remove the total-lines ceiling for Python under `src/forge`. `pyproject.toml` has no
`line_ceiling`, and no test checks the total. This supersedes the ceiling decisions 0094,
0096, 0099, 0100, 0101, 0103 and 0105, including their requirements for another accepted
decision to raise the ceiling and 0105's target to return below 11,000 lines.

## Consequences

The per-file limit of 1,200 lines, the 21-command limit and CI's net-lines report stay
unchanged. Reviews and the simplify fixes still judge unnecessary complexity.

This decision applies only to Forge's own repo. New client repos, including adoption,
and existing client repos on upgrade see no change.
