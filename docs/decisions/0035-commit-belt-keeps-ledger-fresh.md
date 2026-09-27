---
status: superseded
superseded_by: 0093-lean-forge-rebuild
confirmed_by: "Ravi"
date: 2026-08-10
stories: [FORGE-ALIGN-1]
---

# Commit Belt Keeps Ledger Fresh

## Context

`docs/context/ledger.json` is the only self-fresh ledger: CI hard-fails on
drift (`context scan --check`), but the scan itself was manual, so the
deterministic outcome of an agent session editing a context doc was a red PR
(minegate PR #69 failed the check three times in one morning). A write-time
PostToolUse hook was drafted and rejected as speculative: `pending_context`
counts unscanned files as pending already, so write-time scanning changes no
gate outcome — freshness is only ever checked at commit/CI.

## Decision

The `git commit` interception in `pre_tool_use.py` is the single in-session
enforcement point for context-ledger freshness: it re-scans the inbox
in-process, auto-stages the refreshed `docs/context/ledger.json` so the ledger
diff rides the same commit, and DENIES the commit with the refusal reason while
any context file is refused (secret-shaped or oversized).

## Consequences

- Auto-staging mutates the index from a hook, deliberately bounded: exactly one
  machine-owned path, only after a successful scan (verification separated
  from, and preceding, the stage — lesson
  `verify-merge-resolution-before-staging`).
- Accepted holes, with the unchanged CI check as backstop: `git commit
  <pathspec>` bypasses the index, and out-of-session commits see no hooks.
- The write-time hook lives in the deferral ledger with a trigger (stale-ledger
  CI failures recurring from out-of-session commits of agent-written context,
  or a second consumer of write-time freshness), not in the code.
- Deny-on-refusal matches the plan gate's stance: secret-shaped content is
  stopped before it reaches git history, not after CI reds it.
