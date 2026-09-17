# Dual-coordinator parity architecture

This document owns the shared technical boundaries for dual-coordinator parity. The approved story decomposition and task plans own delivery order, exact paths, tests, and implementation scope.

## Coordinator and writer boundary

Claude Code and native Codex adapt the same Forge phase engine. One coordinator owns the current human conversation; product writes still require an admitted task worker whose process, task, worktree, stage, brief, and scope match. The ledgered five-file degraded window remains the outage path.

A developer- or host-directed cooperative coordinator change occurs only between completed tasks. Forge requires the prior marker and green CI on refreshed trunk, no active worker, and no unresolved required ordinary-chat question signal; the developer or host stops the old session, and the new coordinator resumes with `forge next`. The recorded `Wait for all` answer governs that transfer boundary, while Decision 0064 still permits separately owned dependency-ready work that no pending answer can affect. Forge does not record or mechanically verify the old-session stop, observe an unrecorded partial structured exchange, fence a stale session, or prevent concurrent coordinators. This story adds no live transfer command, fencing token, or coordinator registry.

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
| Codex | `Stop` | the host stop event |

An asynchronous question call is guarded at issuance but is not completion evidence. A newly exposed tool must be added to the applicable matcher and tests before parity can be claimed. `check_dual_runtime.py`, focused hook tests, and the recorder-produced automated report are task proof. Timeline events remain best-effort diagnostics under Decision 0017.

Unexpected lifecycle exceptions reach one top-level boundary, return nonzero with a stable sanitized `errorId`, write one structured error containing that ID and the launch's distinct `correlationId`, and increment `forge_native_unexpected_errors_total` once with bounded labels. `correlationId` is the workflow trace key; `errorId` joins the terminal failure to its one structured error. Decision 0060's narrow POSIX signal-mask restoration stays in the existing launch path.

## Native approval and human-question identity

Story and task plans receive one independent cold read. Its recorder authenticates the exact read-only launch lifecycle, argv, runtime/session, brief and durable result identity, rather than trusting a matching label or caller-supplied digest. The launch binds the exact cold input; an ordered one-to-one disposition maps every finding to its resolution and source, and explained amendments bridge that input to the final artifact. Native human approval then binds the final semantic digest. The cold reader is never described as having reviewed amended bytes. Requirements-only grills, human-round floors, synthetic `frontier_empty` questions, manual approval commands, board approval, and the second unchanged save are retired from normal runtime.

Both approval adapters call one recorder. It derives exactly one eligible current-frontier story or task candidate. Claude accepts only a successful `ExitPlanMode` whose `tool_input.plan` derives the current digest. Codex accepts only the completed synchronous question id `approve_plan_<digest>` with prompt `Approve exact plan digest <digest>?`, ordered `Approve plan / Request changes / Stop` choices, and an id-keyed `Approve plan` answer. Runtime, stable session and event identity, plan kind, story, task, and current digest are required and replay-protected. Zero or multiple candidates, replay, missing identity, stale digest, cancellation, wrong runtime, asynchronous acknowledgement, optional clarification, or any unsupported payload refuses. Attribution is only `human-via-Claude` or `human-via-Codex` plus the bound identities.

Broader structured questions remain a successor concern. A successful structured-question hook may still write an immutable diagnostic event, but those old round records no longer authorize plan or task approval and normal runtime never consumes them as a compulsory grill floor.

Shared extends the existing signal family with an orchestrator-produced `required-question` blocked signal bound to the story and sorted affected tasks/artifacts. Closing it requires a validated owning decision or approval record path and SHA256. Existing worker signals keep their present producer contract. Before Shared ships, ordinary required questions remain in the current host conversation and no cross-session recovery is claimed.

An optional grill context file is captured through one open handle into a randomized regular single-link `0600` snapshot beneath a dedicated same-user `0700` transient directory. Native Windows applies and verifies an owner-only protected DACL, rejects extra access entries, and reopens the exact file identity before launch. The griller launches only that immutable snapshot and deletes it after terminal publication. Durable lifecycle rows and evidence record only whether context was supplied, its byte count, and a random opaque context ID; they never record source path, content digest, or supplemental bytes. Recovery deletes a stale snapshot only when ownership, type, link count, mode or DACL, directory boundary, and launch/context filename identity all match; an unknown or mismatched transient refuses unchanged.

## Review publication

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

One classifier in `factory_lib.py` supplies review scope plus current and historical binary branch-diff hashing. Genuine-contribution proof cites its qualifying path and hunk in that same diff and correlates it with admitted write and terminal evidence. There is no product-tree digest.

Pre-seal readers resolve the current pointer. Normal sealed readers resolve the pointer at the task marker commit. A citation-based rejection reads a selected combined or rejection generation and writes an immutable `origin=rejection` successor bound to its immediate source and combined root; it preserves exact raw output, prior history, and unaffected lenses, then appends the exact finding, reason, citation, actor, and durable lesson identity. Upgrade, fixed-only, unselected, copied, stale, incomplete-source, unrelated, no-match, ambiguous, and already-rejected sources refuse without changing selection.

## One-time Lean upgrade migration

Lean upgrade requires a clean target before any write, and `--force` cannot bypass that refusal. Its primary per-family classifier inventories requirements and plan grills, grill-round ledgers, embedded task approvals, story approval and plan-mode markers, fixed review lenses, legacy stage stamps, the old hook flag, and the known fifteen-profile installation state. A separate raw no-follow directory-entry walk over fixed legacy roots and exact parents emits normalized path/type/identity without calling those discoverers. Every raw candidate must classify exactly once, and both universes must match count, classification, and digest before publication.

Current outputs are built and validated in a temporary area before ordinary upgrade mutation, then published, read back, and recorded in `.factory/migrations/lean-workflow-v2.json` before exact promoted old bytes are removed. Project-owned settings, client-added profiles, and client-modified same-name profiles are preserved; only byte/hash-matching Forge-owned retired files are removed or replaced. Unknown, mixed, linked, malformed, conflicting, or hash-mismatched state refuses. Byte-identical completed retry validates the saved manifest and outputs; unequal partial retry refuses.

For fixed review proof, eligible rows are marker-bound sealed three-lens sets. Active or otherwise unshipped, incomplete-but-well-formed, multiply-bound, and unidentified rows are excluded with reasons and active work receives a fresh ordinary combined review. Malformed, linked, colliding, replaced, or ambiguous rows block migration. Sealed proof binds the original marker commit and exact fixed-artifact bytes. Only after complete coverage may upgrade write and read back `origin=upgrade` generations and their pointers.

For already sealed legacy tasks, the current migration pointer is valid only when its generation's sealed-commit binding exactly equals the immutable marker. A replacement, mismatch, malformed set, mixed state, collision, linked path, or ambiguous owner refuses. Byte-identical retry is idempotent. Runtime readers never fall back to fixed paths.

## Successor ownership

`NATIVE-LIFECYCLE` owns detached read-only helpers, lifecycle recovery, cancellation, correlated errors, metrics, and signal behavior. `SHARED-COORDINATOR-JOURNEY` owns broader question identity, workspace-first task ownership, board state, and between-task coordinator changes. `PORTABLE-DELIVERY-MIGRATION` owns the remaining legacy layout families, setup delivery, event retention, and client rollout support; it preserves Lean's three-profile registry and does not reintroduce retired profiles or fixed-review fallback. Each successor updates this architecture before changing an enduring boundary.

Portable also owns the event-family migration to one append-only event log per story. It must preserve every validated source event exactly, support safe concurrent append and crash-safe idempotent retry, and delete a legacy source only after durable readback proves the same event identity and payload. Legacy JSONL and historical copies remain immutable inputs; Portable may not revive the superseded one-shot bundle design.
