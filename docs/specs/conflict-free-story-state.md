---
slug: conflict-free-story-state
title: Conflict-free story state: overlapping PRs stop colliding on recorded evidence
status: confirmed
saved: 2026-08-14T05:47:16+00:00
---

# Conflict-free story state: overlapping PRs stop colliding on recorded evidence

> Captured 2026-08-14 from the PR #104 merge post-mortem. Root cause of the
> every-PR conflicts: story evidence in repo-wide singleton files, an archive
> move that invites rename detection, and an append ledger relying on a
> per-clone merge driver. Decision 0022's principle — one record per file
> removes the conflict rather than resolving it — applied to the rest of the
> recorded state. Evidence: lessons factory-merge-resolution-needs-a-path and
> ledger-directories; decision 0045.

## Why

- `.factory/run.json`, `decomposition.json`, `stages.json`, `tests.json`,
  `outcome.json`, `verify.json` are singletons every story rewrites; any two
  overlapping PRs conflict on them (delete-vs-modify after one side's
  `pr_ready` archive).
- `pr_ready` moves `.factory/*` to `.factory/history/<story>/`; git rename
  detection then pairs one branch's archived copies with the other's live
  files (upstream WIN-ENC grills surfaced inside FORGE-ACC-1's archive).
- `events.jsonl` needs an unversionable per-clone union driver that reorders
  lines when it fires.
- A conflicted `factory_lib.py` or `run.json` crashes the PreToolUse hook,
  fail-closing every write tool including the ones needed to resolve the
  merge; the recovered hook has no sanctioned path for `.factory` conflict
  resolution.

## Behaviour

- **Story-scoped evidence.** From intake, recorders and gates read/write
  `.factory/stories/<KEY>/…` for all task-scoped artifacts (decomposition,
  stages, verify, tests, reviews, outcome, grills, approval events, briefs).
  Native story approval remains the story's `plan-approval.json`; native task
  approval remains on its task-grill record. `pr_ready` marks
  the story shipped in place — no archive move, no rename strands. Existing
  `.factory/history/` archives stay readable.
- **Derived active-story pointer.** `run.json`'s merge-contested authority
  ends: the active-story pointer is worktree-local (untracked); phase state
  derives from the story directory's artifacts.
- **One event per file.** `events.jsonl` is replaced by per-event files
  (0022 pattern, as lessons already do); `forge history` reads both formats.
- **Roadmap self-heals.** `forge next` detects a fresh merge and runs
  `roadmap heal` (done-wins union) automatically.
- **Mid-merge hook carve-out.** With unmerged index entries, the PreToolUse
  hook permits git-native resolution (`checkout --ours/--theirs`, `rm`,
  `add`) for exactly those paths; content hand-writes stay refused. The hook
  falls back to a minimal static deny-list instead of crashing when
  `factory_lib` or state files are unparseable.
- **Migration.** Live singletons migrate to the story layout at the next
  intake; `forge upgrade` carries the change to client repos.

## Acceptance criteria

- Two story worktrees recording concurrently produce zero overlapping
  `.factory` paths; merging either PR into the other's base yields no
  `.factory` conflicts in the gate tests' merge simulation.
- `pr_ready` completes without moving files; the shipped story's evidence
  remains at its recorded paths and `forge history`/board read it.
- Recording an event creates a new file; no shared JSONL is appended; `forge
  history` reads legacy events.jsonl and per-event files together.
- After a merge commit, `forge next` heals the roadmap without being asked.
- With a synthetic unmerged index, git-native resolution commands on exactly
  the unmerged `.factory` paths pass the hook; the same commands on merged
  paths are refused; a syntactically broken factory_lib no longer blocks
  tool calls (deny-list fallback engages).
- Existing suite green; `check_dual_runtime.py` green; lite/quickfix/degraded
  unchanged.

## Non-goals

- No change to roadmap.json's single-file shape.
- No rewrite of existing `.factory/history/` archives.
- No new merge drivers or gitattributes dependencies.
