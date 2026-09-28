---
status: accepted
confirmed_by: "Ravi Kiran Vemula"
date: 2026-09-28
stories: []
supersedes: ""
---

# New projects use Forge's own discovery, not office-hours

## Context

[The FDE discovery spec](../specs/fde-discovery.md) sends a new project, or an ask no confirmed
spec covers, to gstack's `/office-hours` and keeps its design doc in `docs/context/`. That narrowed
[decision 0089](0089-fde-discovery-without-gstack.md) to "of gstack, only office-hours stays". But
Forge no longer ships gstack, so a new project was sent to a step its user may not have. The
salesperson also needs things office-hours does not give: a brief before the first meeting, the
customer's own words, their spreadsheet's column headers and a same-day recap they confirm.

## Decision

A new project, or an ask no confirmed spec covers, runs Forge's own discovery with the story
limit: a pre-meeting brief in `docs/context/` from the prospect's website, the customer's words
in `## Words they use`, the column headers of the spreadsheet or form they use today, and a
same-day recap in `docs/context/` whose reply sources the Demo workflow and Sign-off person
answers. This replaces the spec's `/office-hours` step. The owner chose this on 2026-09-28.

## Consequences

- The Forge skill and its reference page no longer mention gstack or `/office-hours`.
- Of gstack, nothing stays: 0089 applies in full again.
- `forge migrate` still moves an older repo's office-hours design docs to `docs/context/`.
