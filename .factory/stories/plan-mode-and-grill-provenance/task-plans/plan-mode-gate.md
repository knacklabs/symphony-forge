# Task plan — plan-mode-gate (story plan-mode-and-grill-provenance)

## Objective
Make `plan save`, `plan approve`, `task plan save` and `task approve` refuse
any plan file whose body digest was not recorded by a plan-mode write, so a
plan authored from normal mode can no longer be saved or approved.

## State left by prior work
Task 1 shipped `factory/scripts/post_tool_use.py`: for `Write`/`Edit`/
`MultiEdit` with `permission_mode == "plan"` it records
`<scope>/plan-mode/<uuid>.json` = `{generated_by, path (absolute), sha256
(raw), sha256_body (plan_digest_without_assumptions), at, session_id}`,
scope = `evidence_path(root, story, "plan-mode")` (root-level when no
story). An earlier delegation already landed `require_plan_mode_marker`
(factory_lib.py:1336) and its four call sites in `plans.cmd_save/approve`
and `tasks.cmd_plan_save/approve`, plus four tests — this round finishes
the contract: the story-then-root scope fallback and the frontmatter
exclusion found live on 2026-08-24.

## Live findings this round must fix
1. **Root-scope fallback missing:** the helper searches only
   `evidence_path(root, _active_story_key(root), "plan-mode")`; when a
   story is active the root scope is never consulted. Contract: story scope
   first, then root scope.
2. **Frontmatter restamp breaks the marker:** `plan save` rewrites
   `status:`/`saved:` in the plan frontmatter, so the approve-time check
   compares a digest the author could never have marked. The marker digest
   (in BOTH the hook and the gate) must exclude the leading `---` YAML
   frontmatter block as well as the `## Implementation Assumptions` block.
   Add a shared helper (e.g. `plan_body_digest`) used by
   `post_tool_use.py` (as `sha256_body`) and `require_plan_mode_marker`;
   existing markers recorded with the old digest may be re-minted by the
   author — no compatibility shim.

## Steps (Codex, via delegate)
1. `factory_lib.py`: `plan_body_digest(path)` = sha256 of the text after
   stripping one leading `---\n…\n---\n` frontmatter block (if present) and
   truncating at `\n## Implementation Assumptions`;
   `require_plan_mode_marker` compares `sha256_body` to it and scans the
   active story scope then the root scope; malformed markers skipped;
   refusal message unchanged.
2. `post_tool_use.py`: `sha256_body` uses `plan_body_digest`; raw `sha256`
   stays the raw bytes.
3. Tests (six required):
   - `test_plan_save_refuses_plan_without_plan_mode_marker`
   - `test_plan_save_and_approve_accept_plan_with_plan_mode_marker` —
     extended: after `plan save` restamps frontmatter, `plan approve` and a
     second `plan save` still pass with the ORIGINAL marker.
   - `test_task_plan_save_and_approve_require_plan_mode_marker`
   - `test_plan_mode_marker_matches_body_not_assumptions`
   - `test_plan_mode_marker_in_root_scope_counts_for_active_story` —
     marker recorded with no active story (root scope), then intake; save
     passes.
   - `test_plan_save_restamp_does_not_invalidate_marker` — explicit
     restamp regression test.
   Fixtures keep marking plans through the real hook (`record_grill`'s
   `plan_mode=True` path); no hand-written markers, no env bypass.

## Write scope
`factory/scripts/factory_lib.py`, `factory/scripts/forge_cli/plans.py`,
`factory/scripts/forge_cli/tasks.py`, `factory/scripts/post_tool_use.py`,
`factory/tests/test_gates.py`.

## Proof (required_tests)
`uvx --with pytest --with psutil python3 -m pytest {path}::{id} -q -o
junit_family=legacy --junitxml={report}` on `factory/tests/test_gates.py`
for the six ids above.

## Verify commands
`python3 factory/scripts/check_dual_runtime.py` (verify.py is the
story-level phase; it writes an event and is not a task proof).

## Reviewer focus
The digest exclusion is one shared helper used by both the hook and the
gate (no second implementation); markers are read through `evidence_path`
story-then-root, never a hand-built path; fixtures create markers only via
the real hook; the restamp test proves approve works after save without a
fresh plan-mode round.

## Task grill (2 rounds, 4 questions; frontier empty)
- Lookup order: active story scope, then root scope; digest-only.
- Every existing fixture marks its plan through the real hook; no env
  bypass of any kind.
- Root-scope fallback and its test added after review of the first
  delegation.
- Frontmatter exclusion and its test added after the live restamp failure
  (2026-08-24); the shared `plan_body_digest` helper is the fix, not a
  tolerance window.

## Risk
Changing `sha256_body` semantics orphans the two markers minted today with
the old digest — the orchestrator re-mints them in plan mode after this
task lands (one Edit each); acceptable because the gate is not yet
protecting any other story.
