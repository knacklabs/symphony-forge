---
status: superseded
superseded_by: 0093-lean-forge-rebuild
confirmed_by: "vrknetha"
date: 2026-07-24
stories: []
---

# Harness machinery lives in factory/, not .agents/ (Codex sandbox collision)

## Context

Recent Codex CLI versions sandbox-protect `<repo>/.agents/` as an
agent-config directory (same class as `.codex/` and `.git`): writes are
denied at both the apply_patch layer ("writing outside of the project")
and the macOS seatbelt layer ("operation not permitted"), even though the
repo is a writable root. Empirically confirmed 2026-07-24 on plugin 1.0.6
+ CLI 0.145.0; a second team member reported the same failure. Because the
harness stored all machinery under `.agents/`, delegated Codex write tasks
could never modify or extend the harness. The maintainer chose the rename
over documenting the boundary (chat, 2026-07-24).

## Decision

Harness machinery (scripts, schemas, prompts, skills, tests) lives in
`factory/` — the machine; `.factory/` remains its per-task state. All
prior references to `.agents/` in decision records, archived evidence,
and ledger history read as `factory/`. `harness/` was not used: it
already holds the stack scaffolds.

## Consequences

- Codex write tasks can implement harness changes again; `.git` stays
  sandbox-protected, so commits belong to the orchestrator.
- `.codex/` remains Codex-protected by design; role/config edits there
  are orchestrator or interactive-session work.
- Historical artifacts are not rewritten; this record is the read-key.
- `.gitignore` carries a transitional `.agents/` entry: already-running
  sessions execute hooks from an untracked on-disk copy until restarted.
- Client repos vendored from earlier harness versions migrate on the next
  `forge upgrade`.
