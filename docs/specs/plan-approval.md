---
slug: plan-approval
title: A plan is approved by a human, not by the agent that wrote it
status: confirmed
saved: 2026-08-06T07:50:29+00:00
---

# A plan is approved by a human, not by the agent that wrote it

## Why

Plan approval must come from the host interaction in which the human sees the
exact final plan. An agent-authored command, a board view, a synthetic closing
question, or a marker proving only that plan mode was active cannot establish
that fact. Story and task approval therefore consume the host's native Plan
Mode completion and share one digest and replay model across Claude and Codex.

## Behaviour

`forge plan save` validates the story plan and stores it once as
`awaiting-approval`. A successful native approval changes that exact plan to
`approved`; it does not require a second unchanged save. Task plans use the same
approval recorder and store the approval on their existing task-grill record.
There are no normal-flow `plan approve` or `task approve` commands.

Before either approval, one independent cold grill reads the original plan.
The cold launch digest is preserved as `cold_input_sha256`. Ordered
`finding_dispositions` maps every gap and contradiction exactly once to its
resolution and source. When the final artifact differs, ordered `amendments`
explains every change and binds the bridge to `final_artifact_sha256`. The cold
reader is never claimed to have reviewed amended bytes, and amendments alone do
not require another cold launch.

The shared recorder derives exactly one eligible current-frontier candidate:

- Claude accepts only a successful `ExitPlanMode` PostToolUse event whose
  `tool_input.plan` bytes produce the displayed current semantic digest.
- Codex accepts only a completed synchronous `request_user_input` whose single
  question uses id `approve_plan_<digest>`, prompt `Approve exact plan digest
  <digest>?`, the exact ordered choices `Approve plan`, `Request changes`, and
  `Stop`, and whose id-keyed answer is `Approve plan`.
- Each event binds runtime, stable session and event identity, plan kind, story,
  task, and current semantic plan digest. Attribution is
  `human-via-Claude` or `human-via-Codex`; Forge invents no display name.
- Zero or multiple candidates, replay, missing stable identity, stale digest,
  cancellation, wrong runtime, asynchronous acknowledgement, unsupported
  payload, and ordinary optional clarification all refuse without approval.

Current Codex hooks expose no signed or otherwise unforgeable host attestation.
The current native approval trust boundary is therefore the host's invocation
of the hash-approved project hook together with these recorder checks; Forge
does not claim cryptographic or signed host attestation. The recorder still
requires the exact current digest, runtime, session/event/tool identity,
supported payload shape, non-cancelled completion, replay refusal, and exactly
one eligible candidate. A direct or synthetic hook invocation is outside the
trusted operational boundary and cannot establish native human approval.
Signed host attestation remains a host dependency.

The story approval remains `.factory/stories/<key>/plan-approval.json`; the
task approval remains in `.factory/stories/<key>/grills/tasks/<id>.json`. A
story-scoped consumed-event tombstone prevents replay. These are recorder-owned
artifacts, never hand-authored state.

## Acceptance criteria

- One cold-read/disposition/amendment bridge and one native human approval bind
  the final story or task plan digest.
- Story save stops at `awaiting-approval`; native approval advances it without
  a second save or a manual approval command.
- Both runtime adapters call the same candidate, digest, replay, attribution,
  and storage implementation.
- Editing the plan after approval stales the approval and blocks downstream
  implementation until the amended final digest receives a fresh native human
  approval. It returns directly to the approver; the existing cold read is not
  repeated solely because approved content was amended.
- Existing substantive gates remain: active decisions, contradiction signals,
  story criteria, task contracts, and the always-armed write boundary.
