# Dual-coordinator parity architecture

This document owns the shared technical boundaries for dual-coordinator parity. The approved story decomposition and task plans own delivery order, exact paths, tests, and implementation scope.

## Coordinator and writer boundary

Claude Code and native Codex adapt the same Forge phase engine. One coordinator owns the current human conversation. Claude writes through an admitted `codex-plugin-cc` companion. Native Codex prepares the canonical task brief with `forge delegate`, records a preparation row bound to the active task, matching worktree, stage, brief digest and effective or narrowed scope, and then uses a role-based host `spawn_agent` subagent. Dispatch passes no model/reasoning override, so the selected configured role's defaults apply and may pin either value. Native close requires that row but no launched process; Forge does not bind native authority to a session, PID, token or lock. Raw/direct/nested `codex exec` and direct plugin shell launch are off-contract and hook-denied in both runtimes. The ledgered five-file degraded window remains the Claude companion outage path.

A developer- or host-directed cooperative coordinator change preserves completed task markers, green CI on refreshed trunk and unresolved required-question state. Native Codex uses the host's normal coordination controls; Forge does not inspect or restrict subagent status, cancellation, resume, foreground/background execution, old-session stop, stale resumption or concurrency. Decision 0064 still permits separately owned dependency-ready work that no pending answer can affect. The new coordinator resumes with `forge next`; there is no Forge session registry, fencing token or live-transfer protocol.

After the Decision 0063 first-task exception, `task start` creates the worktree before task-plan save and grill. Its attach option accepts only a clean, registered, unowned worktree from the same Git common directory at the fetched trunk commit, with matching branch, story, task, decomposition, and dependency markers. Empty dependencies inherit the immediate predecessor; a nonempty list selects exactly those dependencies. `stage start --trunk` remains legacy behavior and cannot satisfy the new workspace-owned flow.

`./setup` and `forge doctor [--fix]` select the coordinator for one invocation from the first applicable tier: exactly one valid explicit argument, one valid `FORGE_COORDINATOR`, one detected host family, then an interactive TTY question. `CODEX_THREAD_ID` or `CODEX_SHELL` detects Codex; `CLAUDECODE` detects Claude. A valid higher tier suppresses lower-tier disagreement. Both or neither detected family falls through to TTY; multiple explicit values, an invalid selected tier, cancellation, EOF, or unattended absence refuses before repair. Init, adopt, and upgrade install both adapters and never persist a selected coordinator.

## Adapter contract

The committed configurations are the normative current tool inventory:

| Runtime | Hook | Matcher or source |
|---|---|---|
| Claude | `SessionStart` | `startup|resume|clear|compact` |
| Claude | `PreCompact` | the host pre-compact event |
| Claude | `PreToolUse` | `Bash|Edit|Write|MultiEdit|NotebookEdit|AskUserQuestion` |
| Claude | `PostToolUse` | completed `AskUserQuestion|ExitPlanMode` |
| Claude | `Stop` | the host stop event |
| Codex | `SessionStart` | `startup|resume|clear|compact` |
| Codex | `PreCompact` | the host pre-compact event |
| Codex | `PreToolUse` | `Bash|apply_patch|request_user_input` |
| Codex | `PostToolUse` | completed synchronous `request_user_input` |
| Codex | `Stop` | the host stop event, advisory only; Forge does not block native stop |

An asynchronous question call is guarded at issuance but is not completion evidence. A newly exposed tool must be added to the applicable matcher and tests before parity can be claimed. `check_dual_runtime.py`, focused hook tests, and the recorder-produced automated report are task proof. Timeline events remain best-effort diagnostics under Decision 0017.

Native subagent lifecycle belongs to the host. Forge does not wrap native spawn,
status, cancellation, resume or failure in a second lifecycle, correlation ID,
metric, process cleanup or signal policy. Command-managed Claude companions and
standalone specialist commands retain their own existing error handling.

## Native approval and human-question identity

Story and task plans receive one independent cold read. In native Codex,
`forge grill run ...` prepares a self-contained descriptor bound to the exact
input and a preparation ID. Main includes the complete descriptor and its
context metadata in the actual `spawn_agent` message to the configured
`griller` role, then records the exact returned JSON with
`record_grill_from_json.py --cold-result <path> --preparation-id <id>` plus the
gate/task arguments. Its recorder validates the exact input, canonical brief
and result binding rather than trusting a matching label or caller-supplied
digest; native proof does not depend on process/session attribution. Claude
retains its command-managed cold-reader lifecycle. An ordered one-to-one
disposition maps every finding to its resolution and source, and explained
amendments bridge that input to the final artifact. Native human approval then
binds the final semantic digest. The cold reader is never described as having
reviewed amended bytes. Requirements-only grills, human-round floors,
synthetic `frontier_empty` questions, manual approval commands, board approval,
and the second unchanged save are retired from normal runtime.

Both approval adapters call one recorder. It derives exactly one eligible current-frontier story or task candidate. Claude accepts only a successful `ExitPlanMode` whose `tool_input.plan` derives the current digest. Codex accepts only the completed synchronous question id `approve_plan_<digest>` with prompt `Approve exact plan digest <digest>?`, ordered `Approve plan / Request changes / Stop` choices, and an id-keyed `Approve plan` answer. Runtime, stable session and event identity, plan kind, story, task, and current digest are required and replay-protected. Zero or multiple candidates, replay, missing identity, stale digest, cancellation, wrong runtime, asynchronous acknowledgement, optional clarification, or any unsupported payload refuses. Attribution is only `human-via-Claude` or `human-via-Codex` plus the bound identities.

Broader structured questions remain a successor concern. A successful structured-question hook may still write an immutable diagnostic event, but those old round records no longer authorize plan or task approval and normal runtime never consumes them as a compulsory grill floor.

Shared extends the existing signal family with an orchestrator-produced `required-question` blocked signal bound to the story and sorted affected tasks/artifacts. Closing it requires a validated owning decision or approval record path and SHA256. Existing worker signals keep their present producer contract. Before Shared ships, ordinary required questions remain in the current host conversation and no cross-session recovery is claimed.

An optional native context-file input becomes a dispatch descriptor naming the validated source path, regular UTF-8 metadata, byte count, file identity, and opaque context ID for the host/subagent. Main must include that complete descriptor in the actual `spawn_agent` message. The descriptor is not proof that the subagent already received or read the content. Command-managed Claude companion launches retain the private immutable snapshot route: POSIX uses a randomized single-link `0600` file beneath a same-user `0700` directory; Windows verifies an owner-only DACL. Those snapshots are capacity-checked, deleted after terminal publication, and recovered only after exact ownership/type/link/mode-or-DACL/directory/identity matching.

## Review publication

Forge-managed autoreview is unchanged: it remains an authenticated, externally
maintained black box and may invoke Codex or agents internally. The ban on raw
or nested `codex exec` for general/manual delegation does not constrain its
internal implementation.

The story-level `review-run.json` remains only an input/run token. Each task selects one immutable review generation through:

`.factory/stories/<story>/tasks/<task>/reviews/selected.json`

One default review calls the installed helper once and writes one generation below `reviews/generations/` only after the complete raw result and all three schema-valid lens records validate. Failed or interrupted pre-publication attempts retain ordinary run diagnostics but publish no generation or pointer. Forge reads a complete generation back before atomically replacing the pointer. A blocking generation is selected and revokes clean status; only a selected clean generation certifies proof. `factory/schemas/review-set.json` distinguishes `origin=combined`, `origin=rejection`, and `origin=upgrade`.

Each actual provider pass has exactly three full-line blocks, in quality, performance, security order:

```text
BEGIN FORGE ASSESSMENT <lens>
<non-empty body>
END FORGE ASSESSMENT <lens>
```

Quality carries the existing machine-parsed contract verdicts. Forge preflights their minimum size against the helper's 3,000-character explanation limit. Unchunked output is one top-level pass; chunked reports are nonempty and labelled exactly `chunk 1/N` through `chunk N/N`. Raw output and provider findings remain lossless; only the helper's synthesized top-level chunk body uses its declared 2,000-character bound. Forge reconstructs and validates those top-level findings with the installed helper's merge key: NFC repository-relative POSIX path, integer line, exact category, and NFC whitespace-collapsed case-folded tagged title. Every finding has one lowercase lens tag. Lens projection, cross-lens duplicate detection, and citation rejection use the separate remediation fingerprint: repository-relative NFC POSIX path, that integer line as normalized start and end, and the normalized tag-free title. Same-lens projection keeps only the first provider finding for a remediation fingerprint while raw and top-level findings remain lossless; the same fingerprint under multiple lenses refuses. Assessment text carries no separately parsed finding fingerprint. Projections preserve pass order and reuse the existing score, recommendation, and worst quality-verdict functions.

One classifier in `factory_lib.py` supplies review scope plus current and historical binary branch-diff hashing. Native contribution is established by qualifying in-scope paths and hunks in that diff plus task acceptance and review evidence. It is not correlated to a process launch or terminal row, and the repository makes no mechanical authorship claim. There is no product-tree digest.

Pre-seal readers resolve the current pointer. Normal sealed readers resolve the pointer at the task marker commit. A citation-based rejection reads a selected combined or rejection generation and writes an immutable `origin=rejection` successor bound to its immediate source and combined root; it preserves exact raw output, prior history, and unaffected lenses, then appends the exact finding, reason, citation, actor, and durable lesson identity. Upgrade, fixed-only, unselected, copied, stale, incomplete-source, unrelated, no-match, ambiguous, and already-rejected sources refuse without changing selection.

## One-time Lean upgrade migration

Lean upgrade requires a clean target before any write, and `--force` cannot bypass that refusal. Its primary per-family classifier inventories requirements and plan grills, grill-round ledgers, embedded task approvals, story approval and plan-mode markers, fixed review lenses, legacy stage stamps, the old hook flag, and the known fifteen-profile installation state. A separate raw no-follow directory-entry walk over fixed legacy roots and exact parents emits normalized path/type/identity without calling those discoverers. Every raw candidate must classify exactly once, and both universes must match count, classification, and digest before publication.

Current outputs are built and validated in a temporary area before ordinary upgrade mutation, then published, read back, and recorded in `.factory/migrations/lean-workflow-v2.json` before exact promoted old bytes are removed. Project-owned settings, client-added profiles, and client-modified same-name profiles are preserved; only byte/hash-matching Forge-owned retired files are removed or replaced. Unknown, mixed, linked, malformed, conflicting, or hash-mismatched state refuses. Byte-identical completed retry validates the saved manifest and outputs; unequal partial retry refuses. A validated original empty completion may publish one `lean-workflow-v2-supplement.json` for later eligible proof inputs, bound to the original manifest; non-proof runtime/profile inputs refuse that supplement.

For fixed review proof, eligible rows are marker-bound sealed three-lens sets. Active or otherwise unshipped, incomplete-but-well-formed, multiply-bound, and unidentified rows are excluded with reasons and active work receives a fresh ordinary combined review. Malformed, linked, colliding, replaced, or ambiguous rows block migration. Sealed proof binds the original marker commit and exact fixed-artifact bytes. Only after complete coverage may upgrade write and read back `origin=upgrade` generations and their pointers.

For already sealed legacy tasks, the current migration pointer is valid only when its generation's sealed-commit binding exactly equals the immutable marker. A replacement, mismatch, malformed set, mixed state, collision, linked path, or ambiguous owner refuses. Byte-identical retry is idempotent. Runtime readers never fall back to fixed paths.

## Successor ownership

Native lifecycle operations are host-owned and require no Forge lifecycle
feature. `SHARED-COORDINATOR-JOURNEY` owns broader question identity,
workspace-first task ownership and board state. `PORTABLE-DELIVERY-MIGRATION`
owns the remaining legacy layout families, setup delivery, event retention, and
client rollout support; it does not reintroduce Forge-native process locks,
retired profiles or fixed-review fallback. Each successor updates this
architecture before changing an enduring boundary.

Portable also owns the event-family migration to one append-only event log per story. It must preserve every validated source event exactly, support safe concurrent append and crash-safe idempotent retry, and delete a legacy source only after durable readback proves the same event identity and payload. Legacy JSONL and historical copies remain immutable inputs; Portable may not revive the superseded one-shot bundle design.
