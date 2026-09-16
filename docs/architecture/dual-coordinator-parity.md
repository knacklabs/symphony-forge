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
| Claude | `PreToolUse` | `Bash|AskUserQuestion` and `Edit|Write|MultiEdit|NotebookEdit` |
| Claude | `PostToolUse` | completed `AskUserQuestion` plus diagnostic write capture |
| Claude | `Stop` | the host stop event |
| Codex | `SessionStart` | `startup|resume|clear|compact` |
| Codex | `PreCompact` | the host pre-compact event |
| Codex | `PreToolUse` | `Bash|Edit|Write|apply_patch|request_user_input|request_user_input_async` |
| Codex | `PostToolUse` | completed synchronous `request_user_input` |
| Codex | `Stop` | the host stop event |

An asynchronous question call is guarded at issuance but is not completion evidence. A newly exposed tool must be added to the applicable matcher and tests before parity can be claimed. `check_dual_runtime.py`, focused hook tests, and the recorder-produced automated report are task proof. Timeline events remain best-effort diagnostics under Decision 0017.

Unexpected lifecycle exceptions reach one top-level boundary, return nonzero with a stable sanitized `errorId`, write one structured error containing that ID and the launch's distinct `correlationId`, and increment `forge_native_unexpected_errors_total` once with bounded labels. `correlationId` is the workflow trace key; `errorId` joins the terminal failure to its one structured error. Decision 0060's narrow POSIX signal-mask restoration stays in the existing launch path.

## Human-question identity

A successful structured-question hook writes one immutable event. The filename's fresh lowercase 32-hex stem is its event ID; a zero-based index identifies each question in the call. Eligibility binds runtime, session, event ID, question index, exact story/gate/task scope, current input digest, requiredness, question, ordered options, and nonblank answer. The call is atomic for authority: every question returns one nonblank answer or no answer from that call is eligible. Labels and nonblank free-form answers are preserved exactly. One pass claims a question once; Decision 0073 permits reuse only when re-recording the same gate, story, and task. Historical rounds keep their old contract.

Question reuse requires the same gate, story, task, and input digest. If an answer changes an approval-bound artifact, the earlier round remains audit context but cannot authorize the changed bytes. The owning decision or approval independently binds the final revision, and the final grill uses a fresh eligible round or Shared's independently ledgered empty-frontier route. No revision-mapping protocol or chat collector is added.

Shared extends the existing signal family with an orchestrator-produced `required-question` blocked signal bound to the story and sorted affected tasks/artifacts. Closing it requires a validated owning decision or approval record path and SHA256. Existing worker signals keep their present producer contract. Before Shared ships, ordinary required questions remain in the current host conversation and no cross-session recovery is claimed.

An optional grill context file is captured into a randomized regular single-link `0600` snapshot beneath a dedicated per-user `0700` transient directory. The griller launches only that immutable snapshot and deletes it after terminal publication. Durable lifecycle rows and evidence record only whether context was supplied, its byte count, and a random opaque context ID; they never record source path, content digest, or supplemental bytes. Recovery deletes a stale snapshot only when ownership, type, link count, mode, directory boundary, and launch/context filename identity all match; an unknown or mismatched transient refuses unchanged.

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

## One-time upgrade migration

Upgrade performs one fresh walk of both fixed-review roots before any target write and represents every discovered candidate path exactly once in a sorted coverage manifest as eligible, excluded, or invalid. Eligible rows are marker-bound sealed three-lens sets and become the migration inventory. Active or otherwise unshipped, incomplete-but-well-formed, multiply-bound, and unidentified rows are excluded with reasons; active work receives a fresh ordinary combined review. Malformed, linked, colliding, replaced, or ambiguous rows are invalid and block the whole migration. A second independent walk must reproduce the full candidate count, classifications, and digest, so a classifier omission cannot disappear from both sides. Zero eligible rows pass when the universe is empty or every row is explicitly excluded. Sealed proof binds the original marker commit and exact fixed-artifact bytes. Only after complete coverage and the eligible inventory pass may upgrade write and read back `origin=upgrade` generations and their pointers.

For already sealed legacy tasks, the current migration pointer is valid only when its generation's sealed-commit binding exactly equals the immutable marker. A replacement, mismatch, malformed set, mixed state, collision, linked path, or ambiguous owner refuses. Byte-identical retry is idempotent. Runtime readers never fall back to fixed paths.

The first event bundle for a shipped story is immutable. A later eligible event makes preview and apply refuse while leaving that event loose and unchanged. Retry may delete only loose events already represented by identical bundle members. V1 adds no successor shard.

## Successor ownership

`NATIVE-LIFECYCLE` owns detached read-only helpers, lifecycle recovery, cancellation, correlated errors, metrics, and signal behavior. `SHARED-COORDINATOR-JOURNEY` owns question identity, workspace-first task ownership, board state, and between-task coordinator changes. `PORTABLE-DELIVERY-MIGRATION` owns setup delivery, review migration, event retention, and client rollout support. Each successor updates this architecture before changing an enduring boundary.
