# Read-only exploration for story plan-mode-and-grill-provenance

Target worktree: /Users/dev/Workdir/symphony-forge-provenance (branch
feat/plan-mode-and-grill-provenance, from origin/main). Read there. Do not
write anything.

Goal of the story: make two advisory disciplines into recorder-enforced gates:
(1) story plans and task plans must have been authored in Claude Code plan mode;
(2) spec/requirements/plan/task grills must have been conducted through
AskUserQuestion rounds until the frontier was empty, not self-reported.
Also: refuse a task grill recorded before its task plan exists, and make
`forge next` print the enforced order.

Report, with file:line citations (<= 150 lines):

A. Hook wiring today. Read .claude/settings.json and .codex/hooks.json (or
   equivalent): which events are wired (SessionStart, PreToolUse,
   PostToolUse, Stop, PreCompact?), to which scripts, with what matchers.
   What JSON does factory/scripts/pre_tool_use.py receive and parse
   (tool_name, tool_input, permission_mode, session_id, cwd?) — quote the
   fields it reads. Is there any PostToolUse script already? Any existing
   per-story ledger under .factory/stories/<key>/ that a new marker/ledger
   could join (naming, schema validation via factory_lib.validate_payload,
   one-record-per-file per decision 0022)?
B. Plan save path: factory/scripts/forge_cli/plans.py — how `plan save
   --from` reads the file, computes digests (plan_digest_without_assumptions
   etc.), binds to the plan grill, and what `plan approve` checks. Same for
   task plans: factory/scripts/forge_cli/tasks.py (task plan save/approve)
   and stages.py stage start preconditions (task grill, task plan, required
   tests). Identify the exact functions where a "plan-mode marker" check
   would slot in.
C. Grill recorder: factory/scripts/record_grill_from_json.py — per gate,
   which fields are required, how `rounds` are validated (question/options/
   chosen), how digests bind (input_sha256, requirements_digest,
   task contract digest), staleness checks in phase.py. Identify where a
   "rounds must match a logged AskUserQuestion ledger" check and a
   "minimum rounds / frontier_empty attestation" check would slot in, and
   where the task-grill-before-task-plan ordering is (not) enforced.
D. Phase engine: factory/scripts/forge_cli/phase.py — where the planning and
   implementing NEXT lines are produced (the "MANDATORY: enter plan mode"
   text), so the enforced order can be printed.
E. Claude Code facts to verify from installed docs/plugins if present on
   disk (search ~/.claude for hook documentation or examples; do not guess):
   does PostToolUse fire for ExitPlanMode and AskUserQuestion; what does
   the hook input contain for those tools (tool_input.plan? the answers?);
   is permission_mode present in PreToolUse/PostToolUse input. If you cannot
   verify, say so explicitly.
F. Gate tests: factory/tests/test_gates.py — how existing hook/recorder
   tests invoke pre_tool_use.py (stdin JSON shape), fixtures for stories,
   and the pattern for testing a refusal. Name the helpers to reuse.
G. Vendoring: how new scripts/hook entries reach client repos (forge
   upgrade manifest, harness-owned set, VENDOR_MANIFEST.json, check_vendor_
   integrity) — what must be added so a new PostToolUse script is vendored
   and integrity-checked.
H. Anything in active decisions or docs/specs/accountable-engineering-loop.md
   and docs/specs/plan-approval.md that constrains or already partially
   specifies this (quote it).
Return raw findings; no recommendations section needed beyond "slot-in
points".
