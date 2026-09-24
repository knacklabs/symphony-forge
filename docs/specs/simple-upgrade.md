---
slug: simple-upgrade
title: Simple upgrade: one safe step from any factory-era client to current
status: confirmed
saved: 2026-09-24T17:03:50+00:00
---

# Simple upgrade: one safe step from any factory-era client to current

## Why

`forge upgrade` is about 4,800 lines, most of it machinery for converting
in-progress state between versions. A simulation of real client versions
found none upgraded cleanly: pre-Lean clients were left half-upgraded,
stories in progress were stranded, and every upgraded client failed its next
upgrade. All real clients were vendored between 2026-07-31 and 2026-09-12.
Decision 0088 replaces the machinery with one simple, git-protected step.

## Behaviour

**Scope.** One step takes any client vendored after the machinery moved to
`factory/` (2026-07-24) to the current harness. A pre-rename client, whose
Forge machinery still lives under `.agents/`, is refused with exact
instructions: check out the harness tag `forge-legacy-upgrade` (the last
harness commit that migrates `.agents/`, tagged by this story) into a
separate worktree, run its upgrade, then run this one.

**Before anything is written, upgrade refuses:**
- a harness checkout with uncommitted changes (vendoring reads the harness's
  committed tree only);
- a target without `constitution/VENDORED_FROM`, or whose vendored commit is
  not an ancestor of the harness HEAD (unknown, unrelated or newer: no
  downgrades); a repo without Forge is pointed to `forge adopt`;
- a pre-rename client (above);
- a target with any tracked or untracked change;
- a worktree of the repo that git lists but that cannot be read (missing
  folder or unreadable state), named, with `git worktree prune` suggested;
- work in progress in any worktree, unless that story is parked (below). Work
  in progress means: a story pointer (the worktree's git-local pointer, else
  `.factory/run.json`) whose phase is anything but `shipped`; any active stage
  in the git-local stage state; an open Lite, quickfix or degraded window; or
  any plan in `plans/active/` whose roadmap item is not done, whether approved
  or not. The message lists each worktree and story and says to finish it on
  the current version or park it;
- a client file inside Forge's machinery folders (`factory/`, `constitution/`,
  `harness/`, except client skills under `factory/skills/`) that Forge never
  shipped, named, to be moved out first;
- a client-owned or ignored file at a path the current machinery must write.

Acquiring upgrade's own git-local lock is not a repository write; preflight
runs under that lock, and a refusal leaves no repository file, branch or
git-local state changed.

**Parking a story.** `forge upgrade --park <story>` (repeatable) is the
supported way to abandon a story for the upgrade. It is refused while any
worktree other than the target holds that story's pointer or stage (remove
those worktrees first). In the target, the story's workflow state and plan
record move to the archive, its plan moves to `plans/archive/`, its run
pointer is cleared if it points at the story, and its roadmap item returns to
pending so it is planned fresh on the new version.

**The upgrade itself** runs on a new branch `forge-upgrade/<vendored sha>-<ts>`
created from the target's current HEAD; the original branch is never touched
and is the safety point. It:
1. copies the git-local Forge state directory aside (restored on failure);
2. moves the tracked old-format files current Forge cannot read into
   `.factory/archive/pre-<vendored sha>/`, keeping each file's original path
   under that directory. The table is exactly: the fixed per-lens review
   files (`quality.json`, `performance.json`, `security.json`) under story,
   task and history `reviews/` folders, and the root `.factory/`
   `decomposition.json`, `tests.json` and `verify.json`. Nothing else is
   archived; ignored and untracked files are never moved;
3. vendors the current machinery from the harness's committed tree. A file is
   Forge-owned when its bytes equal what Forge shipped at the client's
   vendored commit; only those are refreshed or retired;
4. runs the dual-runtime, scaffold and vendor-integrity checks, `forge next`,
   `forge audit`, `forge doctor --fast` and a load of the board data;
5. commits everything on the upgrade branch with a message naming the old and
   new harness commits and a `Forge-Upgrade: <old>..<new>` trailer, then
   prints the next steps (review commands and how to open the PR).

On any failure it discards the upgrade branch, returns to the original branch,
removes files it added, and restores the git-local Forge state, leaving the
client exactly as before. Running upgrade again with the same harness changes
nothing; a later upgrade to a newer harness works the same way.

**After the upgrade** the developer follows the printed steps: review the
upgrade commit (`git show --stat` and `git diff <original>..HEAD`) and open a
PR from the upgrade branch. The PR ticket check treats a commit with the
`Forge-Upgrade` trailer as a re-vendor only when every change in it is a
harness-owned path, the vendor manifest, an exact rename (100% similar) of a
path matching the archive table into `.factory/archive/pre-*/`, or an addition
of one of Forge's own ignore blocks; anything else needs a normal ticket.

**Skills ready.** The upgrade report ends with the same required-skill check
`forge doctor` runs (impeccable, grill-me, the design skills, Autoreview, the
Codex plugin): it names each skill that is missing or outdated and the one
command that fixes it, `./forge doctor --fix`. It reports and never blocks the
upgrade.

**Archived reviews.** A task with no selected review but with archived review
files under `.factory/archive/pre-*/` shows on the board as "reviewed before
upgrade"; the files stay readable there. CI does not re-check tasks that
already shipped.

**No more automatic upgrade PRs.** The harness-health workflow stops running
upgrades (it cannot see work in progress on a developer's machine), and
WORKFLOW.md says so.

**The upgrade skill** says: find work in progress and ask the developer to
finish or park each story, clean the tree, run `forge upgrade`, and follow
its printed steps. Because upgrade prints its own steps, an older installed
copy of the skill still leads to the right result; `forge doctor` warns when
the installed skill differs from the harness copy.

## Acceptance criteria

- Clients built from harness commits 8563f8c6, 43f6bede and 47516c55, with no
  work in progress, upgrade to current with exit 0 on an upgrade branch; then
  `forge next`, `forge audit`, `forge doctor --fast` and the board data run
  without errors.
- A client built from a pre-rename commit (before 2ebba90d) is refused with
  the `forge-legacy-upgrade` instructions.
- A second upgrade with the same harness leaves no changes; an upgrade to a
  newer harness commit succeeds; a client vendored at a commit that is not an
  ancestor of the harness is refused.
- Work in progress in any worktree (a task sealed and awaiting merge, an
  approved plan with no pointer, a saved plan awaiting approval) is refused
  before anything is written, naming the worktree and story; an unreadable
  listed worktree is refused by name.
- `--park <story>` lets that story through: its state and plan record are
  archived, its plan moves to `plans/archive/`, its roadmap item is pending
  and a new plan for it can be saved; parking is refused while another
  worktree holds the story.
- A dirty target, a dirty harness, a missing vendored commit, an unshipped
  client file in the machinery folders, and a client or ignored file at a
  required machinery path are each refused with no repository change.
- A failure injected after vendoring leaves the original branch, the tracked
  files and the git-local Forge state exactly as before, with no upgrade
  branch left behind.
- Client skills, custom Codex profiles, docs/memory, grill records and unknown
  `.factory` files survive; exactly the table's files end up under
  `.factory/archive/pre-<sha>/` at their original relative paths, and the
  board shows those tasks as reviewed before upgrade.
- The upgrade report names every missing or outdated required skill with
  `./forge doctor --fix`, and a missing skill never fails the upgrade.
- The upgrade PR passes the PR ticket check; a hand-made change added to the
  upgrade commit does not.
- The Lean migration, resume plans, profile hash tables and `.agents`
  migration code are deleted from current Forge.

## Success measure

- Metric: share of local client checkouts with no work in progress that
  upgrade on the first run without manual repair.
- Baseline: 0 of 9 simulated clients (2026-09-24).
- Target: every idle client checkout, including a real myclaw checkout.
- Check date: 2026-10-15
