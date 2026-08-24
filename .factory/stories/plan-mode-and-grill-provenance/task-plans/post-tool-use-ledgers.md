# Task plan — post-tool-use-ledgers (story plan-mode-and-grill-provenance)

## Objective
Add a `post_tool_use` hook that records two kinds of per-story provenance:
plan-mode markers for plan-file writes and AskUserQuestion round records.
No recorder changes in this task; it only produces the evidence later
gates will check.

## State left by prior work
Hook dispatcher `factory/scripts/forge.py` `HOOK_SCRIPTS` knows four
scripts; `.claude/settings.json` wires SessionStart, PreCompact,
PreToolUse (Bash; Edit|Write|MultiEdit|NotebookEdit), Stop — no
PostToolUse. `pre_tool_use.py` reads `tool_name`, `tool_input`,
`permission_mode` from stdin JSON. Per-story evidence lives under
`.factory/stories/<key>/…` via `factory_lib.evidence_path`; payloads are
validated by `factory_lib.validate_payload(base, "<schema>", payload)`
against `factory/schemas/<schema>.json` (shallow, type-checked, extra keys
allowed). Decision 0022: one record per file (uuid4 names), as
`forge_cli/events.py:append_event` does. Decision 0038: hooks are
portable and fail closed for enforcement — but a *logging* hook must
never block a tool, so this script exits 0 on any parse/write failure.

## Steps (Codex, via delegate)
1. `factory/scripts/post_tool_use.py`: read stdin JSON (`tool_name`,
   `tool_input`, `tool_response`, `permission_mode`, `session_id`);
   resolve repo root like `pre_tool_use.py`; active story key from
   `run_state_path` (absent → root-level dirs `.factory/plan-mode/`,
   `.factory/grill-rounds/`).
   - Branch A: `tool_name in {"Write","Edit","MultiEdit"}` and
     `permission_mode == "plan"` → `file_path` from `tool_input`; read the
     file bytes *after* the write; record
     `{"path": <absolute>, "sha256": <hex of bytes>, "sha256_body": <hex
     excluding "## Implementation Assumptions" block via
     plan_digest_without_assumptions>, "at": now_iso(), "session_id",
     "generated_by": "claude-code:plan-mode"}` to
     `<scope>/plan-mode/<uuid>.json`. Missing file → exit 0, no record.
   - Branch B: `tool_name == "AskUserQuestion"` → record
     `{"questions": [{"question","options":[labels],"chosen": <answer or
     null>}], "at", "session_id", "generated_by": "claude-code:plan-mode"}`
     to `<scope>/grill-rounds/<uuid>.json`; `options` from
     `tool_input.questions[].options[].label`, `chosen` from
     `tool_response` if present (answers keyed by question text), else
     null. No free-text (`notes`) stored.
   - Anything else → exit 0 immediately. Validation via
     `validate_payload` with the two new schemas; a validation failure
     logs to stderr and exits 0 (never blocks).
2. `factory/schemas/plan-mode-marker.json` and
   `factory/schemas/grill-round.json` in the existing schema style
   (`artifact`, `phase`, `recorded_by`, `generated_by` allowlist,
   `required`, `optional`).
3. `factory/scripts/forge.py`: add `"post_tool_use": "post_tool_use.py"`.
4. `.claude/settings.json`: `PostToolUse` entry, matcher
   `Write|Edit|MultiEdit|AskUserQuestion`, command identical in shape to
   the PreToolUse ones (`sh -c '"$(git rev-parse --show-toplevel)/forge"
   hook post_tool_use' || exit 0` — exit 0, not 2: logging must not
   block). `.codex/hooks.json` untouched.
5. Tests in `factory/tests/test_gates.py` using `repo`, `intake`, and the
   `hook()` wrapper pattern (new `post_hook()` helper that pipes JSON to
   `forge hook post_tool_use`):
   - `test_post_tool_use_records_plan_mode_marker` — plan-mode Write to a
     temp plan file records one marker with the right sha256 and body
     sha; a normal-mode Write records nothing.
   - `test_post_tool_use_records_ask_user_question_round` — records
     questions/options/chosen; a payload without `tool_response` records
     chosen null.
   - `test_post_tool_use_is_fail_open` — garbage stdin and a missing
     file_path both exit 0 and write nothing.
   - `test_vendor_integrity_covers_post_tool_use` — regenerate manifest in
     a scaffold and assert the new script is hashed (reuse the existing
     integrity test helper).

## Write scope
`factory/scripts/post_tool_use.py`, `factory/scripts/forge.py`,
`factory/schemas/plan-mode-marker.json`, `factory/schemas/grill-round.json`,
`.claude/settings.json`, `factory/tests/test_gates.py`.

## Proof (required_tests)
Runner: `uvx --with pytest --with psutil python3 -m pytest {path}::{id} -q
-o junit_family=legacy --junitxml={report}` on
`factory/tests/test_gates.py` for the four test ids above.

## Verify commands
`python3 factory/scripts/verify.py`; `python3 factory/scripts/check_dual_runtime.py`.

## Reviewer focus
Fail-open is real (every error path exits 0 and writes nothing); no free
text from AskUserQuestion (`notes`) is persisted; marker digests use the
same body-exclusion as `plan_digest_without_assumptions`; records land
under the story scope via `evidence_path`, never a hand-built path.

## Task grill (1 round, 3 questions; frontier empty)
- PostToolUse exits 0 on failure, explicitly asymmetric to PreToolUse's exit 2.
- Marker keeps both `sha256` and `sha256_body`; the gate compares the body.
- Root-scope records (no active story) are committed like events.

## Live check (orchestrator, after stage done)
In this session: one AskUserQuestion and one plan-mode Write; confirm both
records exist under `.factory/stories/plan-mode-and-grill-provenance/`. If
`tool_response` is absent for AskUserQuestion, record the assumption
(`forge plan assume`) and proceed with question-text provenance.
