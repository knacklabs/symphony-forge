---
status: accepted
confirmed_by: "vrknetha"
date: 2026-08-07
stories: [FORGE-MODES-1]
---

# Developer-selectable workflow modes (Lite mode)

## Context

The lifecycle is terminal at ship. `pr_ready.py` archives the story, deletes
task-scoped `.factory` state, and reduces `run.json` to project fields — so the
always-armed planning lock (0013) re-arms and every later product write is
denied. A small, human-supervised fix (the common case after a PR is raised and
a reviewer asks for a tweak) then has only two doors, with nothing between them:
a full re-intake (plan → grill → decompose → stages → verify → three reviews →
outcome → ship), or a `quickfix` window that unlocks writes with no evidence at
all. 0013 is explicit that the threat model is **agent drift, not human
distrust** — so a fix a human is watching diff-by-diff is exactly the low-risk
case the gates were never aimed at. What is missing is a *proportionate* lane:
one that trusts the supervising human while still leaving a durable trace.

## Decision

Introduce **developer-selectable workflow modes**. `full` is the default and
stays mandatory for every fresh roadmap story. `lite` is a human-initiated,
ledgered relaxation that generalizes the quickfix window (a `profile` field on
the same record, same authorization path, same file budget):

- **Entered by a deliberate recorded command** — `./forge mode lite --by
  "<name>" --reason "<why>"` — never by a prompt keyword. A human saying "use
  lite mode" is the trigger; the ledgered command is the enforceable truth. This
  preserves 0013's guarantee: a drifting agent cannot disarm its own guard,
  because the relaxation is an attributed human act.
- **Bounded** — the quickfix file budget (default 5) still binds; exceeding it
  routes to `full` mode. Lite cannot silently become an untracked feature.
- **Records what it touched** — every product file claimed during the window is
  recorded against it (closing the `quickfix.files`-always-empty gap in
  `docs/specs/project-record.md`).
- **`terra@high` does the fix** — lite delegation writes with `gpt-5.6-terra` at
  high effort, not the `sol@medium` implementer; the model profile is pinned in
  `harness.yaml` under `modes.lite`.
- **Closes only after one review** — `./forge mode done` refuses unless a fresh
  autoreview run (three lenses, decision 0011, run by the coordinating session
  directly) exists over the window's diff with **no blocking findings**. That
  single review is lite's only gate; plan, grill, decomposition and verify are
  skipped.

`quickfix` remains the trust-and-trace floor (no review, hand edits). This
decision adds a **third exit** to the planning lock of 0013; 0013 otherwise
stands.

## Consequences

- The planning lock now has three legitimate exits: an approved plan, a
  `quickfix` window, or an open `lite` window. `pre_tool_use.py` already
  authorizes writes for an open window, so lite needs no new authorization path.
- Lite is a genuine loosening: with a unified, anytime scope and one review as
  its only gate, a developer could build a small feature in lite mode. The file
  budget, the ledger, and the required review are what keep that honest;
  recurring findings still escalate to a refactor story, never a fourth patch
  (0005).
- `pr_ready.py` is unchanged — it already refuses to ship with an open window,
  so a lite window must be closed (its review passed) before ship.
- The full loop, the one-autoreview-run contract (0011), and one-story-per-
  worktree (0002) are untouched. Modes change how a bounded fix is authorized,
  not how a story is shipped.
