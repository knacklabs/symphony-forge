# Full access: Forge judges the result, not each write

## What and why

Forge tries to stop the coordinator from writing product files by reading every shell command and
guessing whether it writes. That guess can never be complete: every review found another way through,
each patch added code, and harmless commands got refused. The lock is about 1,100 lines and 60 tests,
needs its own outage mode, and still can't tell who wrote a change. We now let agents write freely and
judge the result instead: proof, a clean review and CI.

## What changes for you

- No more "write lock" refusals. Claude, Codex and their helpers can edit any file.
- `forge task close` still runs the proof and the review. Files a task changed outside its declared
  scope are shown to the reviewer and listed in the PR, instead of blocking the close. Changes to
  records, plans and decisions are listed too.
- Closing a task, or correcting its scope midway, no longer needs proof that a Codex run happened.
- Lite fixes are reviewed in full and still limited to five code files.
- Degraded mode and the old quickfix window disappear; they only existed to get around the lock.
- Still refused: raw `codex exec`, destructive commands like `rm -rf` or force-push, and
  phase-advancing scripts before sign-off. Still required: a ticket on every PR.

Not in this story: who writes by default (the executor setting) stays with the warm-threads story.

## Done when

- No Forge hook refuses a write because of the file it touches.
- A task with an out-of-scope file and no recorded Codex run closes when proof and review pass; the
  file shows in the review brief and in a Forge-owned block of the PR description, and re-running
  close updates only that block.
- A scope correction during a task records without a Codex run.
- Lite windows are reviewed in full and refused at `mode done` when over budget.
- Degraded and quickfix commands say they were removed; old records still count as history.
- The hook checks confirm edit tools are no longer sent to the hook; the Windows CI job passes.
- The lock code and its tests are deleted, and the docs describe the new rule in a sentence or two.

## Risks

- A careless out-of-scope edit is now caught by the reviewer, not by a refusal. That is the trade we
  chose; the review brief lists those files so they are not missed.
- Records under `.factory/` can be hand-edited; they are checked for consistency, not signed. This
  was already true under the lock.

## What I need from you

Nothing beyond approving this plan.

---

## Technical approach

- Hook: delete the write-guard parts of `factory/scripts/pre_tool_use.py` (Edit/Write/apply_patch
  gating, Bash write parsing, git allowlist, writer programs, sed, redirects, wrappers, cd opacity,
  static fallback lock, merge-recovery write policy, repo-kind and `.factory` write denial, native and
  Claude write admission, sibling-worktree re-rooting). Keep the ask gate, the destructive-command
  denylist, the raw `codex exec` / companion route ban, the check bypass, the sign-off gate and the
  commit belt with the tokenizer and git-subcommand helpers it uses.
- Helpers: remove `repo_kind.locked_repo_path`, write-time `quickfix.claim_files` and the repo-kind
  pin, write admission and revocation in `worker_admission.py` and `delegate.py`; keep what
  `stop_continue.py` and `delegate.py` still need (`path_in_scope`, the read-only grill check).
- Hook wiring: drop the Edit/Write/MultiEdit/NotebookEdit PreToolUse entry in `.claude/settings.json`
  and the `apply_patch` matcher in `.codex/hooks.json`; `check_dual_runtime.py` and doctor assert both
  coverage (Bash, AskUserQuestion; shell, request_user_input) and absence (edit tools, apply_patch);
  update the native write-launch readiness check in `delegate.py`.
- Close: remove `_require_successful_launch` and its degraded fallback. A separate stage-base diff
  (committed `<stage base>..HEAD` plus the working tree, all paths, no exclusions) is compared with the
  DECLARED write scope (not the amended effective scope) to list out-of-scope files and overlaps with
  other active tasks' scopes. The review brief carries that list plus the text diff of changed
  `plans/` and `docs/decisions/` files so Autoreview can judge their content; changed `.factory/`
  records are listed by name.
- PR body: `seal_task` updates a marked Forge block (`<!-- forge:scope -->`) both when creating the PR
  and when one already exists (read body, replace the block or append it, `gh pr edit`); an edit
  failure prints a warning and the retry command and does not fail the close.
- Amendments: `record_decomposition_from_json.py` binds a mid-stage amendment to the active stage
  incarnation instead of a launch id.
- Lite: `mode done` budget and the Lite review use the full committed diff since the window base (no
  product filtering, review tip keeps every changed path); budget counts all non-test, non-Markdown
  files.
- Degraded and quickfix: start/done commands print "removed"; old closed records still satisfy
  `check_pr_ticket`; board, signal and review references cleaned up. Guidance that points at removed
  routes is reworded to the Lite fix: `forge next` (phase.py quickfix and hook-blocked-write advice),
  `signal.py`'s degraded-guide pointer, and the scaffolded onboarding text. Clients' old copies of
  `docs/degraded-mode.md` are retired by FORGE-UPG-2's ownership rule (byte-equal copies removed,
  edited copies kept).
- Specs: `strict-role-split.md` gets `status: superseded`; the spec resolver accepts confirmed or
  superseded specs for EXISTING roadmap links (plan save, sign-off) and only confirmed specs for new
  links.
- Docs: amend `delegation-boundary.md`, `dual-coordinator-parity.md`, AGENTS.md, `.claude/CLAUDE.md`,
  WORKFLOW.md, `factory/skills/forge.md`, `docs/getting-started.md`, `docs/QUALITY.md`,
  `docs/FACTORY.md`, the parity architecture, product brief and `workflow-modes.md`; delete
  `docs/degraded-mode.md`; update the session-start message.
- Tests: delete ~60 guard-only tests. New `factory/tests/test_full_access.py`: any-file writes not
  refused; retained command gates still refuse (rm -rf, raw codex exec, unsigned phase advance);
  no-launch close with an out-of-scope file (brief list, overlap, records list, PR block); PR block
  re-run preserves human text and Ticket lines; stage-bound amendment; full Lite review and budget;
  removed degraded/quickfix commands and old records in the ticket check; hook registration presence
  and absence; superseded spec link rules. Windows job selectors: drop
  `test_lockout_denies_product_write_under_approved_plan` and
  `test_degraded_window_allows_and_ledgers_product_write`, reduce
  `test_registered_hook_path_keeps_recorder_and_lockout_armed` to its recorder half, add
  `test_full_access.py::test_retained_command_gates_still_refuse`.
- Tasks (the owner chose two): CODE delivers everything above except canon text, in one PR; DOCS
  follows with the canon and skill text and marks `strict-role-split.md` superseded.

## Task decomposition

CODE first, then DOCS. Each ships its own pull request.

| Label / exact task ID | What it delivers | Depends on | user_facing |
|---|---|---|---|
| Code / CODE | Write guard, write admission and revocation deleted; hook wiring and its checks (presence and absence); retained command gates kept; launch-free close with stray, overlap and records lists; PR block; stage-bound amendments; full Lite review and budget; degraded and quickfix removed; superseded-spec link rule; reworded guidance | none | false |
| Docs / DOCS | Canon, skill, brief and session-start wording; `docs/degraded-mode.md` deleted; `strict-role-split.md` superseded | CODE | false |

## Verify plan

Each task: focused tests in `factory/tests/test_full_access.py`, `forge task close` (full suite plus
one three-lens review), the CI-only checks, and green CI including the Windows hook job with its
updated selectors. The story is done when a real coordinator session edits product, canon and
`.factory` files without a refusal, a task with an out-of-scope file closes with that file listed in
its review brief and PR block, and destructive commands and raw `codex exec` are still refused.
