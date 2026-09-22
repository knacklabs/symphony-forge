---
status: accepted
confirmed_by: "User"
date: 2026-09-22
stories: [FORGE-COORD-1]
---

# Trust hash-approved Codex hook invocation for native approval

## Context
Codex `PostToolUse` supplies session, turn, tool-call, input, and response
fields, but the host exposes no signed or otherwise unforgeable attestation.
Forge cannot distinguish a genuine hook invocation from a same-user process
that supplies the same JSON without adding process registries or a second
authority service, both outside the approved Lean scope.

## Decision
For Codex native plan approval, trust the host's invocation of the exact
hash-approved project hook as the operational boundary. The shared recorder
must still validate the exact current plan digest, runtime, stable
session/event/tool identity, supported synchronous payload, non-cancelled
answer, replay refusal, and exactly one eligible candidate.

## Consequences
Forge does not claim cryptographic or signed host provenance for this event.
Direct or synthetic same-user invocation is outside the trusted boundary.
Signed host attestation remains an OpenAI host dependency; Forge adds no PID,
process, transcript, token, scheduler, or auxiliary-service substitute.
