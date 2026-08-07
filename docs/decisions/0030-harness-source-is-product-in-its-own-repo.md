---
status: proposed
confirmed_by: ""
date: 2026-08-07
stories: [FORGE-LOCK-1]
---

# Harness Source Is Product In Its Own Repo

## Context

The always-armed planning lock (0013) refuses hand-edits to *product* code
without an approved plan or an open quickfix window, but exempts the vendored
harness surface (`factory/`, `constitution/`, `harness/`, `.claude/`, `.codex/`,
…) as machinery. In a client repo that is correct — and 0009 already stops a
client editing the vendored gate surface. But when the harness is dogfooded on
its own repo, that machinery **is** the product: a gate, recorder, schema, or
the lock hook itself can be hand-edited with no plan, no decomposition, no
review — the exact discipline the harness imposes on every client's product
code. The same exemption also makes a quickfix window that touches only those
paths claim zero files, so its closed ledger under-reports scope.

Nothing today distinguishes "this is the harness's own source repo" from "this
is a client that vendored the harness": manifest / `VENDORED_FROM` **absence**
is ambiguous (a pre-manifest client lacks them too), so an absence-based signal
would freeze a real client's `factory/` during planning.

## Decision

In the harness's own source repo, the machinery trees (`factory/`,
`constitution/`, `harness/`, `.claude/`, `.codex/`) are **product** and obey the
planning lock exactly as client product code does; `docs/`, `plans/`,
`.factory/` state, `prototype/`, `.github/`, and the exempt root files stay
freely writable in both repo kinds. Repo kind is decided by a **positive**
committed sentinel `.factory/harness-source.json` (never vendored — `.factory/`
is excluded from all copying); `is_harness_source_repo(root)` is its presence.
The signal is fail-safe: a missing marker degrades to today's exempt behavior, so
no client is ever wrongly locked.

The marker is itself a **product path**, not a freely-writable file: the
planning lock governs creating, editing, or **deleting** it. The Bash write
guard is extended to treat a deletion of a product path as a write, covering the
direct-delete commands (`rm`, `unlink`) and their git equivalents (`git rm`,
`git mv`). So flipping source→client to unlock machinery is never a silent
hand-edit, `rm`, or `git rm`.

Crucially, the marker may be changed **only under an approved plan with a
recorded decomposition — never a quickfix.** The marker decides whether the
machinery trees are product at all, so a quickfix that could `rm` it as its
first claimed file would flip the repo to client-mode and let every later
machinery write skip the five-file budget entirely, defeating the very bound the
quickfix exists to enforce. Under an approved plan the machinery is already
writable, so removing the marker grants nothing new; under a quickfix, a marker
change is refused outright.

The Bash write guard catches the common deletion/relocation vectors that reach
the marker: `rm`/`unlink`, `git rm`/`git mv` (honoring `git -C` and treating an
un-enumerable `--pathspec-from-file` conservatively), `mv` of the source, an
ancestor delete (`rm -r .factory`), and a `cd` into `.factory` before the delete.
The ceiling is 0013's, stated honestly: this is drift-defense, not an adversarial
sandbox. Arbitrary code that can also drop a file — `python -c os.remove`,
`find .factory -delete`, `xargs`, `git checkout`/`reset`/`restore`/`clean` — is
beyond the heuristic for the marker just as it is for `src/app.ts`; git history
keeps such acts visible and the artifact gates (verify/review/pr_ready) remain
the backstop. This **refines 0013** (it does not supersede it — 0013
stays authoritative for client repos; its "harness files stay freely writable"
consequence now applies only to *client* repos) and complements 0009.

## Consequences

- A change to harness machinery in this repo goes through a plan + decomposition
  or a bounded quickfix window, and a harness-repo quickfix now claims the
  machinery files it touches against its 5-file budget (the zero-scope report is
  fixed by the same classification change — no separate quickfix code).
- Client behavior is unchanged: their vendored `factory/` etc. stay writable
  during planning; only a repo carrying the sentinel is held to the rule.
- Trust ceiling matches 0029: this defends against drift/honest mistakes, not an
  adversarial session — a session can still open its own quickfix, and the
  sentinel's content or deletion is forgeable (but visible in git). It is the
  same achievable bar as plan approval, not a cryptographic guarantee.
- The product/machinery split now lives in four differently-tuned classifiers
  (`pre_tool_use`, `pr_ready`, `check_refactor_delta`, `stages`); only the lock
  is made repo-kind-aware here. A shared `is_harness_source_repo` seam is added
  now and a triggered deferral tracks harmonizing the rest onto it, so 0005 is
  honored rather than a fifth tuned copy entrenched.
