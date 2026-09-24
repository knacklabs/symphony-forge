---
status: accepted
confirmed_by: "Ravi Kiran Vemula"
date: 2026-09-24
stories: []
---

# Hybrid mode delegates to Codex through a Forge-owned SDK app-server

## Context

In hybrid mode (decision 0085) Claude coordinates and Codex executes. Claude reaches Codex only
through the codex-plugin-cc companion, which starts a new Codex thread for every delegation and
exposes no way to resume a specific thread, watch its events or steer it. Every worker therefore
re-reads the repository, and every review-fix round starts cold. Codex's app-server protocol,
exposed by the official `openai-codex` Python SDK, supports resuming threads by id, live event
streams, steering and interrupting turns. One app-server process holds each loaded thread, so
threads must have a single owner.

## Decision

In hybrid mode with Claude coordinating, `forge delegate` drives Codex through one Forge-owned,
lease-held app-server per repository, using the `openai-codex` SDK pinned to an exact version and to
the installed `codex` binary. This route is primary; the codex-plugin-cc companion is the fallback,
chosen only before dispatch. Each delegated turn is admitted and closed through recorded ledger rows,
equivalent to today's companion launch rows. Review-fix rounds resume the task's own worker thread.
Workers keep full access with `approval_policy="never"` (decision 0081); the SDK's approval handler
is overridden to decline. Native Codex coordination is unchanged.

## Consequences

- The delegation-boundary spec, the dual-coordinator parity architecture and the product brief are
  amended to name the SDK route as the primary Claude→Codex route in hybrid mode.
- Forge gains a pinned Python dependency and a doctor check; client upgrades add it idempotently and
  tasks already running on the plugin route finish there.
- Forge owns thread lifecycle: a thread ledger, a lease, archival at task merge and story close, and
  pruning of Forge-owned rollouts only.
- The app-server protocol is still labelled experimental; the pin and doctor check make drift a
  pre-dispatch refusal rather than a mid-task failure.
- Forking a warm story thread per task, and approving task plans from the primary checkout, are
  left to a follow-up story.
