# FORGE-ACC-3 · Task 7 — hygiene-content-pins-and-doc-debts

## Context

`check_encoding_hygiene.py` pins its 73 allowlisted call sites by `path:line`,
so any inserted line above a pinned site shifts it and CI's scaffold-check goes
red — signal S-0001 already reported 16 stale pins from tasks 3–6, and the CFS-1
CI-fix pins have the same fragility. Separately, several docs drifted from the
implemented contract: `griller.md` never shows the recorded task-grill payload
shape, the accountable-engineering-loop spec says "zero rounds is not a valid
pass" (contradicting the recorder's per-gap rounds-or-citation rule), and
WORKFLOW/FACTORY never declare the per-task plan artifact or the ordered
closeout chain. This task makes the pins insertion-proof and reconciles the
docs.

## Design (grilled — all three questions confirmed the recommended option)

- **Fingerprint** = `sha256(normalized construct line)` (strip leading/trailing
  whitespace; keep the code) + a 0-based **occurrence** index for identical
  lines; survives insertions/reindentation above, breaks when the construct
  itself changes.
- **Unresolvable pin fails closed** — a pin that matches nothing is a hygiene
  failure demanding re-review, never silently dropped.
- **Reconcile spec → recorder** — soften "zero rounds is not a valid pass" to
  the implemented rule: each GAP needs a rounds-entry or citation; a 0-gap grill
  with sanctioned resolutions is a valid pass (do not invalidate tasks 3–6
  grills).

## Changes (write_scope only — 6 files)

1. **`factory/scripts/check_encoding_hygiene.py`** — the four allowlists
   (`BYTE_PATH_ALLOWLIST`, `BYTE_MODE_ALLOWLIST`, `REPLACE_ALLOWLIST`,
   `STDIN_ALLOWLIST`) pin by `{path, fingerprint, occurrence}` resolved to lines
   at check time; unresolvable → fail. **One-time mechanical migration** of all
   73 current pins by reading each pinned line's text (repairs the S-0001
   breakage and the CFS-1 CI-fix pins).
2. **`factory/prompts/griller.md`** — add the exact recorded task-grill payload
   shape: `rounds` `{question, options (2–4 strings), chosen ∈ options}`,
   `citations` `{finding, source}`, gaps need a rounds-entry or citation.
3. **`docs/specs/accountable-engineering-loop.md`** — reconcile the zero-rounds
   wording to the per-gap rounds-or-citation rule.
4. **`WORKFLOW.md`** — declare the per-task plan artifact
   (`.factory/stories/<KEY>/task-plans/<id>.md`) and the ordered closeout chain.
5. **`docs/FACTORY.md`** — same declarations.
6. **`factory/tests/test_gates.py`** — the required test below.

## Non-goals / guardrails

- Migration is mechanical (regenerate pins from current text), not a re-audit of
  what's allowlisted.
- Do **not** touch `specs.py`/`quickfix.py` — D-0030 (story-spec resolver) and
  D-0031 (window-guard message) are separate lite fixes.
- Touch only the 6 write_scope files.

## Reuse (already on the branch)

The existing AST call-site detection in `check_encoding_hygiene.py`
(`check_file`, `_call_name`, `Finding`) — only the allowlist keying changes;
`record_grill_from_json.py` `_validate_task_grill` as the payload-shape source
of truth for the griller.md example.

## Verification

- `test_encoding_hygiene_content_pins_survive_insertion` — insert a blank line
  above a pinned site → scaffold-check stays green (fingerprint resolves to the
  moved line); mutate a pinned construct's text → its pin no longer resolves →
  check fails.
- `python3 factory/scripts/check_encoding_hygiene.py` green on the current tree
  (all 73 pins migrated and resolving); `python3
  factory/scripts/check_dual_runtime.py` clean.
