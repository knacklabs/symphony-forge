---
status: accepted
confirmed_by: "User"
date: 2026-09-08
stories: [FORGE-COORD-1]
---

# Stage quality cleanup before enforcing the full baseline

## Context
Accepted0055 requires a permanent Python quality baseline. The existing autoreview helper rejects patches larger than180000bytes; the candidate formatter preview alone is1816106bytes. The user explicitly selected staged cleanup PRs on2026-09-08 after being offered staged cleanup or expanded review capacity.

## Decision
Amend0055's rollout timing: deliver bounded cleanup PRs with existing verification and independent review, then activate mandatory full-repository lint, formatting and type checks before coordinator parity ships. Keep the approved Ruff/Pyright choice and final full coverage. During the explicit migration, do not claim the new full baseline is enforced before it actually passes; preserve existing tests and reviews. This is a staged migration, not permanent exclusion of legacy files, blanket suppression or a review-limit bypass.

## Consequences
Plan cleanup units against actual complete patch bytes with headroom below the installed review limit, preserving normal task approval, delegation, review and PR lifecycle. Mechanical formatting and semantic repairs remain separately reviewable. Record final full-baseline activation and tests that missing configuration and violations fail. Preserve user main-conversation interaction and existing candidate work. This decision authorizes preparation of the staged rollout; it does not invent task approvals, native event receipts, merge approval or permission to bypass target runtime gates.
