---
status: accepted
confirmed_by: "Ravi Kiran Vemula"
date: 2026-09-28
stories: [FORGE-SALES-1]
---

# The agent merges prototype changes until client sign-off

## Context

A salesperson needs to show the next version of a prototype without waiting for someone to
judge and merge each ready change. Tests and the automatic review still guard each change.

## Decision

The owner chose agent merging for prototype work. In a client repo whose default branch, as
last fetched, has no accepted client sign-off, the agent merges every ready item through
`forge merge`, even when that branch's `forge.toml` says `merge = "human"` or omits the setting.
`forge close` and `forge next` tell the agent to do this. A sign-off in the current checkout
alone does not change the rule.

Once the default branch has an accepted sign-off, its own `forge.toml` setting applies as
today: `merge = "agent"` permits the agent to merge; `merge = "human"` or no setting leaves
the merge to a person. Forge's own repo is unaffected.

## Consequences

- Every prototype change still needs green tests and a clean review before it is ready.
- The agent uses `forge merge`; the block on a raw `gh pr merge` remains.
- Sign-off returns control of merging to the client repo's chosen setting.
