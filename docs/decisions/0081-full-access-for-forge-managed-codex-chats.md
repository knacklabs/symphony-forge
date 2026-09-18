---
status: accepted
confirmed_by: "Nandu (explicit full-access instruction, Codex conversation 2026-09-12)"
date: 2026-09-16
stories: [FORGE-COORD-1]
supersedes: 0041-sandboxed-workers-default
---

# Full access for Forge-managed Codex chats

## Context
The user explicitly authorized removing Forge's OS sandbox restriction after
the workspace-write policy repeatedly blocked process discovery needed by the
Forge lifecycle. Forge already has the task authority boundary: approved
plans, stage state, write scope, worker admission, hooks, proof, review, and PR
gates.

The supported Claude `codex-plugin-cc` 1.0.6 route independently hardcodes
workspace-write and read-only app-server policies. Upstream PR 742 is
unreleased and task-only, so this repository cannot safely make that route
full-access without patching external installed state or pinning unreleased
code.

## Decision
Forge-managed native Codex chats and the three committed Codex agent profiles
use `danger-full-access` by default. New native invocations state that policy
explicitly for both write-capable and semantically read-only roles.

`approval_policy="never"` remains unchanged. Forge's lifecycle, scope,
admission, hook, proof, review, and PR controls remain the authority boundary,
and read-only roles remain semantically read-only. This supersedes Decision
0041. Decision 0068's network intent is subsumed for full-access chats; its
workspace-write network setting remains as fallback configuration.

## Consequences
Trusted Forge-managed native chats no longer inherit the Codex sandbox
account, psutil, or macOS sysctl restrictions, and new launches no longer need
`--add-dir` grants. Exact historical terminal launch rows using the old
workspace-write/read-only argv remain readable but cannot authorize a new or
running launch.

Full host access increases the impact of a compromised trusted worker, so the
existing Forge authority controls are mandatory rather than optional defense
in depth. The Claude plugin route remains an explicit upstream limitation:
official `codex-plugin-cc` 1.0.6 is not solved by this decision. Integrate a
future official release separately; do not patch `~/.claude`, installed
caches, or an unreleased branch.
