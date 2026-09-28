---
status: accepted
confirmed_by: "Ravi Kiran Vemula"
date: 2026-09-28
stories: [FORGE-DESIGN-1]
supersedes: ""
---

# Screens and flows are built by Opus 5.5

## Context

The owner judges Claude on Opus 5.5 the strongest choice for screen and flow design and wants
every screen to be flawless. Today a Codex worker builds every item in a Codex repo, even when
the item changes what people see. The worker setting alone cannot express the owner's choice for
design work without also moving backend and Forge work to Claude.

## Decision

In client repos, Claude on `claude-opus-5-5` at high effort builds story tasks whose User-facing
cell says yes and fixes allowed as "Prototype before sign-off", regardless of the `workers`
setting. These workers use impeccable, Emil's design engineering and the app baseline. If Claude
cannot run, Codex on `gpt-6-sol` at high effort gets the same brief. A failed Claude run falls back
only when the checkout's HEAD, index and working tree are unchanged; otherwise Forge reports the
failure so the worker's changes are not overwritten or retried blindly. The work log names the
fallback and its reason. Backend tasks, other fixes and work in Forge's own repo keep their
existing worker route.

Both design models belong in `forge.toml` as `[models.design.claude]` and
`[models.design.codex]`, with these values as defaults when either table is absent. This keeps
the choice editable in one place.

## Consequences

- Client screen and prototype work has a deliberate design specialist while other worker choices
  continue to follow their existing settings.
- A machine without Claude can still build that work through Codex, with the fallback made visible
  to the coordinator.
- A Claude failure after checkout changes requires inspection rather than an automatic second
  worker run.
