# FORGE-ACC-3 · Task 4 — local-review-stamp

## Context

FORGE-ACC-3's spec and roadmap AC #5 require that a stage cannot close until a
**clean local review** of the committed work is recorded, bound so it cannot be
recycled or dodged. Today `stage done` (`_finish_stage` in
`forge_cli/stages.py`) measures the diff and refuses an empty delta, but
requires no local review and does not force a fully-committed product tree — the
"autoreview before commit" step is a convention, not a gate. This task makes it
deterministic via a **stage-local stamp** in `stages.json`: a gate token (not a
fourth review artifact — decision 0011).

## Design (grilled — all three questions confirmed the recommended option)

- **Diff pin**: reuse `factory_lib.product_tree_digest` (deterministic index
  fingerprint, excludes `.factory/`+`plans/`) as the reviewed-diff binding.
  Review → stage all product changes → stamp → commit exactly that → `stage
  done` sees an identical `product_tree_digest`. `stamp == done` proves
  shipped==reviewed. No bespoke diff-content digest.
- **Brief binding**: bind `brief_sha256` (`sha256_of` the delegate brief at
  `.factory/briefs/<id>.md`, from the latest launch record) **when present**;
  a non-delegated stage still stamps binding stage id + `task_sha256` +
  baseline + tree digest. No carve-out.
- **Bootstrap**: task 4 records its **own** stage-local stamp (dogfood); no
  exemption code.

## Changes (write_scope only — 4 files)

1. **`factory/scripts/record_review_from_json.py`** — add `--aspect
   stage-local`: instead of writing `reviews/<aspect>.json`, require a clean
   review (reuse `forge_cli.readiness.review_passed`: no `blocking_findings`
   AND `score >= MIN_SCORE`) and write a **stamp token** into the active
   stage's `stages.json` entry, binding `{stage id, task_sha256, brief_sha256
   (when present), base_sha, product_tree_digest}`.
2. **`factory/scripts/forge_cli/stages.py`** — in `_finish_stage`, refuse
   unless: (a) a fresh stage-local stamp exists whose `{stage id, task_sha256,
   base_sha, brief_sha256}` match the stage and whose `product_tree_digest ==`
   current; (b) no uncommitted/staged **product** changes remain (reuse
   `product_tree_snapshot` / `changed_paths`); (c) the committed delta is
   non-empty (extend the existing empty-delta refusal).
3. **`factory/scripts/factory_lib.py`** — a shared derivation of the stamp
   bindings (the single seam the recorder writes and `stage done` re-derives).
4. **`factory/tests/test_gates.py`** — the two required tests below.

## Non-goals / guardrails

- **No fourth review artifact** (0011): `load_review_artifacts` and closeout
  still read exactly `quality`/`performance`/`security`. The stamp lives only in
  `stages.json`.
- `forge next` routing for the local-review step is **out of scope** —
  `task-frontier-and-closeout` (task 10) owns it.
- No bespoke diff-content digest; reuse `product_tree_digest`.
- Touch only the 4 write_scope files.

## Reuse (already on the branch)

`product_tree_digest`, `product_tree_snapshot`, `changed_paths`,
`stage_baseline`, `task_digest` (`factory_lib` / `stages.py`); `review_passed`
(`forge_cli/readiness.py`); the persisted brief + `brief_sha256`
(`forge_cli/delegate.py`, `.factory/briefs/<id>.md`).

## Verification

- `test_stage_done_refuses_without_fresh_stage_local_stamp` — no stamp → refuse;
  a stamp then an uncommitted/staged product change → refuse; a stamp with an
  empty committed delta → refuse; clean stamp + fully-committed non-empty delta
  → pass.
- `test_stage_local_stamp_is_a_stages_token_not_a_fourth_review` — recording a
  `stage-local` stamp writes into `stages.json` and creates no
  `reviews/stage-local.json`; `load_review_artifacts` still sees only the three
  lenses.
- `python3 factory/scripts/check_dual_runtime.py` clean; full stage suite green.
