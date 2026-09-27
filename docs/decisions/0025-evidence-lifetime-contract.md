---
status: superseded
superseded_by: 0093-lean-forge-rebuild
confirmed_by: "vrknetha"
date: 2026-08-05
stories: []
supersedes: 0024-evidence-lifetime-split
---

# Evidence Lifetime Contract

## Context

0024 named the right problem — `.factory/` accumulates committed bytes nothing
reads, and every client repo vendors the habit — and prescribed an overweight
cure. Its "lifetime split" would have uncommitted `run.json` and `stages.json`,
which forced fail-closed rework into every gate that reads them, a board
change (it renders shipped stories from archived stage history), a
worktree-loss policy, and CI disambiguation between "fresh clone" and "state
missing". All of that machinery relocated about 8KB of small files.

Two facts, verified in code, make the actual fix trivial:

1. **`.factory/delegations.jsonl` is a diagnostic mirror with zero readers.**
   The authority copy that stage close validates lives in the git control dir,
   already uncommitted (`forge_cli/delegate.py` — "the mirror is deliberately
   best-effort... diagnostic only"). The tracked copy is written and never
   read.
2. **Briefs are read from disk in the same worktree** at compose time and at
   stage close. Git tracking adds nothing to their function; they are
   regenerable from the decomposition and lessons via `forge delegate`.

Measured on this repo: briefs 208KB + diagnostic briefs 12KB + the delegation
mirror 76KB ≈ **296KB of tracked content with no reader** — more than the
audit's original 222KB figure. The history archive (372KB for seven stories)
is mostly durable artifacts at reasonable size and is not the problem.

## Decision

**Stop committing what nothing reads. Move no authority.**

1. Gitignore `.factory/briefs/`, `.factory/diagnostic-briefs/`, and
   `.factory/delegations.jsonl`; `git rm --cached` them in this repo, and
   `forge upgrade` does the same in existing clients (a `.gitignore` rule does
   nothing to an already-tracked file).
2. Everything else stays committed exactly as today: `run.json`,
   `stages.json`, signals, events, grills, the history archive, and every
   hard-gate artifact. No gate changes, no board changes, no fail-closed
   rework, no worktree-loss policy — those were costs of relocating
   authority, and no authority moves.
3. Going forward, a recorded field arrives with its reader — a consumer in
   code or a named human question — or it is not recorded. Existing write-only
   fields are trimmed opportunistically when a recorder is next touched, not
   as a project.

## Consequences

- ~296KB leaves the tracked tree now; per-story retained cost drops from
  ~70KB to the ~15–20KB the history archive actually earns.
- The review bundle, secret-scanner surface, and merge surface shrink with
  it — the opaque-launch-id false-positive class disappears from tracked
  content, and gitignored ledgers stop merging at all (0022 keeps governing
  the durable ones).
- The delegation authority has always lived in the git control dir and always
  died with a removed worktree; this decision does not change that exposure,
  it only stops committing a copy nothing consults.
- Open signals stay committed and untouched, so the signal-authority hazard
  the 0024 validation flagged does not arise.
- Implementation is one bounded task: the ignore rules, the `git rm --cached`
  migration here and in `forge upgrade`, and a test proving a client upgrade
  untracks all three paths.
- **The migration commit propagates as a deletion.** `--cached` keeps files on
  disk only on the machine that ran it; a teammate's pull removes their clean
  local copies. That is harmless for the mirror (each clone's authority lives
  in its own git control dir) and for closed tasks, but a dev mid-task loses
  the composed brief and stage close refuses until `./forge delegate
  <task-id>` recomposes it from the decomposition. Upgrade says this in its
  output; run the migration at a story boundary when possible.
