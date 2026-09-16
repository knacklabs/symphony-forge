---
slug: project-hierarchy
title: Project hierarchy: captured completely, readable by an engineer
status: confirmed
saved: 2026-08-04T13:17:57+00:00
---

# Project hierarchy: captured completely, readable by an engineer

## Capability

A developer opening the board can see the whole shape of the project —
`Project → Epic → Story → sequential tasks` — and act on it without reading a
single artifact file. The hierarchy is real because the harness refuses to
record an incomplete one, not because an agent remembered to fill it in.

## Why

The board today shows lifecycle state but not the project. A developer joining
mid-flight cannot answer what the product is, who it serves, what each epic
delivers, which stories can start right now in parallel, why another story is
blocked, or which task is active. They read `plans/roadmap.json` instead.

The data to answer most of that already exists and is already derived:
`ready_pending()` computes the parallelizable frontier, `leverage()` ranks
stories by what finishing them frees, `epic_gating()` derives epic order from
story edges. None of it reaches the UI.

But projecting it is not enough, because capture is too loose to project from.
`check_item()` requires only `key` and `title`. Epics are optional on every
route, and this repo's own roadmap has none. `plan save` checks one of the nine
sections the planner prompt names. A reading layer built on that renders blanks
and calls them a hierarchy.

So the contract is tightened where content is authored, and only then displayed.

## Behaviour

### Capture is refused when it is incomplete

**Project brief.** There is no single existing heading set to preserve: the live
`docs/product/BRIEF.md` uses `Summary` / `Users` / `Key Flows` /
`Domain Concepts` / `Constraints` / `Out of Scope`, while
`harness/nestjs-react/BRIEF_TEMPLATE.md` scaffolds `What` / `Who` / `Flows` /
`Domain Concepts` / `Constraints` / `Out of Scope (v1)`. A contract cannot be
enforced against both, so one is canonical: the live brief's set, plus
`Target Outcome`. The template and its conventions doc are realigned onto it.
The template only feeds new scaffolds, so no heading in a brief any project has
already written is renamed. `record_signoff.py` refuses when a required heading
is absent or its body is empty. One parser serves both the gate and the board,
so the warning and the refusal can never disagree.

**Capability specs.** `forge spec confirm` requires an H1 title plus `Why`,
`Behaviour`, and `Acceptance criteria` — the casing already on disk. Drafts stay
free-form; the gate is at confirmation.

**Epics and stories.** One shared contract check runs on the three routes that
author story content — `roadmap derive`, `roadmap import`, `roadmap add`. Every
epic carries `id`, `title`, `objective`, and `source_refs` that resolve to real
repo-relative paths. Every story carries a narrative, non-empty acceptance
criteria, a skill, a known epic id, an explicit `depends_on` (`[]` counts), and
either a confirmed spec or the existing ad-hoc debt marker. `derive` and
`import` require at least one epic.

`forge roadmap epic add` creates an epic after sign-off, so the epic requirement
is satisfiable without re-running the PM handoff ceremony that `roadmap import`
demands.

**Plans and tasks.** `plan save` requires all nine sections the planner prompt
names, present and non-empty. A recorded decomposition takes its project,
story, epic, plan path and plan digest from committed repository state, not from
what the payload claims. Every task carries an objective, acceptance criteria, a
write scope, runnable verify commands, a required-test list (which may be
empty), and a reviewer focus. Array order is the execution sequence and a task
dependency may only name an earlier task.

### Legacy artifacts stay usable

Validation runs where content is authored, never in `save_roadmap`. A status
flip at intake or ship, an assignment, a spec link, and a post-merge
`roadmap heal` all keep working on an artifact that predates the contract —
`heal` especially, because it exists for the moment a merge went wrong. Only new
or amended authored content is refused. `forge doctor` reports the gaps it finds
in older projects instead of blocking them.

### Only dependencies are authored

Story `depends_on` edges are the single authored ordering. Reverse `unblocks`,
transitive leverage, epic-to-epic gating, the ready frontier, and epic and story
progress are all derived from them. Agents never author a second graph.

### The board reads the hierarchy back

`/api/state` and `/api/story/<key>` gain project identity and sections, epic
membership and derived epic relationships, and per-story reverse edges and task
progress. `frontier` stays the canonical startable list and epic progress keeps
its single existing source. No mutating route is added; the board stays a
reading layer over committed artifacts.

The default view is an Overview that answers, in order: what this project is,
what can start now and in how many worktrees, what each epic delivers, and where
every story sits with what it requires and unblocks. The lifecycle board remains
as a second view, with `EPIC`, `STORY` and task labels that cannot be confused
and a drawer that reads `Project › Epic › Story` before it shows evidence.

Parallelism is presented as the live frontier plus each story's own
requires/unblocks, because that is the answer that stays true as stories ship. A
layered wave number would need a caveat on every screen explaining that it is
not actually the order.

## Acceptance criteria

- A developer answers, from the default screen and without opening an artifact:
  what the project is, who it serves, what each epic delivers, which stories
  belong to it, which stories can start in parallel right now, why another story
  is blocked, and which sequential task is active.
- Every roadmap authoring route refuses an incomplete epic or story with a
  message that names the missing field.
- Every non-authoring roadmap route still succeeds against an artifact captured
  before this contract existed.
- `forge roadmap epic add` makes the epic requirement satisfiable after
  sign-off, proven against a roadmap that has no epics.
- `record_signoff.py` refuses a brief missing a required heading, and
  `forge spec confirm` refuses a spec missing `Why`, `Behaviour`, or
  `Acceptance criteria`.
- `plan save` refuses a plan missing any of its nine sections.
- A decomposition's project, story, epic and plan provenance comes from
  repository state and cannot be set by the payload.
- `/api/state` and `/api/story/<key>` carry the hierarchy; no mutating route
  exists on the board.
- The bundled example project passes the production validators rather than
  fixture-only checks, and its frontier, blocked stories and active task read
  correctly at desktop, tablet and mobile widths.

## Boundaries

- No wave or layer numbering, and no node-and-arrow dependency graph. The
  frontier plus requires/unblocks is the dependency presentation.
- No dates, estimates, burndown or velocity.
- The board never writes. Recording stays in the gated commands.
- No new database, UI framework or build step; the board stays one
  self-contained HTML file.
- Tasks are still created only after a story's plan is approved. Each leaf owns
  its task worktree and PR; dependency-ready siblings may overlap only when
  their measured scopes are disjoint.
- Existing BRIEF and spec heading vocabulary is not renamed. The only addition
  is `Target Outcome`.
- Client repos receive the stricter gates at re-vendoring, not retroactively.
