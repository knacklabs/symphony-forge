---
status: superseded
confirmed_by: "Ravi Kiran Vemula"
date: 2026-09-24
stories: []
superseded_by: 0093-lean-forge-rebuild
---

# Upgrade: refuse work in flight, archive old review files, reset on failure

## Context

`forge upgrade` is about 4,800 lines, three quarters of it migration and
resume machinery for converting in-progress Lean-era state. A simulation of
real client versions found that none upgraded cleanly: pre-Lean clients were
left half-upgraded, stories in progress were stranded, and every upgraded
client failed its next upgrade. No client runs a Lean-era version; all real
clients were vendored between 2026-07-31 and 2026-09-12.

## Decision

Upgrade does one simple thing, made safe by git:

1. It works only on a Forge client (`constitution/VENDORED_FROM` present) with
   a clean tree. Anything else is sent to `forge adopt`.
2. It refuses while any worktree of the repo has a story, stage or Lite window
   in progress: finish or abandon it on the current version first.
3. It creates a safety branch at HEAD.
4. It moves the tracked old-format files current Forge cannot read (the fixed
   per-lens review files, old grills and approval files) into
   `.factory/archive/pre-<vendored sha>/`, and keeps everything else:
   stories, history, outcomes, events, ledgers, roadmap, docs, client skills
   and profiles, and any unknown file.
5. It vendors the current machinery. A file is Forge-owned when its bytes
   equal what Forge shipped at the client's vendored commit.
6. It runs the health checks; on any failure it resets to the safety branch.

## Consequences

- The Lean migration, resume plans, inventories, profile hash tables and the
  `.agents/` layout migration are deleted; upgrade shrinks to a few hundred
  lines with tests that build clients from real old commits.
- Clients with a story in progress upgrade only after finishing it, or after
  parking it with `forge upgrade --park <story>` (the supported abandon path:
  its state is archived and its roadmap item returns to pending).
- In practice the "safety branch" is the untouched original branch: upgrade
  works on its own `forge-upgrade/...` branch and commits there, so failure
  means returning to the original branch.
- Recurring-findings history starts fresh for archived reviews.
- The automatic upgrade PR in harness-health is removed: it cannot see
  local work in progress. A developer upgrades with the upgrade skill.
- Supersedes the upgrade parts of 0016, 0045, 0064, 0069 and 0080, and the
  `legacy-upgrade` spec.
