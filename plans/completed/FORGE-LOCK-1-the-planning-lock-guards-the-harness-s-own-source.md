---
issue: FORGE-LOCK-1
title: The planning lock guards the harness's own source
status: approved
saved: 2026-08-07T03:32:01+00:00
story: FORGE-LOCK-1
decisions_reviewed:
  - 0001-determinism-contract
  - 0002-concurrency-one-task-per-branch
  - 0003-model-tiers-terra-explore-sol-implement
  - 0005-recurring-findings-escalation
  - 0006-lessons-ledger
  - 0007-stage-commit-loop
  - 0008-loop-health-audit
  - 0009-frozen-gate-integrity
  - 0010-client-signoff
  - 0011-orchestrator-runs-autoreview
  - 0012-project-level-memory
  - 0013-always-armed-planning-lock
  - 0014-specs-before-signoff
  - 0015-plan-contradiction-gate
  - 0016-machinery-dir-rename
  - 0017-repo-as-system-of-record
  - 0018-delegation-gates
  - 0021-derived-ordering
  - 0022-conflict-free-ledgers
  - 0023-stage-delta-by-ref
  - 0025-evidence-lifetime-contract
  - 0026-bundled-example-validated-by-production-validators
  - 0027-responsive-proof-without-a-browser
  - 0028-path-boundary-invariant
  - 0029-plan-approval-in-plan-mode
---

# FORGE-LOCK-1 — The planning lock guards the harness's own source

## Problem

The planning lock (decision 0013) refuses hand-edits to *product* code unless
there is an approved plan (+ recorded decomposition) or an open quickfix
window. In `pre_tool_use.py`, `PLANNING_WRITE_OK` (lines 34-38) exempts
`factory/`, `docs/`, `constitution/`, `harness/`, `.claude/`, `.codex/`,
`plans/`, `prototype/`, … — the vendored harness surface. In a **client** repo
that is correct: those trees are machinery the client vendored, not the
client's product, and 0009 already stops a client editing the gate surface
(hash manifest, fix-direction-outward).

But when the harness is dogfooded on **itself** — this repo — that machinery
**is** the product. So a change to `factory/scripts/*` (a gate, a recorder, the
lock hook itself) lands with no plan, no decomposition, no review — exactly the
discipline the harness imposes on every client's product code. Two concrete
holes:

- The lock never fires for a `factory/` hand-edit here (`product_path()`
  returns `None` at line 97-100).
- A quickfix window that touches only `factory/`/`constitution/`/`harness/`
  paths claims **zero** files: `guard_product_writes` returns early at
  `pre_tool_use.py:222-226` before `claim_files()` runs, so the closed ledger
  entry reports `"files": []` — a bounded-scope window that recorded no scope.

The harness must hold itself to its own rule *in its own repo*, while leaving
client behavior exactly as it is today.

## Scope / Non-goals

**In scope**
- Introduce a durable repo-kind marker that positively identifies the harness's
  own source repo, and commit it to this repo.
- Make the planning lock (`pre_tool_use.py`) repo-kind-aware: in the harness
  source repo the machinery trees classify as product (locked + quickfix-
  claimed); in a client repo, unchanged (exempt).
- The quickfix zero-scope fix falls out of the same classification change (no
  separate quickfix code path).
- Tests proving the two repo kinds are classified differently, in both
  directions, and that the marker never reaches a vendored client.
- One decision record refining 0013's scope for the harness repo.

**Non-goals**
- The three *other* product/machinery classifiers — `pr_ready.py`
  `EVIDENCE_PATHS`, `check_refactor_delta.py` `EXCLUDE_PREFIXES`, `stages.py`
  `WORKFLOW_PATHS` — are **not** made repo-kind-aware here. They govern
  evidence attribution and diff-delta, not the lock; each is a differently
  tuned set. Harmonizing them onto one shared classifier is a separate refactor
  (see Risks — a deferral with a trigger is filed, honoring 0005 rather than
  entrenching a 5th tuned copy).
- No change to 0009's frozen-gate manifest, to client `forge init/adopt/
  upgrade`, or to what counts as product in a *client* repo.
- Not an adversarial sandbox: like 0013, this defends against drift/honest
  mistakes, not a session that deliberately opens its own quickfix. Same trust
  ceiling as 0029.

## Acceptance Criteria

1. A hand-write (Edit/Write or a Bash redirect) under `factory/` **in the
   harness's own repo** is denied when `plan_status` is not approved and no
   quickfix window is open.
2. The same write under `factory/` **in a client repo** (no harness-source
   marker) is allowed, exactly as today.
3. A quickfix window in the harness repo that touches `factory/` paths claims
   them against the 5-file budget; the closed ledger entry reports the real
   files, not `[]`.
4. A test proves the two repo kinds classify the same path differently, and a
   test proves a freshly scaffolded/vendored client does **not** carry the
   marker (so it classifies as a client).

## Technical Approach

**(a) Repo-kind marker — a positive sentinel in `.factory/`.**
Add `.factory/harness-source.json` (`{"role": "harness-source", "repo":
"symphony-forge"}`), committed to this repo. `.factory/` is already excluded
from every vendoring path (`COPY_TREES`/`INIT_COPY_TREES` and adopt all skip
`.factory`), so the marker never reaches a client — no code change needed to
keep it out, but a test pins it. It is static config, not recorded evidence
(no `record_*` script, no `factory/schemas/` entry).

Chosen over reusing manifest/`VENDORED_FROM` absence because those are
**fail-dangerous**: a pre-manifest or pre-`VENDORED_FROM` client lacks them
too, and "absence ⇒ harness ⇒ lock their factory/" would freeze a real
client's planning (violates AC #2). A positive harness marker is
**fail-safe**: if it is ever missing, the repo degrades to today's exempt
behavior and no client is ever wrongly locked.

**Marker creation wrinkle (mechanical).** The hook already denies raw
`.factory/` writes (`test_factory_state_is_never_hand_written`) — evidence must
enter via `record_*` scripts. The sentinel is config, not evidence, so it gets
**one** entry in the hook's evidence-write allowlist (the same exemption
`.factory/scratchpad.md` already has), letting it be authored/committed once.
This is the only reason the marker must be created in the same task that edits
the hook (allowlist entry lands first, then the file writes).

**(b) Small shared discriminator.** New `factory/scripts/forge_cli/
repo_kind.py` (or a helper in an existing small module) exposing
`is_harness_source_repo(root) -> bool` = the marker file exists. One function,
imported where needed. Placed as a shared helper (not inlined into the hook's
tuple) so the deferred harmonization of the other three classifiers has one
seam to adopt — without making duplication worse now.

**(c) Repo-kind-aware lock in `pre_tool_use.py`.** The machinery trees that
flip to product **only in the harness source repo** (grilled — "machinery only,
docs/ free"): `factory/`, `constitution/`, `harness/`, `.claude/`, `.codex/`.
Stay exempt in **both** repo kinds: `docs/`, `plans/`, `.factory/`,
`prototype/`, `.github/`, and the exempt **root files** (`AGENTS.md`,
`CLAUDE.md`, `WORKFLOW.md`, `harness.yaml`, …). Rationale: `docs/` is
discovery/spec/architecture authoring (0013 keeps it ceremony-free; its
gate-critical decisions/memory are script-written and pass the hook anyway);
`.github/` (CI) and the root process-contract files are low-churn planning
surfaces reviewed via PR, not the machinery trees the story targets.
`product_path()` subtracts the machinery prefixes from the exempt set when
`is_harness_source_repo(root)`. Everything downstream is unchanged: once a
`factory/` write classifies as product, the existing gate logic
(`plan_status`/decomposition/quickfix + `claim_files`) applies verbatim — which
is why AC #3 needs no new code.

Workflow-script writes are unaffected: the hook's Bash guard only catches
redirects/`tee`/`sed -i`/`cp`/`mv`/`touch`, not `python3 factory/scripts/…`
invocations, so `./forge` recorder commands that write under `factory/` (if
any) still pass. Only raw hand-edits are locked — the intended target.

**(d) Marker committed + kept out of clients.** Commit the sentinel; a test
scaffolds a client and asserts the marker is absent there.

## Decisions

One new record (drafted before decomposition):
`docs/decisions/0030-harness-source-is-product-in-its-own-repo.md` — "In the
harness's own source repo the vendored machinery trees are product and obey the
planning lock; a positive `.factory/` marker discriminates repo kind; client
behavior is unchanged." **Refines** 0013 (does not supersede — 0013 stays
authoritative for client repos; this narrows its "harness files stay freely
writable" consequence to *client* repos only). Consistent with 0009 (clients
can't edit gate machinery; the harness now can't either without a plan).

Rejected simpler approach (recorded here as the decision's alternative):
manifest/`VENDORED_FROM`-absence discrimination — rejected as fail-dangerous
per 4(a).

## Surface Impact

| Surface | Class | Note |
|---|---|---|
| Runtime behavior | Changed | Lock fires on machinery hand-edits in the harness repo; quickfix now claims those files |
| API | N-A | — |
| Data/schema | Changed | New `.factory/harness-source.json` marker (static config, no schema); one entry added to the hook's `.factory/` write-allowlist so it can be committed; no existing schema altered |
| CLI/ops | Unchanged by design | No new/changed commands; quickfix/plan flows behave identically, just now applied to machinery paths in-repo |
| UI | N-A | — |
| Docs | Changed | New decision 0030; one line noting harness self-governance where the lock is documented |
| Tests | Changed | New lock/quickfix/marker classification tests (§8) |
| Other classifiers (`pr_ready`/`check_refactor_delta`/`stages`) | Deferred | Not made repo-aware here; deferral filed with a trigger (Risks) |

## Task Decomposition

Small story — one bounded task (`user_facing: false`):

**Task 1 — Repo-kind-aware planning lock + marker.**
`pre_tool_use.py` (repo-kind branch in `product_path()`), new
`repo_kind.is_harness_source_repo`, `.factory/harness-source.json` marker
committed, and the `test_gates.py` tests below. The implementer writes and
records the tests. Disjoint write scope; nothing else depends on it.

(If the grill splits marker-plumbing from the hook change, it becomes two
sequential tasks in one worktree — but the change is small enough for one.)

## Risks

- **Self-lockout during this very story.** While planning FORGE-LOCK-1,
  `plan_status` is not yet approved — but implementation writes to `factory/`
  happen *after* approval (plan_status=approved + decomposition recorded →
  unlocked), the same path client product code already takes. Verify a scratch
  rehearsal: locked before approval, writable after. Also confirm no
  planning-phase `./forge` command writes raw under a newly-locked tree.
- **A client wrongly locked (AC #2 regression).** Mitigated by fail-safe
  marker direction + an explicit both-directions test + a marker-absent-in-
  scaffold test.
- **Duplicated classifier drift (0005 spirit).** The classification now lives
  in 4 tuned copies; this story adds repo-awareness to one. To avoid a 5th
  entrenchment, the shared `is_harness_source_repo` seam is introduced now and
  a deferral is filed: `./forge defer add "harmonize product/machinery
  classification across pre_tool_use/pr_ready/check_refactor_delta/stages onto
  one repo-kind-aware classifier" --trigger "any of the 4 classifiers needs a
  path-set change again"`. `stages.py:35-42` already flags the harness-repo gap
  in a comment — the natural first adopter.
- **Marker leaks into a client.** `.factory/` is excluded from all vendoring;
  pinned by a scaffold-has-no-marker test.

## Verify Plan

`python3 factory/scripts/verify.py` (check_dual_runtime, check_factory_scaffold,
full pytest). Falsifiers, each a test:
- Harness repo (marker present): raw Edit/Write and a Bash redirect under
  `factory/` are **denied** without an approved plan; **allowed** with
  plan_status=approved + decomposition recorded.
- Client repo (no marker): the same `factory/` write is **allowed** (AC #2) —
  the both-directions classification test (AC #4).
- Harness-repo quickfix: a window touching `factory/` paths claims them; closed
  ledger reports the real files, budget still refuses the 6th (AC #3).
- A freshly scaffolded client (`init`/adopt harness) carries **no**
  `.factory/harness-source.json` (AC #4).
- `docs/`, `plans/`, `.factory/`, `prototype/` stay writable in the harness
  repo (no over-locking) — regression guard.
- Scratch rehearsal: this story's own machinery edits are blocked pre-approval,
  unblocked post-approval; no planning-phase workflow command is blocked.
Then ONE autoreview pass (quality, performance, security), loop until clean.

## On approval

Record approval with `./forge plan approve --by "vrknetha"`, re-save the
unchanged plan, draft + reference decision 0030, decompose (one task), file the
harmonization deferral, implement via `./forge delegate`, verify + autoreview,
then evidence → PR → merge — the same flow as the prior three stories.
