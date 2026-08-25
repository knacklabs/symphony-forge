---
status: accepted
confirmed_by: "Ravi Kiran Vemula"
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
story, a marker with the plan's `plan_body_digest` — the file excluding the
harness-stamped YAML frontmatter block and the `## Implementation
Assumptions` block (a `plan save` restamp must not invalidate authorship);
`plan save`, `plan approve`, `task plan save` and `task approve` refuse a
file whose body digest has no marker in the active story scope or the root
scope. The same hook records every AskUserQuestion round (questions,
options, chosen) one record per file under the story (root-level before
sign-off); the grill recorder accepts only rounds that match a logged
record, enforces floors spec 2 / requirements 1 / plan 2 / task 1, and
requires `frontier_empty: true` on the final round. AskUserQuestion answers (`tool_response`) are
delivered to the hook — proven live on 2026-08-24 — so `chosen` equality is
exact when the ledger entry has one. The task frontier is
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
- Verified live: the hook receives AskUserQuestion answers and plan-mode
  Write/Edit events with `permission_mode: "plan"`; both record kinds were
  proven on this story's own plan, task plans and grills before acceptance.
