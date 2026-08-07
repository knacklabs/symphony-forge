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
`prototype/`, `.github/`, and the exempt root files stay freely writable in both
repo kinds. `.factory/` is unchanged by this decision: it stays evidence-guarded
(script-written, never hand-edited — only `.factory/scratchpad.md` is free), and
the repo-kind marker inside it is plan-only (below). So "no over-locking" means
those planning surfaces are untouched, not that `.factory/` is freely writable.
Repo kind is decided by a **positive**
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
recorded decomposition — never a quickfix.** Under an approved plan the machinery
is already writable, so removing the marker grants nothing new; under a quickfix,
a marker change is refused outright.

**The budget is protected structurally, not by exhaustive parsing.** A quickfix
PINS the repo kind at its start (`harness_source` in the window state); while the
window is open the planning lock reads that pin instead of the live marker. So
even if the marker were removed mid-window by a vector the Bash guard does not
catch, classification stays `harness`, machinery keeps being claimed, and the
five-file budget cannot be escaped. This is the guarantee — the deletion guard is
defence-in-depth, not the load-bearing wall.

To keep the quickfix budget honest, it is counted per **created file**, not per
literal operand: a copy/move into a machinery directory expands to
`<dir>/<basename>` per source, so N copies spend N slots. A write whose file set
cannot be bounded from the literal command — a recursive/globbed/brace `rm`/
`git rm` of a product path, or a recursive or glob-sourced copy/move whose
DESTINATION is a product path — is **refused**; the fix must enumerate the exact
paths or be planned. Copy/move opacity is keyed on the destination, never the
source, so a read-OUT backup (`cp -R factory/scripts /tmp/x`) is never blocked.
The heuristic covers the common copy/move shapes. Exotic invocations — the
attached `-tDIR` target form, a bare `mv <dir>` (recursive with no flag), a
`git mv` into a directory, pure shell games (subshells, `xargs`, `\rm`), and
arbitrary code (`python -c os.remove`, `find -delete`) — remain a documented
residual, general to every repo. Per 0013 this Bash guard is drift-defense, not
an adversarial sandbox: those forms are deliberate, not drift, and at worst they
mis-count the budget — never a lock disarm, because the pin keeps classification
correct while a window is open. A determined adversary who runs arbitrary code
AND rewrites the git index — e.g. `python -c os.remove(marker)` then
`git update-index --assume-unchanged` so the deletion does not show in
`git status`/diff (only `git ls-files -v` reveals it) — is explicitly out of
scope, as it is for **any** in-repo gate: nothing running inside the repo can
bind an actor who can execute code and edit the index. The backstop for that
class is process (review discipline, the artifact gates), not this heuristic.

The Bash write guard catches the **common** deletion/relocation vectors that
reach the marker: `rm`/`unlink`, `git rm`/`git mv`, `mv` of the source, and an
ancestor delete (`rm -r .factory`). So the "marker is plan-only" rule holds
against ordinary/drift editing; it is not an absolute — cwd games
(`cd .factory && rm`), `git -C`, indirect pathspecs, and arbitrary code
(`python -c os.remove`, `find .factory -delete`) are beyond the heuristic for the
marker just as they are for `src/app.ts`. For the LOCKED case (no quickfix, no
plan) those are the residual: a change made that way still lands in the working
tree and is caught by the artifact gates (verify / branch autoreview / pr_ready)
UNLESS the actor also hides it via the git index — the arbitrary-shell +
index-tampering class ruled out of scope above. For the quickfix case the pin
closes them entirely (the budget cannot be escaped regardless of vector).
This **refines 0013** (it does not supersede it — 0013
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
  sentinel's content or deletion is forgeable by an actor who runs arbitrary code
  and can rewrite the git index to hide it. It is the same achievable bar as plan
  approval, not a cryptographic guarantee, and no lower than any other in-repo
  gate.
- The product/machinery split now lives in four differently-tuned classifiers
  (`pre_tool_use`, `pr_ready`, `check_refactor_delta`, `stages`); only the lock
  is made repo-kind-aware here. A shared `is_harness_source_repo` seam is added
  now and a triggered deferral tracks harmonizing the rest onto it, so 0005 is
  honored rather than a fifth tuned copy entrenched.
