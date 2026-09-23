---
status: accepted
confirmed_by: "Ravi Kiran Vemula"
date: 2026-09-23
stories: [FORGE-COORD-1]
---

# Either runtime may execute: FORGE_EXECUTOR selects codex, claude or hybrid

## Context

Decision 0037 made the role split structural: Claude coordinates, Codex executes, and the session
write lock denies every coordinator product write. `FORGE_COORDINATOR` (claude|codex) selects only
who coordinates. A user with only Claude therefore has no supported way to change code, and even a
Lite window admits only a Codex worker. Forge must work the same whether a team uses Claude, Codex,
or both.

## Decision

A single setting, `FORGE_EXECUTOR` = `codex` | `claude` | `hybrid` (default `hybrid`), selects who may
execute (write product code). `.envrc` sets the repo default; an exported environment variable
overrides it per machine; every gate reads it through one resolver.

- `hybrid` (default): Claude orchestrates and Codex executes — delegated Codex workers are the
  default route for code changes. The Claude session may still execute through the same gates when
  the coordinator chooses to (for example a small fix, or Codex unavailable).
- `codex`: only Codex workers write; the Claude session never executes.
- `claude`: Claude only — the Claude session and its subagents write; no Codex is required.

Every writer passes the same gates: approved plan, active stage and write scope (or an open Lite /
degraded window with its file budget), protected-state denial, and the same proof, review and ship
gates. A new executor adds an admitted writer, never a bypass.

Independence does not depend on vendor. Without Codex, the cold grill is a fresh Claude subagent that
never saw the artifact, and the formal review runs through the unchanged Autoreview helper with
`--engine claude`.

## Consequences

Decision 0037's structural write lock stays, but its "Codex only" executor clause is replaced by
`FORGE_EXECUTOR`. Hook admission, delegation, grill and review dispatch, docs and the dual-runtime
check must all honor the resolver. Routing within Codex (Decisions 0083, 0084) is unchanged.
Claude-only teams can ship end to end; Codex-only teams keep today's flow.
