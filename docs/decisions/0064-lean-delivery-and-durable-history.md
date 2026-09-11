---
status: accepted
confirmed_by: "User (explicit lean-workflow and client-migration approval, Codex conversation 2026-09-10)"
date: 2026-09-10
stories: [FORGE-COORD-1]
---

# Lean delivery with durable decisions and task proof

## Context
On 10 September 2026 the user approved simplifying the workflow, cleaning up
existing ledgers and migrating Symphony clients. The developer should make
necessary decisions quickly in the main conversation, then let authorized
work continue unattended. Repeated planning, approval and review ceremonies
had obscured the work; the unapproved 39-task proposal is replaced.

The current installed autoreview helper supports complete, lossless review
chunks. Its 512000-byte prompt capacity is an observed tool setting, not a new
Forge policy. The previous 180000-byte rejection remains in an older backup.
Task boundaries must follow coherent changes and review risk rather than that
obsolete limit. Complete coverage remains mandatory.

## Decision
Use one current task brief stating the intended behavior, boundaries, owner,
verification and relevant rulings. Main retains the project/story intent and
dependency graph; each task owns its worktree and delivery through PR and green
CI. Derive execution and review inputs from that brief and existing records.
Do not add another plan, approval ledger, review registry or coordinator.

Carry the user's actual standing authorization across in-scope execution,
technical corrections and retries. Bind each concrete revision honestly through
the existing approval commands. Only a material new choice, changed intent or
scope, missing authority, or an unresolved contradiction needs the developer.
Present one concise recommendation, its tradeoff and consequence together with
the actual changed artifact. Never fabricate an answer or infer authorization
from silence. A required decision blocks dependent work; independent ready work
continues. Inject settled rulings into every fresh worker and reviewer so a
resolved issue is not repeatedly raised without new contrary evidence.

Use independent design scrutiny where the change warrants it: permissions,
security boundaries, destructive operations, data migration and substantial
architecture changes. Ordinary bounded work does not require separate story
and task cold reads or a repeated cold read after each factual correction.
Existing genuine grill records remain valid history. Structured question rounds
actually used retain their exact identity, eligibility and single-use rules.

Run meaningful deterministic tests and the declared CI checks. Use one
independent review operation with one combined assessment of quality,
performance and security, followed by an autonomous fix/review loop until
clean. Preserve explicit assessments and their shared run/diff binding in the
existing three review artifacts; never copy a pass into an unassessed lens.
The installed review helper may divide complete inputs into lossless chunks;
every chunk must finish successfully before the operation passes. No input
truncation, skipped semantic/generated output, cap override or artificial clean
result is permitted. Choose task bounds from behavior and risk. Mechanical
formatting and semantic repairs remain separately reviewable; full Ruff/Pyright
activation remains mandatory before parity ships.

Keep active decisions available through the existing derived reader and replace
repeated policy text with canonical pointers. Preserve historical decision IDs,
paths and references. Compact only shipped-story per-file events into one
validated immutable bundle using their actual payload/filename IDs. Remove a
source only after identical content is durable in that bundle. Retain repeated
events with distinct IDs; never infer identity from equal text. Leave legacy
idless JSONL and historical copies unchanged. Proof, task seals and trunk
markers remain durable authority, distinct from diagnostic event history. Use
the existing upgrade path for the one-time client migration, isolating dirty
clients and preserving client changes and existing hotfixes.

## Consequences
- Amend only the repeated planning/grill, edited-plan approval and mandatory
  budget-driven split clauses of 0032, 0044, 0048, 0050, 0052, 0059 and 0061.
  Attributed authorization, concrete revision binding and locked worker scope
  remain required. Preserve 0018's actual admission, measurement and test gates.
- Under this accepted decision and 0011, amend the separate lens-launch
  procedure while retaining genuine three-lens proof. Proposed 0049 is not
  authority for this change. Amend 0055/0056 rollout ordering to native
  foundation, lean enforcement, then coherent quality capabilities; full static
  quality and all six native runtime cells still precede full parity shipping.
  Amend 0058's obsolete fixed-cap interpretation: existing review limits mean
  the installed helper's actual enforced safeguards, never a tool-cap override.
  Replace the spec's agreed 120000/180000-byte bounds with complete review under
  the current tool's actual capacity, without changing that tool's safeguards.
- Amend 0017's copied-but-never-removed event clause only for exact durable
  per-file-event compaction. Preserve 0022/0025/0045 proof/history requirements
  and the existing three-path ephemeral-log untracking allowlist. No database,
  Git history rewrite or client decision-file deletion is authorized.
- Implement the changed rules through the normal registered-worker route.
  Until enforcement ships, existing commands retain their real prerequisites;
  do not invent passing records to skip them.0063 supplies the existing first
  source-contract to target-workspace transition. The first native task retains
  genuine source/target binding and current review gates; the lean-workflow
  task then changes the gates for subsequent work.
- Resume must preserve task identity, base commits and sealed proof. A task's
  missing evidence cannot be replaced by another task's review. Trunk owns
  immutable merged markers; the task worktree owns active contracts and proof.
  Fix the reported client failures with regressions before rollout.
- Keep routine progress quiet. Main reports meaningful state changes, completed
  PRs, failures and actual decisions; unattended runs return a compact account
  of completed work and remaining blockers. This decision schedules no job and
  grants no new merge authority or platform-proof substitution.
