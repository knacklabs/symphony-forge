---
slug: simple-upgrade
title: Simple upgrade: one safe step from any client version to current
status: draft
saved: 2026-09-24T12:52:11+00:00
---

# Simple upgrade: one safe step from any client version to current

## Why

`forge upgrade` is about 4,800 lines, most of it machinery for converting
in-progress state between versions. A simulation of real client versions
found none upgraded cleanly: pre-Lean clients were left half-upgraded,
stories in progress were stranded, and every upgraded client failed its next
upgrade. All real clients were vendored between 2026-07-31 and 2026-09-12.
Decision 0088 replaces the machinery with one simple, git-protected step.

## Behaviour

**Before anything is written, upgrade refuses:**
- a harness checkout with uncommitted changes (vendoring reads the harness's
  committed tree only);
- a target without `constitution/VENDORED_FROM`, or whose vendored commit is
  not a commit in the harness repository (a repo without Forge is pointed to
  `forge adopt`);
- a pre-rename client that still carries Forge machinery under `.agents/`:
  it is told to upgrade first with the last harness version that migrates
  `.agents/` (2026-08-04 or later, before this change), then run this upgrade;
- a target with any tracked or untracked change;
- a target where any worktree has work in progress, unless that story is
  parked (below). Work in progress means: a story pointer (the worktree's
  git-local pointer, else `.factory/run.json`) whose phase is anything but
  `shipped`; any active stage in the git-local stage state; an open Lite,
  quickfix or degraded window; or an approved story plan in `plans/active/`
  whose roadmap item is not done. The message lists each worktree and story
  and says to finish it on the current version or park it. Unreadable state
  is refused, not guessed;
- a client-owned file, or an ignored file, at a path the current machinery
  must write.

**Parking a story.** `forge upgrade --park <story>` (repeatable) is the
supported way to abandon a story for the upgrade: its old workflow state is
archived with the other old files, its plan moves to `plans/archive/`, and its
roadmap item returns to pending so it is re-planned on the new version.

**The upgrade itself** runs on a new branch `forge-upgrade/<vendored sha>-<ts>`
created from the target's current HEAD; the original branch is never touched
and is the safety point. It:
1. copies the git-local Forge state directory aside (restored on failure);
2. moves the tracked old-format files current Forge cannot read into
   `.factory/archive/pre-<vendored sha>/`, keeping each file's original path
   relative to the repo under that directory. The list is one explicit table:
   root `decomposition.json`/`tests.json`/`verify.json`, `grills/`,
   grill-round files, `plan-approval.json`, `plan-mode/`, and the fixed
   per-lens review files under stories, tasks and history. Ignored and
   untracked files are never moved. Everything else stays: story and history
   directories, outcomes, events, ledgers, `run.json`, the roadmap, docs,
   client skills and profiles, and unknown files;
3. vendors the current machinery from the harness's committed tree. A file is
   Forge-owned when its bytes equal what Forge shipped at the client's
   vendored commit; only those are refreshed or retired;
4. runs the dual-runtime, scaffold and vendor-integrity checks plus
   `forge next` and `forge audit`;
5. commits everything on the upgrade branch with a message naming the old and
   new harness commits.

On any failure it discards the upgrade branch, returns to the original branch,
removes files it added, and restores the git-local Forge state, leaving the
client exactly as before. Running upgrade again with the same harness changes
nothing; a later upgrade to a newer harness works the same way.

**After the upgrade** the developer reviews the upgrade commit
(`git show --stat` and `git diff <original>..HEAD`, which include archived
moves) and opens a PR from the upgrade branch. The PR ticket check accepts an
upgrade commit's re-vendored machinery, `.factory/archive/pre-*/` moves and
the upgrade's `.gitignore` and `.codex` edits as a harness re-vendor.

**Archived reviews.** Tasks whose reviews were archived show on the board as
reviewed before the upgrade; their review files remain readable in the
archive. CI does not re-check tasks that already shipped.

**No more automatic upgrade PRs.** The harness-health workflow stops running
upgrades (it cannot see work in progress on a developer's machine), and
WORKFLOW.md says so.

**The upgrade skill** walks the agent through: find work in progress and ask
the developer to finish or park each story, clean the tree, run upgrade,
review the upgrade commit, open the PR. It drops the old post-upgrade audit,
doctor repair, backfill and re-authoring steps.

## Acceptance criteria

- Clients built from harness commits 8563f8c6, 43f6bede and one Lean-era
  commit, with no work in progress, upgrade to current with exit 0 on an
  upgrade branch; then `forge next`, `forge audit`, `forge doctor --fast` and
  the board data run without errors.
- A second upgrade with the same harness leaves no changes; an upgrade to a
  newer harness commit succeeds.
- Work in progress in any worktree (including a task sealed and awaiting
  merge, and an approved plan with no pointer) is refused before anything is
  written, naming the worktree and story; `--park <story>` lets that story
  through, archives its state and returns its roadmap item to pending.
- A dirty target, a dirty harness, a missing or unknown vendored commit, a
  pre-rename `.agents/` client, and a client or ignored file at a required
  machinery path are each refused before anything is written.
- A failure injected after vendoring leaves the original branch, the tracked
  files and the git-local Forge state exactly as before, with no upgrade
  branch left behind.
- Client skills, custom Codex profiles, docs/memory and unknown `.factory`
  files survive; the listed old-format files end up under
  `.factory/archive/pre-<sha>/` at their original relative paths.
- The upgrade PR passes the PR ticket check.
- The Lean migration, resume plans, profile hash tables and `.agents`
  migration code are deleted.
