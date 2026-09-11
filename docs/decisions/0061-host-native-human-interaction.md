---
status: accepted
confirmed_by: "User (Codex conversation)"
date: 2026-09-09
stories: [FORGE-COORD-1]
---

# Forge follows the host's human-interaction rules

## Context
On 9 September 2026 the user directed: "we have honour what your default
mode does. lets stick to that. change forge", followed by "lets resolve all
the conflicts which forge has with codex and lets make the UX simple and
flawless with codex". This explicitly changes the earlier synchronous-only
interaction choice; it is not a synthetic question-tool answer.

The current Codex Default mode permits synchronous `request_user_input` for
optional clarification or quality questions, but prohibits its use for
permission requests and requires necessary explicit input in ordinary chat.
Forge's compulsory tool-backed closing rounds therefore prevent its own
otherwise supported approval workflow. The existing decision, spec, plan
and task approval commands already record explicit human confirmations.

## Decision
Forge follows the actual host's interaction rules. In Codex Default mode,
main asks necessary decisions and approvals directly in ordinary chat. Use
the synchronous question tool only for optional questions the host permits;
an unanswered optional question is not permission or a reason to block work
that can proceed from existing facts. Do not require a manual mode switch,
an asynchronous approval tool, a fabricated tool event or a repeated
"continue" message.

Grilling remains an independent technical check. It must resolve its
blocking findings and explicitly attest an empty frontier before passing,
but need not invent a human question or closing round when nothing requires
a human decision. Record actual human decisions through the existing
decision and artifact-approval commands. Keep exact matching, eligibility
and single-use consumption for any structured question rounds actually
used. An empty round list is not human approval.

Main displays the saved revision and its changes before any required
approval, records the user's actual confirmation against that revision,
then continues automatically. Existing authorization persists; changed
approval-bound content still needs its own confirmation. Ordinary facts,
test failures and review findings are resolved by the agents within scope.

## Consequences
- Amend only the compulsory human-round floor, synchronous-only and manual
  mode-switch clauses of Decisions0048,0051,0053,0054,0057 and0059. Preserve
  historical receipts and the other requirements of those decisions.
- Reuse existing approval records and grill artifacts. There is no new chat
  collector, parallel approval ledger, host-instruction override or custom
  coordinator framework. Never label ordinary chat as a completed tool call.
- Reconcile the canonical skill, runtime guidance, hooks and gate messages
  with actual Codex capabilities. Keep logical phase ownership distinct from
  optional agent presets and preserve the harness's worker model policy.
- The immediate human-interaction compatibility repair belongs to the
  previously authorized Decision0054 bootstrap preparation: keep its exact
  scope bounded, test it and independently review it before relying on it.
  It supplies no normal task contribution, stage completion or release proof.
- All remaining implementation retains the accepted bounded task route,
  scope/admission checks, independent grilling, revision-bound approvals,
  verification, tests, three-lens review, conditional functional proof,
  PR/CI checks and human merge ownership. Preserve both coordinator routes
  and the complete supported-runtime release criteria.
