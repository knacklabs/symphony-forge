# Branch-wide plan-contract review brief

For each contract, emit a verdict — implemented | partial | missing — with file:line evidence, recorded as contract_verdicts in the quality artifact. Then review the diff normally; the contract check does not replace the quality/performance/security lenses.

## Task plan-approval-binding

### Plan contracts

- **ACC3T1-C1**
  - Source: plans/active/FORGE-ACC-3-approval-and-closeout-integrity.md#task-decomposition
  - Statement: an edited approved plan is refused at re-record and stage start until re-approved
- **ACC3T1-C2**
  - Source: plans/active/FORGE-ACC-3-approval-and-closeout-integrity.md#task-decomposition
  - Statement: plan approve refuses without a fresh passing --gate plan grill bound to the plan digest

### Reviewer focus

The approval marker (plans.py cmd_approve) must bind approved_plan_sha256 = plan_digest_without_assumptions(body), NOT body_sha256 - appending an assumption keeps approval valid but editing the plan body invalidates it. record_decomposition_from_json.py AND stage start (stages.py) compare the LIVE plan's plan_digest_without_assumptions against the APPROVED marker's approved_plan_sha256 (not the record-time digest) and refuse on divergence with a re-approve message. cmd_approve requires a fresh passing --gate plan grill bound to the plan digest (mirror cmd_save require_grill). ALL plan/marker reads via evidence_path (ACC-3 is new-layout, story-scoped). Do NOT regress the story-plan save/approve flow (existing tests stay green). SCOPE: plans.py marker+approve grill, the shared approved-digest compare in factory_lib, the two refusal sites, tests only.

## Task task-plan-approval-gate

### Plan contracts

- **ACC3T2-C1**
  - Source: plans/active/FORGE-ACC-3-approval-and-closeout-integrity.md#task-decomposition
  - Statement: stage start and delegate refuse a task with no approved task plan whose digest matches, or a stale grill
- **ACC3T2-C2**
  - Source: plans/active/FORGE-ACC-3-approval-and-closeout-integrity.md#task-decomposition
  - Statement: forge next and the board route author-task-plan and await-approval identically from shared predicates

### Reviewer focus

Codex-validated minimal design. New forge_cli/tasks.py (cmd_plan_save, cmd_approve) + forge.py registration of `forge task plan save <id> --from <path>` and `forge task approve <id> --by "<name>"`. The per-task plan lives at .factory/stories/<KEY>/task-plans/<id>.md via evidence_path - NOT plans/active/, NOT the decomposition. Approval metadata stays OUT of the Markdown so stamping does not change its digest. forge task approve refuses unless the task grill exists, passes, and is fresh, then stamps approved_task_plan_sha256 = plan_digest_without_assumptions(plan), approved_by, approved_at into the grill record (schema grill.json must allow these 3). Extend require_ready_task(root, id, *, require_approval=True) right after require_task_grill: task-plan exists, grill fresh, approval fields present, stored digest == current plan digest; stage start and write delegate already call this shared seam (no new local logic); forge task approve calls it with require_approval=False. Do NOT add the task-plan digest to grounding_digest (grill precedes plan authoring -> would stale the just-passed grill). task_frontier_state derives (no new stored status): author-contract -> grill -> author-task-plan -> await-approval -> stage-start -> delegate; phase.py maps each to one [dev] action and task_rows uses the SAME predicates so the board cannot disagree. A re-grill (record_grill) replaces the record and clears prior approval. Audited human attestation per 0029 - no signing/OAuth/nonce/plan-mode-hook/daemon (over-building). SCOPE: the 7 write_scope files only.

## Task pre-draft-requirements-round

### Plan contracts

- **ACC3T3-C1**
  - Source: plans/active/FORGE-ACC-3-approval-and-closeout-integrity.md#task-decomposition
  - Statement: plan save refuses without a fresh requirements-round grill matching the spec+tree digest
- **ACC3T3-C2**
  - Source: plans/active/FORGE-ACC-3-approval-and-closeout-integrity.md#task-decomposition
  - Statement: forge next routes the requirements round as the first planning action

### Reviewer focus

Minimal design mirroring the existing plan/task grill gates - no new machinery. New 'requirements' grill gate: record_grill_from_json.py adds 'requirements' to --gate choices and SELF-DERIVES input_sha256 = requirements_digest(root, spec) exactly as --gate task self-derives grounding_digest (no --input-digest file). factory_lib.requirements_digest(root, spec_path) = sha256(spec_body_bytes + b'\x00' + product_tree_digest(root)); REUSE product_tree_digest (it already excludes .factory/ and plans/, so plan/evidence churn does not stale the grill) - do NOT write a second tree-walker. spec is the active story's confirmed spec resolved from plans/roadmap.json item['spec']; refuse if the story has no confirmed spec. Grill recorded story-scoped at .factory/stories/<KEY>/grills/requirements.json via evidence_path. plans.py cmd_save gains _require_matching_requirements_grill(base, spec, issue) called alongside _require_matching_plan_grill: refuse unless a fresh passing requirements grill exists whose input_sha256 == requirements_digest (re-derived at gate time, mirroring the plan-grill digest re-derivation). phase.py routes the requirements round as the FIRST planning action (before plan grill/draft), one [dev] action, derived purely from grill presence+freshness - NO new stored status, NO new run-state field. griller.md/AskUserQuestion rounds are the delivery convention, not code. Gate at plan SAVE only (not a separate approve gate). SCOPE: the 6 write_scope files only; do not touch tasks.py or the task-level gate.

## Task local-review-stamp

### Plan contracts

- **ACC3T4-C1**
  - Source: plans/active/FORGE-ACC-3-approval-and-closeout-integrity.md#task-decomposition
  - Statement: stage done refuses without a fresh stage-local stamp, or with uncommitted/staged product changes, or an empty committed delta
- **ACC3T4-C2**
  - Source: plans/active/FORGE-ACC-3-approval-and-closeout-integrity.md#task-decomposition
  - Statement: the stamp is a stages.json token and records no fourth review artifact

### Reviewer focus

Minimal design reusing existing stage machinery - no fourth review artifact (decision 0011). record_review_from_json.py gains --aspect stage-local: instead of writing reviews/<aspect>.json it writes a STAMP token into the ACTIVE stage's stages.json entry, requiring a clean review (reuse forge_cli.readiness.review_passed: no blocking_findings AND score>=MIN_SCORE) else refuse. The stamp binds {stage id, task_sha256 (task_digest of the frontier task), brief_sha256 (sha256_of the delegate brief at .factory/briefs/<id>.md via the latest launch record; bound-when-present so non-delegated work still stamps), base_sha baseline (stage_baseline), and the reviewed product-diff pin}. Realize the 'pre-commit product diff digest' by REUSING product_tree_digest (the deterministic index fingerprint excluding .factory/ and plans/) - reviewing then committing exactly that leaves it identical, so stamp==done proves you shipped what you reviewed; do NOT invent a bespoke diff-content digest. stage done (_finish_stage in stages.py) refuses unless: (a) a fresh stage-local stamp exists whose {stage id, task_sha256, base_sha, brief_sha256} match the stage and whose product_tree_digest == current, (b) no uncommitted/staged PRODUCT changes remain (reuse product_tree_snapshot/changed_paths), (c) the committed delta is non-empty (extend the existing empty-delta refusal). The stamp is a stages.json token ONLY: load_review_artifacts and closeout still read exactly the three lenses. Bootstrap: task 4 records its OWN stage-local stamp (dogfood) - no exemption. forge next routing for the local-review step is OUT of scope (task-frontier-and-closeout owns it). SCOPE: the 4 write_scope files only.

## Task coherent-branch-review

### Plan contracts

- **ACC3T5-C1**
  - Source: plans/active/FORGE-ACC-3-approval-and-closeout-integrity.md#task-decomposition
  - Statement: pr_ready refuses when the three lens artifacts do not share one review_run_id + brief sha + branch diff digest matching current state

### Reviewer focus

Minimal design; ONE shared coherence seam (no duplicated checks). review-brief --all (cmd_review_brief) additionally mints a review-run token at .factory/stories/<KEY>/review-run.json = {review_run_id, brief_sha256, branch_diff_digest, minted_at}. review_run_id is DETERMINISTIC = sha256(brief_sha256 + branch_diff_digest) (self-verifying; no opaque id store). factory_lib.branch_diff_digest(root) hashes the committed PRODUCT diff over merge-base(origin/main)..HEAD (reuse committed_paths + WORKFLOW_PATHS exclusion; excludes .factory/ and plans/), so a new branch commit re-grounds it. record_review (quality/performance/security) reads the current review-run token, refuses if its branch_diff_digest != current, and echoes {review_run_id, brief_sha256, branch_diff_digest} into each lens artifact (schema review.json allows the 3 fields). A shared factory_lib.require_coherent_review_run(root, reviews) checks all three lenses share one review_run_id + brief_sha256 + branch_diff_digest AND branch_diff_digest matches current state; pr_ready calls it (and load_review_artifacts may reuse it) - do NOT inline the check in pr_ready. Bootstrap: ACC-3's own story closeout mints the review-run and records the three lenses under it. SCOPE: the 6 write_scope files only; the stage-local stamp (task 4) is untouched.

## Task ordered-closeout

### Plan contracts

- **ACC3T6-C1**
  - Source: plans/active/FORGE-ACC-3-approval-and-closeout-integrity.md#task-decomposition
  - Statement: pr_ready refuses out-of-order closeout, a dirty product tree/index, or a missing outcome stamp on the evidence commit
- **ACC3T6-C2**
  - Source: plans/active/FORGE-ACC-3-approval-and-closeout-integrity.md#task-decomposition
  - Statement: quickfix/lite/degraded start refuse while any stage is active

### Reviewer focus

Minimal, pr_ready-centred design; ONE shared stages-done seam. New factory_lib.require_all_stages_done(root) (all decomposition stages status=done; returns the open-stage list) replaces the inline open_stages check in pr_ready and is reused by the window-refusal guard. Enforce the closeout ORDER at pr_ready, NOT via record-time recorder gates (record-time gates on record_review/verify would break the lite-window review path). pr_ready requires, in order: require_all_stages_done -> verify present+ok stamped at HEAD -> the three coherent lenses (task 5) stamped at HEAD (this realises 'verify before review': verify must be present+current before pr_ready accepts the branch review) -> functional at HEAD when user_facing -> outcome present with outcome.commit == HEAD (the outcome stamp on the evidence commit) -> a clean product worktree AND index (reuse product_tree_snapshot: no staged or unstaged product change) with the existing repo-kind-aware evidence exclusions preserved. A shared factory_lib.require_closeout_order(root) returns the ordered problem list; pr_ready calls it (no inline duplicate). phase.py closeout routing lists the steps in that order. Window refusal: the shared quickfix._open refuses to start any profile (quickfix/lite/degraded) while require_all_stages_done reports an active/open stage — uniformly, per spec; pause a stage with `stage done --incomplete` first if a window is truly needed. SCOPE: the 5 write_scope files only.

## Task hygiene-content-pins-and-doc-debts

### Plan contracts

- **ACC3T7-C1**
  - Source: plans/active/FORGE-ACC-3-approval-and-closeout-integrity.md#task-decomposition
  - Statement: adding a line above a pinned site leaves scaffold-check green (fingerprint pins survive insertions); existing pins migrate mechanically
- **ACC3T7-C2**
  - Source: plans/active/FORGE-ACC-3-approval-and-closeout-integrity.md#task-decomposition
  - Statement: griller.md payload example matches the recorder and the spec zero-rounds wording is reconciled

### Reviewer focus

Two parts: a mechanical hygiene-pin migration and doc-debt reconciliations. (1) check_encoding_hygiene.py allowlists (BYTE_PATH_ALLOWLIST, BYTE_MODE_ALLOWLIST, REPLACE_ALLOWLIST, STDIN_ALLOWLIST) stop pinning by 'path:line' and pin by {path, fingerprint, occurrence}: fingerprint = sha256 over the NORMALIZED construct line (strip leading/trailing whitespace; keep the code text so a changed construct correctly breaks its pin), occurrence = 0-based index among identical fingerprints in that file. At check time resolve each pin to its line(s) by scanning the file; an UNRESOLVABLE pin FAILS closed (the allowed construct moved or changed -> re-review), never silently drops. Do a ONE-TIME mechanical migration of ALL 73 existing pins (including the CFS-1 CI-fix line pins AND the accumulated tasks 3-6 shifts that made 16 stale) by reading each pinned line's current text and computing its fingerprint -> scaffold-check goes green and stays green under insertions. (2) Doc debts: griller.md gains the EXACT recorded task-grill payload shape (rounds entries {question, options (2-4 strings), chosen (one of options)}; citations {finding, source}; gaps need a rounds-entry-or-citation) so the doc matches record_grill_from_json.py; the accountable-engineering-loop spec's 'zero rounds is not a valid pass' wording is reconciled to the recorder's actual rounds-or-citation-per-gap rule (a 0-gap grill with resolutions is valid); WORKFLOW.md and docs/FACTORY.md declare the per-task plan artifact (.factory/stories/<KEY>/task-plans/<id>.md) and the ordered closeout chain. SCOPE: the 6 write_scope files only; do NOT touch specs.py/quickfix.py (D-0030/D-0031 are separate lite fixes).

## Task task-worktree-start

### Plan contracts

- **ACC3T8-C1**
  - Source: plans/active/FORGE-ACC-3-approval-and-closeout-integrity.md#task-decomposition
  - Statement: forge task start creates the task worktree/branch off fetched main and refuses if task N-1's marker is absent from main
- **ACC3T8-C2**
  - Source: plans/active/FORGE-ACC-3-approval-and-closeout-integrity.md#task-decomposition
  - Statement: stage start and delegate refuse from the wrong worktree/branch via require_task_worktree

### Reviewer focus

Implements decision 0047 forge task start. New forge_cli/tasks.py cmd_task_start(<id>) registered in forge.py as `forge task start <id>`: (1) git fetch origin main; resolve base_main_sha = the fetched origin/main SHA. (2) Predecessor-marker gate: the task's predecessor is the decomposition task immediately before <id> in recorded order; require its marker present in the fetched main tree via `git cat-file -e origin/main:<marker>` where marker = factory_lib.task_marker_path(key, pred_id) = .factory/stories/<KEY>/tasks/<PREDID>/pr-ready.json (NEW shared helper; task-pr-gate/task 9 WRITES this exact path). The FIRST task (no predecessor) skips the gate (bootstrap). (3) git worktree add <sibling ../<repo>-<KEY>-<TASKID>> -b feat/<KEY>-<TASKID> <base_main_sha>. (4) Hydrate the new worktree FROM THE CURRENT planning worktree (copy the approved story plan plans/active/<KEY>-*.md, the protected decomposition, this task's grill grills/tasks/<id>.json, and its task plan task-plans/<id>.md) and initialize that worktree's protected run/decomposition/stages authority (git_control_dir/run.json etc.). (5) Write the untracked run pointer (git_control_dir/run.json) with issue_key, task_id, branch, base_main_sha. Shared factory_lib.require_task_worktree(root): reads the run pointer and refuses unless the current branch == the pointer's branch AND task_id == the frontier task; stage start (stages.py) and write delegate (delegate.py) call it as a single seam. BOOTSTRAP: ACC-3 itself ships story-level and does NOT run forge task start; this builds it for the next story (0047). Idempotence/safety: refuse if the branch/worktree already exists; never touch origin. SCOPE: the 6 write_scope files only; keep the run-pointer additions backward-compatible (story-level runs omit task_id/branch).

## Task task-pr-gate

### Plan contracts

- **ACC3T9-C1**
  - Source: plans/active/FORGE-ACC-3-approval-and-closeout-integrity.md#task-decomposition
  - Statement: forge task pr-ready refuses an unsealed task (missing approval/stamp/clean-tree/committed-delta) and otherwise writes the task marker + opens the PR without flipping the roadmap
- **ACC3T9-C2**
  - Source: plans/active/FORGE-ACC-3-approval-and-closeout-integrity.md#task-decomposition
  - Statement: await-merge advances only when the task marker appears on refreshed origin/main, never on CI success alone

### Reviewer focus

Implements decision 0047 forge task pr-ready. FACTOR the reusable seal predicates OUT of pr_ready.py into a shared factory_lib.require_task_sealed(root, task_id) (do NOT clone pr_ready logic): fresh task grill + attributed task-plan approval (reuse require_ready_task), this task's stage status==done with a clean certified local-review stamp (reuse the task-4 stamp check) and a non-empty committed product delta, no open signal, no open window (quickfix/lite/degraded), no blocking assumption, and a clean product worktree/index (reuse product_tree_snapshot). Then refactor pr_ready.py to CALL the same factored predicates where they overlap (story closeout still adds its own verify/review/outcome chain). New forge_cli/tasks.py cmd_task_pr_ready(<id>) registered as `forge task pr-ready <id>`: run require_task_sealed; on pass write the marker task_marker_path(key, id) = .factory/stories/<KEY>/tasks/<TASKID>/pr-ready.json (validated recorder-style payload: task_id, branch, base_main_sha, commit==HEAD, sealed_at) then open the PR via `gh pr create` (gh is installed and authenticated in this environment). The marker is written FIRST (shipped truth) so it never depends on the PR call; if gh is unavailable/unauthenticated at run time, FAIL with a clear message directing `gh auth login` (never silently skip the PR). Tests stub a fake `gh` on PATH (recording its argv) to stay hermetic. It MUST NOT mark_status(), write outcome.json/shipped.json, or flip the roadmap. AC2 (await-merge advances only when the marker is on refreshed origin/main, never on CI success) is the marker-on-main truth task 8's start gate already reads; add a shared factory_lib.task_marker_on_main(root, key, id) helper (git fetch + cat-file) that task 8's gate and task 10's frontier reuse. BOOTSTRAP: ACC-3 ships story-level and does not run task pr-ready. SCOPE: the 5 write_scope files only.

## Task task-frontier-and-closeout

### Plan contracts

- **ACC3T10-C1**
  - Source: plans/active/FORGE-ACC-3-approval-and-closeout-integrity.md#task-decomposition
  - Statement: forge next and the board surface exactly one next per-task frontier state from shared predicates, never offering task N+1 until N's marker is on main
- **ACC3T10-C2**
  - Source: plans/active/FORGE-ACC-3-approval-and-closeout-integrity.md#task-decomposition
  - Statement: story pr_ready refuses until every task marker is on main; completed_stories recognizes .factory/stories/<KEY>/shipped.json

### Reviewer focus

CRITICAL backward-compat (task 8's lesson): the marker-aware behavior applies ONLY to task-level runs; a story-level run (like ACC-3 itself: run pointer has NO base_main_sha, no task_id) MUST keep the current stage-status-driven frontier and closeout unchanged. Gate every new behavior on `is_task_level = bool(run-pointer base_main_sha)`. (1) task_frontier_state: for task-level runs add an `await-merge` state after a task's stage is done until task_marker_on_main(root, key, id) is true (reuse task 9's helper), and select the earliest task whose marker is absent from main; for story-level runs, UNCHANGED (earliest stage!=done). (2) phase.py: route exactly one per-task frontier state incl. await-merge; task_rows uses the SAME predicates so the board cannot disagree; story-level routing unchanged. (3) pr_ready (story closeout): for task-level runs require EVERY decomposition task marker present on the closeout main base before verify+review+outcome+done-flip (an evidence-only story-closeout PR carries the flip); story-level closeout UNCHANGED (task 6 chain). (4) the CFS-1 completed-story recognition lives INLINE in factory/scripts/check_pr_ticket.py (a `.factory/history/<KEY>/` startswith check, ~line 171), NOT in factory_lib — make it ALSO recognize a `.factory/stories/<KEY>/shipped.json` added path (additive). Reuse task_marker_on_main, task_marker_path, git_control_dir. SCOPE: the 4 write_scope files only; a required test asserts the story-level frontier is unchanged when no task markers exist.

## Task roadmap-gate-task-markers

### Plan contracts

- **ACC3T11-C1**
  - Source: plans/active/FORGE-ACC-3-approval-and-closeout-integrity.md#task-decomposition
  - Statement: a task PR whose only completed work record is a validated task marker passes pr-ticket-check
- **ACC3T11-C2**
  - Source: plans/active/FORGE-ACC-3-approval-and-closeout-integrity.md#task-decomposition
  - Statement: story and quickfix declaration handling is unchanged

### Reviewer focus

Extends check_pr_ticket.py (the pr-ticket-check gate). Add completed_task_markers(root, added): an added path matching .factory/stories/<KEY>/tasks/<TASKID>/pr-ready.json whose JSON carries the required marker fields (task_id==<TASKID>, branch, base_main_sha, commit, sealed_at) yields the work record '<KEY>/<TASKID>'. Wire it into main() ADDITIVELY alongside completed_stories + completed_windows: a PR must declare EVERY completed record, and a task record is declared by a `Ticket: <KEY>/<TASKID>` body line OR inferred from a canonical task branch feat/<KEY>-<TASKID> (extend branch_ticket to yield <KEY>/<TASKID> when the branch names a decomposition task id and the diff adds that task's marker; the story-branch feat/<KEY>-<slug> inference stays). So a task PR whose only completed record is its validated marker passes. Story done-flip (history/shipped.json) and quickfix-window handling stay UNCHANGED (a required test asserts this). roadmap-gate.yml: change only if it must pass the head branch / not filter the marker path; otherwise leave it. Keep the CI-side check dependency-free (no schema import); validate marker fields by presence. SCOPE: the 3 write_scope files only.
