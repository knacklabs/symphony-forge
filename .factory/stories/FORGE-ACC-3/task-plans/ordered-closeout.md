# FORGE-ACC-3 · Task 6 — ordered-closeout

## Context

FORGE-ACC-3's spec and roadmap AC #7–#8 require closeout to be **ordered and
tamper-evident**: all stages done → verify → branch review → functional (when
user_facing) → outcome → pr_ready, with pr_ready additionally requiring a clean
product tree and the outcome stamped on the evidence commit; and no write window
(quickfix/lite/degraded) may open while a stage is active. Today `pr_ready`
collects a flat `missing` list with an inline open-stages check, no product-tree
cleanliness gate, and no outcome-at-HEAD check; `quickfix._open` starts a window
regardless of active stages.

## Design (grilled — all three questions confirmed the recommended option)

- **Order at pr_ready via HEAD stamps** (not record-time gates, which would break
  the lite-window review path): pr_ready requires each artifact present and
  stamped at HEAD, in order.
- **Window refusal is uniform** across quickfix/lite/degraded while any stage is
  active (pause with `stage done --incomplete` if truly needed).
- **Clean tree = worktree AND index** (no staged or unstaged product change).

## Changes (write_scope only — 5 files)

1. **`factory/scripts/factory_lib.py`** — `require_all_stages_done(root)` (all
   decomposition stages `done`; returns the open-stage list) and
   `require_closeout_order(root)` returning the ordered problem list:
   stages-done → `verify` present+ok @HEAD → the three coherent lenses @HEAD
   (this realises "verify before review") → functional @HEAD when `user_facing`
   → `outcome` present with `commit == HEAD`.
2. **`factory/scripts/pr_ready.py`** — replace the inline open-stages check with
   `require_all_stages_done`; call `require_closeout_order`; add a clean
   product worktree **and** index gate (reuse `product_tree_snapshot`), keeping
   the existing repo-kind-aware evidence exclusions.
3. **`factory/scripts/forge_cli/quickfix.py`** — `_open` (shared by
   `cmd_start`/`cmd_lite`/`cmd_degraded_start`) refuses when
   `require_all_stages_done` reports an active stage.
4. **`factory/scripts/forge_cli/phase.py`** — closeout routing lists the steps
   in the enforced order.
5. **`factory/tests/test_gates.py`** — the two required tests below.

## Non-goals / guardrails

- No record-time recorder gates (they'd break lite-window reviews).
- One shared `require_all_stages_done` / `require_closeout_order` seam — no
  inline duplicate in pr_ready or the window guard.
- `outcome` already stamps `commit = head_sha`; this is a check, not new
  plumbing.
- Touch only the 5 write_scope files.

## Reuse (already on the branch)

`product_tree_snapshot` (staged+unstaged product dirt, `forge_cli/stages.py`),
`load_review_artifacts` / `require_coherent_review_run` (`factory_lib.py`),
`load_outcome` + `commit` stamp (`forge_cli/outcome.py`), `load_stages`
(`forge_cli/stages.py`), `head_sha` (`factory_lib.py`).

## Verification

- `test_pr_ready_refuses_out_of_order_or_dirty_or_unstamped_closeout` — a stale
  verify/review (not at HEAD), a dirty product worktree or staged index, or an
  outcome whose `commit != HEAD` → pr_ready refuses; a fully ordered, HEAD-
  stamped, clean closeout → passes.
- `test_mode_start_refuses_while_a_stage_is_active` — `forge stage start` then
  `mode lite` / `quickfix start` / `mode degraded start` all refuse; after the
  stage is done, they open.
- `python3 factory/scripts/check_dual_runtime.py` clean; the pr_ready/mode suite
  green.

## Bootstrap

ACC-3's own story closeout runs under this ordered chain (verify → coherent
three-lens review → outcome → pr_ready, clean tree, outcome at HEAD).
