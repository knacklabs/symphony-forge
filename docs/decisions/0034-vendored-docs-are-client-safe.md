---
status: superseded
superseded_by: 0093-lean-forge-rebuild
confirmed_by: "Ravi"
date: 2026-08-10
stories: []
---

# Vendored docs must not reference un-vendored files

## Context

`forge upgrade` copies a fixed set of harness-owned files into a client repo
(`COPY_FILES`, `COPY_WORKFLOWS`, …). `WORKFLOW.md` is one of them. The
traceable-board epic added prose to `WORKFLOW.md` naming the enforcement-gate
workflows by path — `.github/workflows/pr-ticket-check.yml`, `pr-link.yml`,
`board-invariant.yml` — but those workflows are **harness-internal** and are NOT
in `COPY_WORKFLOWS`, so clients never receive them.

Result: any client that runs its own doc-reference check (e.g. myclaw's
`check_architecture.py`) fails on upgrade, because the freshly-vendored
`WORKFLOW.md` points at three workflow files that don't exist in the client repo.
A vendored artifact silently assumed the harness's own filesystem.

## Decision

A file that `forge upgrade` vendors to clients MUST only reference paths that
also exist in every client — i.e. other vendored files, or paths in the client's
own tree. Specifically, a vendored doc may reference a `.github/workflows/*.yml`
only if that workflow is in `COPY_WORKFLOWS`. Harness-internal workflows are
described by name/function in vendored docs, never by a client-unresolvable path.
A gate test enforces this over `COPY_FILES`.

## Consequences

- `WORKFLOW.md`'s gate section now names `pr-ticket-check`/`pr-link`/
  `board-invariant` as harness-internal workflows without path references (and,
  incidentally, updates Gate A's description to the declare-all contract of 0033).
- New guard: `test_vendored_docs_do_not_reference_unvendored_workflows` fails if a
  vendored doc names a non-vendored workflow file — this regression can't recur
  silently.
- The rule is about client-safety of vendored *content*; it does not change which
  files are vendored, and the harness repo keeps its own gate workflows.
