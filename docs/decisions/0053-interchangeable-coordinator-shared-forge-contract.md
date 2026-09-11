---
status: accepted
confirmed_by: "User (Codex conversation)"
date: 2026-09-07
stories: [FORGE-COORD-1]
---

# Either Claude or Codex coordinates the existing Forge contract

## Context

The existing contract assigns coordination to Claude Code and execution to
Codex. The developer now wants either Claude Code with its rescue/companion
plugin or Codex alone as coordinator, with the existing worker policy and all
features and gates retained. The original Codex adapter lacked the installed
human-round provenance path needed by the six grill gates, and execution/setup
assumed the Claude plugin.

On 2026-09-07 the user explicitly directed the initial native question change
in Codex and rejected the proposed Claude bootstrap. That bounded enabling
work is separate from normal approved-task proof; it does not approve this
decision or satisfy a grill, plan, delegation or shipping gate.

## Decision

Make the coordinator interchangeable while preserving the existing
Codex execution roles, worker model/effort policy, phase engine, protected
authority, evidence and shipping contract. Claude retains its rescue/companion
route; Codex uses a native adapter to the same Forge boundaries.

Treat the prepared bootstrap bytes as pre-stage work, not a continuing
coordinator-write exception. All further normal implementation follows the
existing approved delegation route. Prove real runtime human-round provenance before claiming a native grill pass;
prove worker admission, launch proof, setup and recovery before claiming full
native parity. The subsequent dogfood task must deliver scoped work through
the complete native approval-to-PR chain.

## Consequences

- This amends only runtime-specific coordinator/transport clauses
  in 0037 and 0018, the literal Claude coordinator wording in 0011, and permits
  truthful native human-round provenance under 0051. The coordinator continues
  to release `forge review` directly; independent three-lens ownership and the
  prohibition on nested reviewers remain, together with scope and proof gates.
- No model retuning, new review procedure, relaxed round matching, synthetic
  answers, manually written evidence or degraded-mode bootstrap belongs here.
- Native coordinator activation and legitimate worker admission must land
  together so stronger hooks cannot prevent the existing worker route from
  implementing or repairing the feature.
- A coordinator switch happens before the next task's human rounds, with no
  active worker or partially completed question/answer exchange, after the
  current task is complete. Transfer of unfinished tasks is outside this change.
- Setup honors an explicit coordinator choice, then the detected interface,
  and asks when neither identifies it. Unattended setup requires a choice;
  choosing Codex does not install or launch Claude as a prerequisite.
- Native runtime limitations require Codex repairs within the authorized
  scope and a retry at a valid task boundary; Claude is not a native prerequisite.
- Human acceptance of this decision leaves the normal spec, plan and task
  approval gates in force before normal task implementation.
