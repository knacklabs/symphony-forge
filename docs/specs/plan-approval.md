---
slug: plan-approval
title: A plan is approved by a human, not by the agent that wrote it
status: confirmed
saved: 2026-08-06T07:50:29+00:00
---

# A plan is approved by a human, not by the agent that wrote it

## Why

Plan approval must come from the host interaction in which the human sees the
exact saved plan body. The body is a reader-facing brief, with no Forge status,
dates, reviewed-decision list, hashes, paths, or scope lists inserted into it.
An agent-authored command, a board view, a synthetic closing question, or a
marker proving only that plan mode was active cannot establish approval. Story
approval consumes the host's native Plan Mode completion across Claude and Codex;
task plans are covered by that approval after their matching cold read.

Plan metadata lives in `.factory/stories/<story>/plan-meta.json` and contains
status, dates, and reviewed decisions. Before saving, the planner reviews every
active decision; `forge plan save` records that attestation itself in this
metadata and is its only writer. This metadata is not shown as part of the plan
body. Native approval binds the body the human read.

## Behaviour

`forge plan save` validates the story plan and stores it once as
`awaiting-approval`. A successful native approval records approval of that
exact body separately, making its effective status `approved` without rewriting
the save-owned metadata or requiring a second unchanged save. A task plan is
ready when its saved revision has a matching recorded cold read.
There are no normal-flow `plan approve` or `task approve` commands.

The saved brief is displayed exactly as written in native approval, without
added bookkeeping. Codex asks `Approve this plan?`; its question id
`approve_plan_<digest>` alone carries the digest. These remain recorder details
and do not become part of the plan body.

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
  question uses id `approve_plan_<digest>`, prompt `Approve this plan?`, header
  `Approve plan`, the exact ordered choices `Approve plan`,
  `Request changes`, and `Stop`, and whose id-keyed answer is `Approve plan`.
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

The story approval remains `.factory/stories/<key>/plan-approval.json`; task
cold-read proof remains in `.factory/stories/<key>/grills/tasks/<id>.json`. A
story-scoped consumed-event tombstone prevents replay. These are recorder-owned
artifacts, never hand-authored state.

## Acceptance criteria

- One cold-read/disposition/amendment bridge and one native human approval bind
  the story plan; a task plan needs its matching recorded cold read only.
- Story save stops at `awaiting-approval`; native approval advances its
  effective status without a second save or a manual approval command.
- Both runtime adapters call the same candidate, digest, replay, attribution,
  and storage implementation.
- The native approval surface displays the saved brief body exactly, without
  inserting plan metadata into it.
- Plan status, dates, and reviewed decisions live in
  `.factory/stories/<story>/plan-meta.json`, and only `forge plan save` writes
  that metadata.
- Editing `What changes for you` or `Done when` after story approval requires
  fresh native approval. Other story amendments carry approval to the new digest
  with a recorded reason; the existing cold read is preserved.
- Existing substantive gates remain: active decisions, contradiction signals,
  story criteria, task contracts, and the always-armed write boundary.
