---
status: superseded
confirmed_by: "Ravi"
date: 2026-08-11
stories: [FORGE-ROLE-1]
superseded_by: 0087-full-access-close-checks
---

# Strict Role Split

## Context

The role split (Claude orchestrates, Codex executes) was instruction-level:
with an approved plan the orchestrating session could edit product freely
(five direct edits in one day, none prevented), discovery drifted to Claude
subagents, and the sanctioned rescue path was blocked by its own guard's
quoting test. The operator's call: make the split a gate.

## Decision

Session writes to product and canon paths (code, tests, `factory/`
machinery incl. prompts and skills, `.github/`, `constitution/`,
`AGENTS.md`, `WORKFLOW.md`, vendored adapters) are hook-denied ALWAYS —
even under an approved plan. `forge delegate` is the sole write path for
those files; review findings re-delegate by mechanical necessity (no
trivial-fix carve-out). Discovery exploration routes to Codex rescue
read-only; the orchestrator reads code only inside gate work (0011's
direct review stands — reads are not fenced). The single exception is an
explicitly opened, ledgered degraded-mode window (`forge mode degraded
start --reason`, quickfix ledger, 5-file budget) whose done record the PR
declares.

## Consequences

- **Amends 0013 and 0031 (human-confirmed 2026-08-11):** quickfix and lite
  windows survive as LEDGERED WORK RECORDS — the small-work ticket Gate A
  requires — but the writes inside them are delegated like all product
  work. The degraded window is the only session-write permit. Both prior
  records stay active for their ledger/window semantics; their
  session-write clauses are superseded by this record.

- Orchestration surfaces stay writable: `docs/`, `plans/`, `.factory/` via
  recorders, prototype, scratchpad, and git operations on worker diffs.
- The lockout is born on a shared classifier in `repo_kind.py`; the four
  legacy product-path classifiers remain (D-0007 progress note, not a
  resolve).
- The companion guard admits provably read-only invocations by argument
  content — quoting alone no longer denies — or the routing rule is dead
  letter. Read-only can happen ANYTIME: no active task, no approved plan,
  any phase, harness and client repos alike. Only writes are stage-bound.
- A companion outage without a window stops product work; that is the
  chosen failure mode (bounded valve over silent role-drift).
