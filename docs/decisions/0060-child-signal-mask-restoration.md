---
status: accepted
confirmed_by: "User (Codex conversation)"
date: 2026-09-09
stories: [FORGE-COORD-1]
---

# Retain the existing child signal-mask restoration during launch

## Context

Decision0042 says that the old subprocess `preexec_fn` is dropped. Current
main retains a narrower use during atomic process registration: the child
restores the inherited termination-signal mask before executing its worker.
This behavior predates native Codex support and is present in the delegate
and proof launchers. Removing it to match the old sentence could leave the
child unable to receive the termination signals used by verified cleanup.

This is a documentation reconciliation of existing launch behavior, not an
additional process framework or permission to change cleanup guarantees.

## Decision

Retain the existing POSIX child signal-mask restoration during atomic process
registration, including its narrowly scoped `preexec_fn` use. This amends
only Decision0042's blanket statement that `preexec_fn` is dropped. All other
Decision0042 requirements remain active, including the cross-platform psutil
process model and verified process cleanup.

Keep the platform guards and existing Windows launch behavior. Do not add
unrelated work to `preexec_fn` or reintroduce the superseded process-discovery
mechanism. Before process creation, failure must be recorded truthfully
without inventing process identity or exit status; after creation, terminal
publication follows verified cleanup as already required.

## Consequences

The native execution task updates lifecycle wording and retains focused
launch/cancellation regressions for this existing behavior. The task's real
platform checks distinguish signal-mask handling on POSIX from Windows
process cleanup. No new process registry, worker transport, evidence format
or platform-support claim follows from this decision.
