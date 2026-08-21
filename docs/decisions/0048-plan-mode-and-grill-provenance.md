---
status: proposed
confirmed_by: ""
date: 2026-08-21
stories: [plan-mode-and-grill-provenance]
---

# Plan mode and grill provenance are enforced, not advisory

## Context

`forge next` prints "MANDATORY: enter plan mode" and decision 0044 says every
grill delivers its rounds through AskUserQuestion, but no recorder checks
either. On 2026-08-21 (cadence, `decisions-reconciled`) a session authored a
story plan and a task plan as files from normal mode and recorded grills
with one self-reported round; `plan save`, `task plan save` and the grill
recorder accepted all of it. Decision 0029 established that hooks do not
fire on `ExitPlanMode` (#21282), so the enforcement signal must come from
somewhere a hook can see. Claude Code delivers `permission_mode` on every
tool event, and in plan mode the only writable file is the plan itself.

## Decision

A `Write`/`Edit` made with `permission_mode == "plan"` is the proof that a
plan was authored in plan mode. A PostToolUse hook records, per active
story, a marker with the sha256 of the written plan file; `plan save`,
`plan approve`, `task plan save` and `task approve` refuse a file whose
exact digest (excluding the `## Implementation Assumptions` block) has no
marker. The same hook records every AskUserQuestion round (questions,
options, chosen) one record per file under the story (root-level before
sign-off); the grill recorder accepts only rounds that match a logged
record, enforces floors spec 2 / requirements 1 / plan 2 / task 1, and
requires `frontier_empty: true` on the final round. The task frontier is
author-task-plan → grill → approve → stage start → delegate. The Codex
planner hands its draft to Claude for the grill and plan mode; quickfix
and degraded windows stay exempt; sessions without the hook (CI, terminal,
non-Claude) cannot save plans or record grills. This supersedes the
sentence in 0044 permitting zero rounds for a zero-gap grill and the
sentence in 0029 calling plan mode "not the enforcement signal"; 0029's
human approval marker and 0044's loop otherwise stand.

## Consequences

- New `factory/scripts/post_tool_use.py`, two schemas, a `PostToolUse`
  entry in `.claude/settings.json`; vendored by the existing wholesale copy
  and integrity-checked by `check_vendor_integrity`.
- The plan-mode file is the plan and is saved verbatim; `forge plan assume`
  is the only post-approval edit path.
- A grill re-recorded after tree drift may reuse its rounds when the
  interrogated text is byte-identical; a changed text needs new rounds.
- In-flight stories that grilled a task before saving its task plan keep
  that grill if the task plan is saved before `stage start` (one-time
  tolerance).
- If Claude Code does not deliver AskUserQuestion answers to the hook, the
  ledger stores questions and options only and the grill record carries
  `chosen` (implementation assumption, verified live after the first task).
