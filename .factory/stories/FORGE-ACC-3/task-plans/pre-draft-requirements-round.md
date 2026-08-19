# FORGE-ACC-3 · Task 3 — pre-draft-requirements-round

## Context

FORGE-ACC-3's spec (`docs/specs/accountable-engineering-loop.md`) and roadmap
AC #3 require that **before a story plan is drafted, the confirmed spec is
re-grilled against current repository state**, with rounds via AskUserQuestion,
and drafting is instructed only after that pass records. Today `plan save`
gates only on the `plan` grill (`_require_matching_plan_grill`); nothing forces
a fresh look at whether the confirmed spec still matches repo reality before
planning. This task adds that gate — a story-level **requirements grill** —
reusing the existing digest and self-deriving-grill machinery so it is a thin
mirror of the plan/task gates, not new infrastructure.

## Design (grilled — all three questions confirmed the recommended option)

- **Digest**: reuse `factory_lib.product_tree_digest` as-is (it already excludes
  `.factory/` and `plans/`, includes `docs/`). New
  `requirements_digest(root, spec_path)` =
  `sha256(spec_body_bytes + b"\x00" + product_tree_digest(root))`. No second
  tree-walker. A docs/spec/product change since the grill correctly stales it.
- **Spec**: the story's single confirmed spec from `plans/roadmap.json`
  `item["spec"]`; refuse when the story has no confirmed spec.
- **Bootstrap**: the gate applies to ACC-3 itself — a real ACC-3 requirements
  grill (via AskUserQuestion) runs before the task-7 plan re-save. No exemption
  code.

## Changes (write_scope only — 6 files)

1. **`factory/scripts/factory_lib.py`** — add `requirements_digest(root,
   spec_path)` (reusing `product_tree_digest`) and a small resolver for the
   active story's confirmed spec path from the roadmap item, refusing when none.
2. **`factory/scripts/record_grill_from_json.py`** — add `requirements` to the
   `--gate` choices; for that gate self-derive
   `payload["input_sha256"] = requirements_digest(root, spec)` exactly as
   `--gate task` self-derives `grounding_digest` (no `--input-digest` file).
   Store story-scoped at `.factory/stories/<KEY>/grills/requirements.json` via
   `evidence_path`.
3. **`factory/scripts/forge_cli/plans.py`** — add
   `_require_matching_requirements_grill(base, spec, issue)`, called in
   `cmd_save` alongside `_require_matching_plan_grill`: refuse unless a fresh
   passing requirements grill exists whose `input_sha256 == requirements_digest`
   (re-derived at gate time), mirroring the plan-grill freshness/mismatch
   messages.
4. **`factory/scripts/forge_cli/phase.py`** — route the requirements round as
   the FIRST planning `[dev]` action (before plan grill/draft), derived purely
   from grill presence + freshness. No new stored status, no new run-state field.
5. **`factory/schemas/grill.json`** — extend the `recorded_by` doc line to
   include `requirements`.
6. **`factory/tests/test_gates.py`** — the two required tests below.

## Non-goals / guardrails

- Gate at plan **save** only — no separate approve-time gate.
- No new stored status or run-state field; the round is derived.
- No bespoke digest excluding docs; reuse `product_tree_digest`.
- Touch only the 6 write_scope files; do **not** touch `tasks.py` or the
  task-level gate.

## Reuse (already on the branch)

`product_tree_digest`, `grounding_digest` and the `--gate task` self-derive
pattern (`record_grill_from_json.py`), `_require_matching_plan_grill` /
`cmd_save` (`plans.py`), `evidence_path` (`factory_lib.py`).

## Verification

- `test_plan_save_refuses_without_fresh_requirements_grill` — no requirements
  grill → `plan save` refuses; a fresh matching grill → passes; editing the
  spec (or the product tree) → digest mismatch → refuses again.
- `test_forge_next_routes_requirements_round_first` — a story with no
  requirements grill surfaces the requirements round as the first planning
  action in `forge next` / `phase.py`.
- `python3 factory/scripts/check_dual_runtime.py` clean; full plan/grill suite
  green.
