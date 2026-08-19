# FORGE-ACC-3 · Task 5 — coherent-branch-review

## Context

FORGE-ACC-3's spec and roadmap AC #6 require the three review lenses to be **one
coherent run over one brief at one branch state** — not three artifacts stitched
from different runs or stale branch states. Today `review-brief --all` writes
`.factory/review-briefs/all.md` but mints no run identity, and the three lens
artifacts (`reviews/{quality,performance,security}.json`) carry no shared
binding, so `pr_ready` cannot tell whether they cohere. This task adds a
deterministic **review-run** binding and enforces it at closeout.

## Design (grilled — all three questions confirmed the recommended option)

- **review_run_id** = `sha256(brief_sha256 + branch_diff_digest)` — deterministic
  and self-verifying; no opaque id store.
- **branch_diff_digest** = digest of the committed **product** diff over
  `merge-base(origin/main)..HEAD` (excludes `.factory/` + `plans/`, like
  `product_tree_digest`); a new branch commit re-grounds it.
- **Coherence check** lives in a shared `factory_lib.require_coherent_review_run`
  helper — `pr_ready` calls it (and `load_review_artifacts` may reuse it); not
  inlined.

## Changes (write_scope only — 6 files)

1. **`factory/scripts/forge_cli/review_brief.py`** — `review-brief --all` also
   mints a review-run token at `.factory/stories/<KEY>/review-run.json` =
   `{review_run_id, brief_sha256, branch_diff_digest, minted_at}`.
2. **`factory/scripts/factory_lib.py`** — `branch_diff_digest(root)` (reuse
   `committed_paths` + the `WORKFLOW_PATHS` exclusion) and
   `require_coherent_review_run(root, reviews)` (all three lenses share one
   `review_run_id`/`brief_sha256`/`branch_diff_digest` **and**
   `branch_diff_digest == current`).
3. **`factory/scripts/record_review_from_json.py`** — each lens reads the current
   review-run token, refuses if its `branch_diff_digest != current`, and echoes
   `{review_run_id, brief_sha256, branch_diff_digest}` into the lens artifact.
4. **`factory/scripts/pr_ready.py`** — call `require_coherent_review_run`;
   refuse an incoherent or stale lens set.
5. **`factory/schemas/review.json`** — allow `review_run_id`, `brief_sha256`,
   `branch_diff_digest`.
6. **`factory/tests/test_gates.py`** — the two required tests below.

## Non-goals / guardrails

- One shared coherence seam; **no inline duplicate** in pr_ready (the drift class
  already flagged in tasks 1/3/4).
- `branch_diff_digest` covers product only — evidence/doc churn must not
  invalidate a valid review.
- Do not touch the task-4 stage-local stamp.
- Touch only the 6 write_scope files.

## Reuse (already on the branch)

`committed_paths` + `WORKFLOW_PATHS` (`forge_cli/stages.py`),
`product_tree_digest` (`factory_lib.py`), `cmd_review_brief`
(`forge_cli/review_brief.py`), `load_review_artifacts` (`factory_lib.py`),
`sha256_of` / brief SHA (`forge_cli/delegate.py`).

## Verification

- `test_review_brief_mints_run_id_and_lenses_echo_it` — `review-brief --all`
  writes a review-run token; recording each lens echoes the same
  `review_run_id`/`brief_sha256`/`branch_diff_digest`; a lens recorded against a
  stale token is refused.
- `test_pr_ready_refuses_incoherent_lens_set` — lenses with mismatched
  `review_run_id` (or a branch commit that moves `branch_diff_digest`) → pr_ready
  refuses; one coherent set matching current state → passes.
- `python3 factory/scripts/check_dual_runtime.py` clean; the review/pr_ready
  suite green.

## Bootstrap

ACC-3's own story closeout mints the review-run token and records the three
lenses under it (this gate applies to the closeout that ships ACC-3).
