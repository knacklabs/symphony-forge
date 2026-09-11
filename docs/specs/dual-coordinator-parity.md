---
slug: dual-coordinator-parity
title: Either Claude or Codex can coordinate the same Forge workflow
status: confirmed
saved: 2026-09-10T08:26:21+00:00
---

# Either Claude or Codex can coordinate the same Forge workflow

This revision retains the coordinator contract and acceptance coverage while
applying accepted Decision 0064. Its managed frontmatter and confirmation
records determine approval status. Specification text supplies neither an
implementation claim nor a task marker or proof artifact.

## What changed in this revision

Compared with the confirmed 824baed4 revision of the source specification,
this draft applies accepted 0064: one current task brief, risk-based coherent
task boundaries, carried standing authorization, one combined lossless review,
and durable event/client retention. It removes only repeated ceremony and the
obsolete fixed 120000/180000-byte clauses. It also carries the ten audited
client failures into explicit owner obligations. The prior confirmed revision
and its comparison remain recoverable through the existing Git artifact and
approval records; this revision does not replace those records.

## Why

Developers must be able to use Claude Code with its existing Codex
rescue/companion route or native Codex CLI/Desktop as the Forge interface.
Changing the coordinator must not change the phase engine, human approvals,
worker policy, protected authority, tests, review, evidence, or shipping gates.
Native preparation exposed missing human-answer provenance, runtime
registration, setup ownership, worker admission, and task-proof paths. Prepared
native bytes retain their source and review provenance. An approved support
task reviews and delivers them completely, but they are never credited as that
worker's new contribution.

Decision 0064 makes one current task brief the working contract. Main retains
project/story intent, dependency graph, scheduling, and required human
decisions. Each task owner takes its own worktree through JIT planning,
delegated implementation, tests, verification, review, PR, and green CI.
Existing approval, admission, proof, and trunk-marker records remain the
authority. Repeated story/task grills, approval ceremonies, and separate review
launches are removed only when they duplicate the same current binding. A
material new choice, changed intent or scope, missing authority, or
contradiction still stops dependent work for the developer.

The installed autoreview helper has an observed 512000-byte prompt capacity
and lossless chunking. This is tool capacity, not a new Forge policy. The old
120000-byte product and 180000-byte review limits are removed from this
contract. Boundaries follow coherent behavior, ownership, changed file/line
risk, and actual complete review capacity. In the roadmap and 0058, "existing
review limits" means the installed helper's enforced safeguards and complete
lossless coverage, as amended by 0064; 512000 is an observation, not a pinned
replacement limit. Do not edit or override helper capacity to admit a task.
Remeasure the entire final input, use supported chunks, and split the task if
complete input cannot fit the helper's actual safeguards. No input may be
truncated, omitted, or declared clean without all three assessments.

## Behaviour

### One contract and shared authority

Main owns confirmed intent, story planning, the frozen decomposition,
dependency scheduling, story decisions, and the human conversation. Each task
owns one current brief containing behavior, boundaries, owner, tests, review
focus, relevant decisions, and settled rulings. Derive execution and review
inputs from that brief and existing digest-bound plan, approval, and proof
records. Do not add another plan, approval ledger, review registry,
coordinator registry, or protected-ruling database.

Standing authorization covers unchanged in-scope work, technical corrections,
and retries. Bind concrete revisions through existing commands and recorders.
When a decision is needed, present the changed artifact with one concise
recommendation, tradeoff, and consequence. Silence, continuation, workflow
status, mode change, or technical pass is not approval. Dependent work waits
for required answers; independent ready work continues. Carry settled rulings
through the existing task brief/contract and recorder family into every fresh
worker and reviewer.

Both adapters use the same Forge phases and protected state. Coordinator
product/canon writes remain locked. Planning/docs, recorder-mediated evidence,
prototypes, and normal Git operations retain their existing exceptions. A
delegated worker writes only when registered admission, stage, brief, task
digest, process identity, and derived scope match. Environment claims, copied
workspace state, and role names cannot grant authority.

Decision 0062 defaults read-only exploration and routine implementation to
Luna/max, validation/debugging to Sol/xhigh, and cold-read grilling to
Terra/xhigh. Other specialist settings retain their authority. Optional
explorer/validator presets are read-only and get resolved settings at dispatch;
they do not restore retired writer definitions. Forge remains the launcher;
direct native writer or certifying-griller transport is deferred.

### Human interaction and exact question identity

Required decisions and approvals use the host's permitted interface. In Codex
Default, main asks required questions and approvals in ordinary chat; the
synchronous request-user-input tool is optional and host-permitted. Claude
keeps AskUserQuestion. No manual Plan-mode switch, asynchronous approval
tool, private host patch, or repeated “continue” is required. Optional
unanswered questions do not stop work supported by existing facts.

For each structured round actually used, preserve runtime, session, tool-call,
question, answer, story, and event identity. Native certification reads the
completed PostToolUse payload: questions from tool_input.questions and the
answer from tool_response.answers[question_id].answers. The raw request
notification, serverRequest/resolved event, cancellation, error, cleanup
acknowledgment, empty result, or multiple answers cannot certify a round. One
nonempty non-whitespace offered-option or free-text answer is valid; retain its
exact submitted text, without coercing it to an option label. A free-text
answer is not approval. Replay, mismatch, wrong story, malformed payload,
cancellation, and missing event refuse. Question age adds no expiry.

After LEAN-WORKFLOW ships, each approval-bound artifact records
`design_review: required|routine` in its existing frontmatter. Missing or unknown values
mean required. Main records required for permissions, security boundaries,
destructive operations, data migration, substantial architecture changes, or
material changes to those designs. Routine requires an explicit rationale that
none of those triggers applies; workers cannot downgrade the bound choice.
Both adapters use the same phase-engine predicate. Classification and its
rationale are authored, digest-bound content, never excluded managed metadata.
The following existing inputs own the classification and proof binding:

| Gate | Classification input | Existing record and binding |
|---|---|---|
| spec | Selected capability Markdown | Global grills/spec.json; exact spec SHA256. |
| requirements | Story-linked confirmed capability | Story grills/requirements.json; requirements_digest(spec, product tree). |
| epics | All capability specs referenced by the proposed roadmap; any required/missing classification requires review | Global grills/epics.json; exact proposed roadmap SHA256 plus cited spec digests. No new JSON classification authority. |
| signoff | Product BRIEF and participating capability specs; any required/missing classification requires review | Global grills/signoff.json; existing commit/guarded-input freshness plus SHA256 of the complete Gate.locate handover text. |
| plan | Story-plan Markdown | Story grills/plan.json; existing authored plan digest. |
| task | Current task-plan Markdown | Story grills/tasks/<id>.json; task-plan digest plus existing protected-contract/product grounding digest. |

Use the existing evidence_path layout, Gate.locate readers and recorder digest
functions; the table adds no registry. A shared read must explicitly name every
gate, include each complete located input and grounding, and return a separate
assessed verdict/frontier for each. Each existing record retains its own exact
input binding, with the actual launch and inspected paths/digests in its
existing summary/inspected_refs. Missing inputs, unassessed gates or a changed
binding refuse. Reading common context never certifies another gate. The
current one-gate launcher grants no shared-read capability; LEAN-WORKFLOW must
implement and test this behavior before it is usable. Routine work skips
duplicate cold reads, not authorization, admission, tests, review or CI. No new
risk ledger is introduced. First retains current prerequisites until Lean ships.
The six existing grill types retain freshness, finding resolution, artifact/grounding digest,
and explicit empty-frontier checks. Top-level frontier_empty: true is canonical
for empty or populated rounds. An existing round-bearing payload may retain
final-round frontier_empty: true when the top-level field is absent; explicit
top-level false refuses. Empty rounds without canonical true refuse. Structured
rounds are eligible and single-use. There is no compulsory human round and no
invented answer.

For a first approval-bound artifact or material revision, save the exact draft,
identify the last confirmed revision, preserve its artifact/commit/body digest
through the existing scratchpad and committed event, show the full artifact
and comparison, and display it in main chat or a supported fallback. A
queued/stale/failed/wrong reader is not presentation. Ask explicit approval
only after display through the existing host interface; a grill or technical
pass is not approval. Ambiguous, refused, canceled, or missing answers remain
awaiting approval. Unchanged standing authorization and in-scope technical
corrections update the brief and existing binding without repeated ceremony.
Material choice, intent/scope, authority, or contradiction repeats the current
applicable design-scrutiny and approval path. The first 0063 native task keeps current
source/target gates until LEAN-WORKFLOW ships.

### Workspaces, first native task, and worker lifecycle

Under 0059, create or safely attach a dependency-ready task worktree at
refreshed trunk before that task's detailed plan or grill. Require the approved
story, its matching decomposition, exact story/task identity, fetched trunk
commit and all effective dependency markers on that trunk. An open PR, green
CI or worker message does not satisfy a dependency. Preserve the approved IDs,
order and dependency graph. A valid attachment
is clean, unowned, registered, and in the same Git common directory; validate
before hydration and publish ownership last. A verified retry returns the
existing owner without resetting it or creating a duplicate. Creation grants
no product write authority. Omitted/empty dependencies follow the immediate
predecessor; an explicit list names dependencies. Concurrent tasks require
distinct worktrees and disjoint protected scopes. A task enriches only its
permitted fields. Missing/conflicting owner state refuses without overwrite.
After trunk integration, refresh non-owner rows from incorporated trunk while
retaining the owner's contract, approvals, and stage baseline.

The first native foreground support task is the only 0063 exception. In the
planning checkout it needs a complete source contract, independent grill, and
actual approval before the existing task-start command creates its worktree.
In that target, freshly ground behavior, scope, tests, and dependencies are
written, grilled, and approved before stage start or native delegation. A
placeholder/incomplete source contract refuses; source-bound proof cannot
satisfy target proof. The first task repairs successor workspace creation
ordering. Later tasks use the normal 0059 workspace-first route. A
forge stage start --trunk route is not an alternative.

Accepted 0058 permits explicitly scoped native bootstrap support tasks to use
the validated isolated candidate. Validate exact scope, target preparation,
baseline, predecessor markers, and review boundaries before implementation.
Preserve sequential merges and normal task PR gates. Original prepared bytes
retain source, commit, and review provenance but do not count as the worker's
delegated contribution. Native write-hook activation and legitimate worker
admission land together. A preparation patch, draft graph, temporary path, or
diagnostic receipt never authorizes writes or proves release. Versioned
`plans/exploration/coordinator-parity-preparation/lean-delivery-graph.json`
assigns every original path/hunk to its complete-review owner and names the
exact reproducible preparation artifacts. The approved story plan binds its
SHA256 before any support-task contract is recorded. The committed
`native-foreground-preparation-inventory.json` in that directory binds the
first allocation to trunk 824baed4, its 109953-byte patch SHA256
bee122bb370177ededefb5fe81a82f8c600f69af8502e151956ec7b8afed29e2
and all 16 prepared file hashes. Revalidate against fetched trunk in the actual
target; local paths and source approvals do not replace target proof.

Forge is the sole launcher. An admitted worker binds launch ID, live process
identity, target worktree, stage incarnation, task contract, brief, and
derived write scope in protected Git-control state. It starts unadmitted;
registration must complete before writes. Registration/startup/process
discovery failure grants no authority. Failure before process creation records
failure without invented PID or exit code; verified cleanup precedes terminal
publication once a process exists. Cancellation revokes before cleanup, failed
cleanup leaves revocation, and completion/failure/stage closure revokes too.
Resume requires fresh preflight and launch; session identity/history never
revives authority. Companion workers still pass admission with native hooks.
Retain existing POSIX signal-mask restoration and Windows process guards.

Both routes expose the same start/running/terminal lifecycle, status, recovery,
logs, proof, and scope checks. Background success requires protected
registration; detached readers remain observable/cancelable. Read-only work
cannot satisfy a write launch. Startup, resume, clear, compaction, question,
and Stop interception use installed registrations; removing one fails
validation. CLI evidence does not certify Desktop.

Protected Git-local stage settings must be genuinely readable by the admitted
worker through an existing protected seam. A writable mirror, copied token,
environment claim, or instruction to skip lifecycle/recorders is not a fix.
A host brief snapshot is informational and cannot replace protected admission
or closeout; reproduce and test the actual denial/read path before claiming
repair.

### Setup, ownership, upgrade, and retired presets

Setup precedence is explicit --coordinator, FORGE_COORDINATOR, unambiguous
detection, then TTY choice. Empty/canceled/EOF/invalid/ambiguous/unattended
no-choice refuses before install and prints both commands. CODEX_THREAD_ID or
CODEX_SHELL detects Codex; CLAUDECODE detects Claude; both is ambiguous. Pass
the choice to both doctors without persisting it. POSIX stays ./setup; Windows
keeps forge.cmd and user-scope behavior. Codex setup does not start Claude.

Fresh, adopted, and upgraded clients receive both adapters; inert .claude is
not a runtime dependency. Existing COPY_CODEX, GATE_FILES, ownership,
conflict, replacement, and vendor-integrity rules remain authoritative.
Preserve client settings, skills, agents, CI, local configuration, history,
hotfixes, and dirty state. Refuse unsafe targets, report conflicts, and never
silently delete client files.

Remove only unchanged harness-owned copies of planner-high, docs-decomposer,
and functional-checker definitions plus obsolete delivery/scaffold-check
requirements. Preserve logical phase roles, prompts, producer identities,
model policy, and gates. Preserve modified, client-owned, or unverifiable
copies and report a user decision; never delete by filename alone. New
deliveries omit retired definitions. Optional read-only presets do not
recreate them or become native writer authority.

### Review, quality, dogfood, and delivery

Every task keeps deterministic verification, implementer-owned tests,
conditional functional proof, independent review, PR, and green CI. Main
launches one `forge review <task-id>` operation under accepted 0011/0064; the
implementer cannot self-certify and nested reviewers are prohibited. On
findings, main delegates fixes and repeats review until every assessment is
clean. Proposed 0049 is not authorization for changing review execution. The first
native task uses the current three-lens execution. After LEAN-WORKFLOW ships,
one combined review has explicit quality, performance, and security
assessments bound to the same diff/input and uses the installed lossless chunk
helper. Every chunk must finish. Include formatting/AST/comments/directives,
tests, generated semantic output, and exceptions in the review. Mechanical
formatting and semantic repairs may be separate coherent tasks where risk
requires. No truncation, blanket suppression, artificial clean result, cap
override, or unassessed lens pass is permitted. Use coherent capability and
file/line risk bounds instead of obsolete byte splitting.

The review-only parity checkpoint may create/reuse a Git-only draft PR after
normal contribution, verification, and independent review. Its body names
every missing required platform result and accepted unobserved platform limitation. It stays unmerged and receives no Forge task-ready
marker while required platform proof is incomplete. It is not forge task pr-ready and
does not bypass guard, admission, review, or protected state. After complete
proof, the same task repeats readiness/review as needed, seals normally, and
reaches refreshed trunk before closeout. No duplicate PR, marker, proof, or
fabricated readiness is allowed. Use normal Git push and gh PR lookup/create
--draft/checks operations, not forge task pr-ready, for this checkpoint. Before
reuse or creation, match the verified origin repository, head repository and
branch, base branch, and exact reviewed head commit. Query existing PRs with
that repository/head/base; an uncertain, failed or ambiguous lookup stops
creation. If creation returns an uncertain result, query again before any
retry; never create blindly. Preserve the existing PR identity in the current
scratchpad/report and reuse it after required platform proof is complete. Normal readiness
creates the eventual task marker once and retries preserve its identity and
timestamp. These requirements belong to Shared's PR retry path and Integration's
actual checkpoint; no new PR registry or marker substitute is introduced.

The platform evidence contract follows accepted 0065-ci-platform-evidence,
which amends 0064's six-live-cell requirement. Require actual local macOS
native CLI and Desktop proof plus Ubuntu 24.04 LTS x64 and native Windows CI.
Keep the six existing labels for platform coverage accounting. Each row says
whether its evidence is live runtime, CI regression/package smoke, or
unobserved; a passed CI row never claims an authenticated live runtime or
Desktop interaction. WSL cannot satisfy native Windows.

The required rows are native-cli-macos and native-desktop-macos with actual
local proof, native-cli-linux-ubuntu-24.04-x64 with Ubuntu CI proof, and
native-cli-windows with native Windows CI proof. CI preserves the full Ubuntu
harness suite and existing native Windows gates, and exercises native
launcher/admission, hooks, recovery and portable-delivery regressions on the
actual runner OS. Install the real Codex CLI package at an explicit reviewed
version and record its version/help smoke outcome. An authenticated native
task uses only existing authorized CI authentication when available; otherwise
state that live-task behavior is unobserved. Package/help smoke certifies only
package/argument-parser startup. Fixture normalization remains regression
proof. Required CI commands must succeed and collect meaningful tests; empty
or wholly skipped selections cannot pass.

Retain native-desktop-linux-ubuntu-24.04-x64 and native-desktop-windows as
unobserved when no genuine Desktop host is available. Their absence, and
unavailable authenticated CLI observations beyond required CI coverage, are
accepted limitations under 0065 and do not block this delivery. Record those
limitations explicitly; never mark an unrun Desktop observation passed or
infer it from CLI/CI. Any actually observed correctness/security failure,
including in a normally unobserved path, still blocks readiness.

Each row records actual OS/CPU, tested revision, runtime/build where installed,
evidence kind, commands/interactions and durable logs. Live Mac observations
identify trusted hook registrations, startup/resume/clear/compact, denied
coordinator writes, admitted work and truthful terminal outcomes. Include
completed question/event identity and mapping when an optional structured
interaction is supported and actually used; otherwise use the permitted
main-chat route and state the unavailable optional mechanism. Missing required
behavior or an observed failure blocks; optional interactions are not invented.

The final integration implementer authors the existing
factory/schemas/test-automated.json payload with generated_by: implementer;
record_test_from_json.py --kind automated writes
.factory/stories/FORGE-COORD-1/tasks/FORGE-COORD-1.1/tests.json. Use only the
existing fields status, summary, commands_run, pass_fail_summary,
remaining_gaps and blocking_findings. pass_fail_summary contains each existing
label exactly once: native-cli-macos, native-desktop-macos,
native-cli-linux-ubuntu-24.04-x64,
native-desktop-linux-ubuntu-24.04-x64, native-cli-windows and
native-desktop-windows. Each row states passed/failed/unobserved and its
explicit evidence kind and references. Actual commands/interactions go in
commands_run. Every failure and unobserved limitation appears in remaining_gaps.
Actual failures and missing required evidence also appear in blocking_findings.
The accepted unavailable Desktop/live-CLI observations remain limitations
without becoming blockers merely because they were not observed. State the
CI-backed coverage limitation in summary. Aggregate status and required
verification pass only when the four required rows, other task checks and
required client proof pass and no actual blocker remains. C10 propagates that
result to local, committed-CI, board and seal checks. Independent review checks
required results and limitations against actual logs. Evidence kind is text
in existing fields, not a schema property, new report or second authority.

Main creates a separate fresh Task tracker client under /tmp with private
origin, meaningful CI, and normal confirmed-spec/story/task lifecycle. It is
a dogfood consumer, not harness-task contribution. Its UI task is user_facing
true and must show real functional proof. Its admitted worker contributes real
code, tests, verification, review, functional evidence, PR, and green CI.
Forge parity integration is user_facing false under the current per-task
definition but still needs the required platform results and lifecycle proof. Record exact
client repository, commits, PR, and logs in the existing report; missing
client proof blocks the claim.

Accepted 0055/0056 quality rollout has bounded mechanical predecessors,
separately reviewed semantic repairs, then mandatory Ruff 0.16.6 and Pyright
1.1.411 over authored Python/tests with identical local/CI checks. Missing
configuration and deliberate violations fail. Generated clients declare their
own stack checks. Staging delays activation but never weakens final coverage.
Full quality and parity ship only after activated quality, AC1-AC12, C1-C10,
and the required local Mac and Linux/Windows CI results pass, with unobserved live-platform limitations stated.

### Durable decisions, events, and client migration

Active decision output is generated from the existing parser and remains a
view, never a second authority. Keep numeric IDs, paths, references,
supersession links, and decision files. Existing root JSONL and historical
idless copies remain readable and unchanged. At shipped-story retention,
compact only attributed per-file events with actual payload/filename stable
IDs into one atomic events.bundle.json container with format, story, and an
events array of explicit IDs. Remove a source only after exact normalized
comparison. Distinct IDs with equal text remain distinct. Different/malformed
bundle, conflicting duplicate ID, missing story, or source mismatch refuses
without deletion; identical bundle is a no-op. There is no sidecar, database,
heuristic deduplication, Git history rewrite, or legacy events.jsonl rewrite.
Proof, markers, and task seals remain shipping authority.

Use `.factory/stories/<KEY>/events.bundle.json` for scoped stories and
`.factory/history/<KEY>/events.bundle.json` for legacy stories, with
`format: forge-event-bundle/v1`, matching story and explicit event IDs. The
existing event reader adds only those validated bundles while preserving its
legacy JSONL and loose-file behavior; identical stable IDs deduplicate across
bundle/loose sources during interrupted cleanup, conflicting content refuses.
Do not read old idless history copies as new live events. After shipped proof
is durable, write a sibling temporary file and atomically replace the bundle
path; remove loose sources only after reading back and exactly comparing the
durable bundle. Partial failure leaves sources and hard-gate proof intact.

Use existing forge upgrade for one isolated migration per Git common
directory. A dirty client gets an isolated upgrade worktree when its common
directory can be safely resolved; preserve the original dirty checkout and
hotfixes. Defer only that client's unsafe, shared, ambiguous, or unresolvable
migration and continue independent authorized client migrations. Upgrade only
owned machinery/doc contracts; client decisions, settings, CI, and evidence
remain intact. The existing three-path ephemeral run-log allowlist is
unchanged. Event cleanup cannot waive proof, markers, readiness, or shipping.

## Ten retained client failures and owner obligations

The following audit findings are implementation obligations, not completion
claims. Each owner adds focused positive, negative, tamper, and recovery
regressions where relevant.

1. Review preflight reads story proof while producers write task proof.
   NATIVE-FOREGROUND-ACTIVATE owns the first-task fix: review resolves
   verify/tests through proof_path with exact task ID and refuses story,
   sibling, absent, or stale proof. Add review.py as path 24 to the existing
   23-path first scope.
2. The actual question ledger can be omitted during task hydration.
   SHARED-COORDINATOR-JOURNEY carries exact existing story/task question
   records and identities into target ceremony context, without reviving a
   plan-mode gate or inventing a ledger.
3. Generated snapshots and migration input can consume complete-review
   capacity. LEAN-WORKFLOW keeps generated SQL/snapshots/journals in semantic
   and security review with an explicit measured risk contract, never blanket
   exclusion or truncation.
4. Git-local stage wording can make protected state appear invisible to an
   admitted sandbox. The current production probe can read the Git control
   directory and run forge next, so no read denial is claimed. LEAN-WORKFLOW
   owns the phase/status wording repair; NATIVE-FOREGROUND-ACTIVATE only
   probes actual native read and protected-write denial in its existing tests.
   No writable snapshot/token, environment claim, or recorder bypass is a fix.
5. Broad .github ownership hides client CI. LEAN-WORKFLOW treats only the
   four exact factory-owned workflows as harness machinery and all other
   .github paths as product input in measurement, review, readiness staleness,
   scaffold/upgrade, and vendor integrity.
6. Settled lint/engineering rulings disappear in fresh workers.
   LEAN-WORKFLOW propagates each current task ruling through the existing
   brief/contract and recorders, bound to story, task, contract, and signal.
   Material scope/acceptance changes still amend, re-grill, and re-approve.
7. Resume can choose the wrong proof chain when base_main_sha is absent.
   SHARED-COORDINATOR-JOURNEY preserves task, owner, branch, worktree, base
   commit, and task-level closeout mode; ambiguous recovery refuses.
8. An older task can fall back to another task or story proof.
   NATIVE-FOREGROUND-ACTIVATE owns task-bound readers and C10: an unqualified
   T2 or story singleton cannot satisfy T1. Valid historical proof remains
   readable only when its owner, task identity, and historical binding are
   established; a legitimate shipped marker cannot pollute a current T3
   singleton.
9. Resume/migration can rewrite sealed records. SHARED-COORDINATOR-JOURNEY
   preserves sealed task/stage/approval/proof bytes and refuses destructive or
   uncertain migration; reconciliation uses existing owner/trunk rules.
10. Sibling/trunk integration can overwrite sealed records.
    SHARED-COORDINATOR-JOURNEY reconciles common-directory ownership and
    immutable trunk markers without replacing an owner's sealed contract/proof,
    retaining task identity through refresh and retry.

The eight owners are NATIVE-FOREGROUND-ACTIVATE, LEAN-WORKFLOW,
NATIVE-LIFECYCLE, SHARED-COORDINATOR-JOURNEY, PORTABLE-DELIVERY-MIGRATION,
FORMAT-SOURCES, QUALITY-BASELINE, and FORGE-COORD-1.1. They replace the
unapproved 39-row graph while preserving its preparation. Background lifecycle
belongs to NATIVE-LIFECYCLE; interaction/recovery to
SHARED-COORDINATOR-JOURNEY; decisions/events/clients to
PORTABLE-DELIVERY-MIGRATION; source repairs to FORMAT-SOURCES; staged checks
to QUALITY-BASELINE; integrated parity to FORGE-COORD-1.1. LEAN-WORKFLOW is
user_facing false (backend gates, proof, CLI/docs). SHARED-COORDINATOR-JOURNEY
is user_facing true for the actual board/coordinator UI journey. The separate
Task tracker UI leaf is true; Forge integration is false despite live proof.
These are ownership candidates, not approved wildcard scopes.

## Acceptance criteria

1. Required Codex Default decisions and approvals use ordinary main chat and
   existing revision-bound commands without a tool-round prerequisite. Real
   permitted CLI/Desktop structured questions pass the same provenance checks
   as Claude across pre-story, current-story, other-story, malformed-story,
   and historical eventless cases. Missing/canceled/mismatched/replayed,
   empty/whitespace-only/multiple answers refuse. Offered-option and free-text
   answers preserve exact text. All six grills use canonical frontier_empty:
   true when appropriate, retain stated final-round compatibility, reject
   explicit false/unsupported empty rounds, and add no question expiry.
2. Both coordinators are denied direct locked writes while legitimate
   delegated workers perform approved work. Registration timing, failed
   admission, cancellation, revocation, expiry, resume, cleanup, and terminal
   truth are tested.
3. Codex-only launch, status, recovery, and setup require no Claude executable,
   process, plugin metadata, or environment state. Static vendored Claude files
   and the working companion/rescue route remain supported.
4. Worker model/effort and every approval, admission, verification, review,
   functional, PR, marker, and shipping gate are coordinator-independent.
5. Startup, resume, clear, compaction, question, and Stop interception use
   installed runtime registrations. Removing a required registration from one
   adapter or both fails parity validation.
6. At the review-only draft checkpoint, delegation, deterministic verification,
   lossless independent review, and honest source proof run without fabricated
   evidence; incomplete platform proof remains explicit. Final readiness,
   marker, shipping, and closeout require the local Mac and Linux/Windows CI results and task/worktree/
   shipping checks. Support-task proof remains separate; platform coverage rows
   cover native Codex only, and CI-backed rows state only their observed coverage.
7. After separately approved 0058 support tasks, final integration uses the
   approved stage route, real schema recorders, actual runtime evidence, and
   an unmerged review-only draft with no task marker. Missing required proof blocks
   readiness; accepted unavailable-platform limitations remain explicit, and complete required proof permits the same task's normal closure.
8. Setup honors explicit/environment/detected/interactive selection and
   cancel/EOF refusal before install, passes selection to both doctors, and
   preserves project configuration, historical evidence, and both adapters in
   fresh, adopted, and upgraded clients.
9. Both coordinators continue authorized work and resume after required
   answers without repeated continuation prompts. Optional work continues when
   facts suffice. Existing grill launcher context-file input uses a trusted
   readable UTF-8 path whose separately labeled untrusted contents cannot alter
   artifact identity, scope, decisions, evidence, or read-only authority;
   missing files refuse. Existing material-shape reread preserves nonblank
   reason and refuses blank reason, missing-reason second read, or beyond-cap
   reread. No new evidence family is added.
10. Coordinator switching occurs only at completed-task boundary after
    active-worker checks and actual no-pending-question observation in the
    existing test report. Active work, incomplete proof, unanswered/canceled
    approval, and conflicting workers refuse; no cross-session registry exists.
11. Shared presentation is required before first approval and every material
    spec/plan revision; unchanged technical corrections within standing
    authorization carry the existing binding without repeated ceremony. Main
    owns story planning, grill, approval, frozen decomposition, scheduling,
    and human questions; each task owns JIT through PR/green CI in its
    worktree. The first native task performs the full 0063 source-contract
    then target-contract sequence and refuses placeholders/source-bound proof;
    its current gates remain until LEAN-WORKFLOW ships. Exercise owner
    reads/retries, disjoint dependency-ready work, task-only enrichment, safe
    trunk reconciliation, real handles, stable/custom titles, scratchpad
    recovery, quiet results, host restrictions, and the unchanged Claude
    route. No new management framework is introduced.
12. Separately approved quality predecessors retain verification/review. Final
    activation covers authored source/tests with pinned Ruff lint/format and
    Pyright, identical local/CI checks, missing-configuration and deliberate
    violation refusals, and client stack checks. No suppression, truncation,
    review-limit bypass, or artificial clean result is allowed; the activated
    baseline passes on integrated parity before shipping.

## Parity contract labels C1-C10

C1. Setup uses explicit flag, environment, unambiguous detection, then TTY-only
interactive choice. Ambiguous/no-choice unattended runs, cancellation, EOF,
and unknown runtime refuse before installation; both doctor calls receive the
same choice and Codex has no Claude dependency.

C2. New Claude/Codex structured events preserve actual story, session, event,
tool-call, question, and answer identity. Story gates reject other-story or
unbound claims; project gates accept valid pre-story/current-story claims.
Replay, cancellation, malformed, and mismatch fail while completed historical
grills remain valid. Required Codex approvals use ordinary chat; optional
structured rounds and technical passes never imply approval.

C3. Each adapter requires startup, question, compaction, write-policy,
completion, and Stop handlers, including startup/resume/clear/compact
SessionStart. Removing/replacing any required source in one or both adapters
fails validation.

C4. Foreground/background startup failure before process creation publishes
failure without PID or exit code. Registered workers retain process-bound
admission, verified cleanup, revocation, observable status, refusal of expired
authority, and refusal of incomplete output.

C5. Init/adopt/upgrade deliver native assets through ownership and target
boundary checks, preserve client settings/historical proof, retain Claude,
and retire only unchanged harness-owned presets.

C6. Optional untrusted context reaches required cold readers through the
existing launcher without changing artifact identity, finding resolution,
frontier checks, model policy, or read-only authority. The current brief and
recorders carry settled facts; no compulsory round, forced closing question,
clean-next-round instruction, or new evidence family is added. Reread reason
and refusals are preserved. forge next routes active missing/draft specs before
requirements and authorized work continues after answers/gates.

C7. Lifecycle coverage proves approved delegation, task-scoped tests/reviews,
conditional functional proof, completed-task handoff, active-worker refusal,
and actual no-pending-question observation. Unanswered/canceled/replayed
questions do not satisfy approval; no cross-session registry exists.

C8. A real native worker contributes after stage start and before stage done,
passes verification and independent review, and records all required
local Mac and Linux/Windows CI results before final parity readiness/shipping, with unavailable live-platform observations reported honestly.

C9. Task, branch, and autoreview briefs include complete approval-bound task
plan and automated-test report. Prose deliverables remain valid when the
approved plan/contract and actual reports let review assess them. Missing,
unapproved, stale plan text, or incomplete validation refuses. Cleanup retains
required Claude and historical consumers. Review reads proof by exact task
identity.

C10. Managed save metadata preserves an unchanged story-plan grill while
substantive changes invalidate it. Readiness requires task verify, automated
tests, three explicit review assessments, and conditional functional proof.
Shared predicates reject blockers even with passed status and require
functional proof for user-facing tasks. Task readers reject unqualified
cross-task/story fallback while retaining historically bound proof. They retain
history compatibility and never use a legitimate shipped marker as a current
task singleton.

## Proof and handoff boundary

The platform evidence contract, separate /tmp Task tracker client, first native
source/target transition, original preparation bytes, ten client failures,
AC1-AC12, and C1-C10 are closure obligations. C1-C10 alone cannot establish
whole-spec closure. Before recording contracts, map each criterion to an
owning task and actual evidence. Support tasks may own complete prepared native
changes, workflow/workspace/delivery changes, or quality predecessors under
0058/0055/0056; final parity owns integrated behavior and confirms activated
quality and required local Mac/Linux/Windows CI proof, with live-platform limitations stated. No omitted or partially reviewed bytes may ship.

The approved roadmap amendment at e218db6 and reviewed proposal digest
c37199034d36f19942d133c691a5bc234df1f756a9c1347ae176640090af27ab remain
history. Preserve story/epic identity, order, unrelated fields, and no task
IDs in story depends_on. Exact scopes/tests are bound by saved story/task
plans; the replaced 39-row graph is not an approved wildcard. Temporary
review, /tmp, and preparation paths are inputs until needed facts are
preserved in repository-owned records. This draft does not authorize
implementation, merge, or release outside the approved task route. Platform evidence follows accepted 0065; CI is never represented as unobserved live Desktop behavior.
