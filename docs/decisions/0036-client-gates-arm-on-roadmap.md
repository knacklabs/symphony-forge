---
status: superseded
superseded_by: 0093-lean-forge-rebuild
confirmed_by: "Ravi"
date: 2026-08-10
stories: [FORGE-ALIGN-3]
---

# Client Gates Arm On Roadmap

## Context

The strict-alignment epic vendors real CI teeth to clients
(`roadmap-gate.yml`: a declare-all PR gate and a default-branch audit gate).
Pulling a harness upgrade must never instantly red an unprepared client, the
harness repo must not double-run its own internal gates, and Git Flow clients
(default branch not `main`, e.g. minegate on `develop`) must not get a gate
that silently never fires — the existing vendored workflows already have that
defect (deferred with a trigger, not replicated here).

## Decision

The vendored client gates arm if and only if `constitution/VENDORED_FROM`
exists (a client, never the harness) AND `plans/roadmap.json` has at least
one epic — the authored roadmap IS the opt-in. The push job follows the
repository default branch, and enforces the FULL `forge project audit`
severity (grilled 2026-08-10: chosen over an alignment-gaps-only filter).

## Consequences

- A client without a roadmap stays green on upgrade; the `no-roadmap` audit
  gap (decision-free, from FORGE-ALIGN-2) is the visible pressure to author.
- A client that authors its roadmap immediately inherits the full contract:
  untraced PRs blocked, incomplete stories / missing outcomes / vendor drift
  red the default branch. For the myclaw pilot this red list is deliberately
  the to-do list.
- Git Flow caveat, accepted: the gate follows the DEFAULT branch; where the
  integration branch differs (develop) the PR gate still fires on every PR,
  but the push audit runs only where the default branch points.
- A malformed `plans/roadmap.json` fails the arming step loudly — fail
  closed, never silently disarmed.
- The harness repo keeps its internal gate workflows untouched; the vendored
  file lives in its tree but never arms there.
