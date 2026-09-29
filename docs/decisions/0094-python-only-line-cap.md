---
status: superseded
confirmed_by: "Ravi Kiran Vemula"
date: 2026-09-28
stories: []
supersedes: ""
superseded_by: 0096-python-cap-7500
---

# Forge's line cap counts only its Python

## Context

The v1 rule that Forge shrinks over time is checked by a ceiling on the lines under `src/forge`,
set at 8,000 in `pyproject.toml`. That count mixed 6,512 lines of Python with 1,488 lines of text
templates, the skill, brief and guide text Forge writes into repos. On 2026-09-28 `src/forge` sat at
exactly 8,000, and three open tasks could not land without first cutting lines elsewhere. The
trims the workers found removed docstrings and comments that explain rules, not dead code, and a
wording change to a template competed with code for the same room.

## Decision

The ceiling counts only Python files under `src/forge`, and it is 7,000. Text templates and other
files there no longer count. The owner chose this on 2026-09-28 over keeping 8,000 and trimming per
story, and over raising the total to 8,500.

## Consequences

- About 490 lines of room for Python today; code growth is still capped, and the 1,200-line module
  limit and the command limit are unchanged.
- Template text can grow without a trim; its size is judged in review, not by the count.
- Raising the ceiling again still needs an accepted decision.
