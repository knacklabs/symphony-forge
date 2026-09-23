---
status: accepted
confirmed_by: "Ravi Kiran Vemula"
date: 2026-09-23
stories: [FORGE-COORD-1]
supersedes: 0080-native-role-model-routing
---

# Native role model routing on GPT-6

## Context

Decision 0080 pinned every native child role to the GPT-5.6 family and gave
read-heavy exploration its own `gpt-5.6-terra` lane at `high` reasoning. Two
things have since made that record false rather than merely dated.

Terra is retired. The review path already refuses any argv that mentions it
(`factory/scripts/forge_cli/review.py`), so the harness simultaneously banned
the model in one lane and prescribed it in another.

GPT-6 is now reachable. Both `gpt-6-sol` and `gpt-6-luna` were probed
read-only through the companion before anything was wired; each resolves.
Neither probe distinguished its variant in the reply, so what is established is
that the ids are accepted, not that the two are measurably different models.
That distinction is recorded here deliberately rather than assumed away.

An accepted decision that contradicts the shipped tree is not a documentation
lag: `plan save` validates `decisions_reviewed` against the active set, so every
future plan would have had to keep citing routing that no longer exists.

## Decision

Native role routing moves to GPT-6 in three lanes:

- `gpt-6-luna` at `max` — routine implementation, automated tests, diagnosed or
  review fixes, documentation edits, mechanical refactors. Roles: `coder`,
  `frontend`, `lite`, `refactorer`, `tester`, `worker`.
- `gpt-6-sol` at `medium` — read-heavy codebase exploration and dependency
  tracing. Role: `explorer`. This replaces the retired Terra lane, and it drops
  from `high` to `medium` because tracing is read-heavy rather than
  hard-thinking work.
- `gpt-6-sol` at `high` — planning, decomposition, difficult diagnosis,
  independent cold-read grills, and final functional checks. Roles: `architect`,
  `debugger`, `docs-decomposer`, `functional-checker`, `griller`, `performance`,
  `planner`, `planner-high`, `security`.

The formal review stays Codex-only on `gpt-6-sol` at `high`. The retired-model
guard stays exactly as it is and continues to refuse any argv containing
`terra`; its refusal tests keep the literal on purpose.

No Forge lane selects Luna at `low`.

## Consequences

A difficult diagnosis still returns its edit to the Luna lane, so the split
between deciding and typing is unchanged; only the model family and the
exploration effort move.

The autoreview skill is externally maintained and still defaults to
`gpt-5.6-sol`. Because the review now passes `--model` explicitly, its
access-retry is reachable only when the account cannot reach `gpt-6-sol`, in
which case the review would fail outright anyway. That reasoning is recorded
beside the constant so it cannot silently rot again.

Exploration at `medium` is the one quality tradeoff accepted here. If read-only
tracing starts missing dependencies that `high` would have found, raise that
single lane rather than the whole registry.

Historical records are left alone: superseded decisions, completed plans, and
specs that describe past runs keep their original model names, because
rewriting them would falsify what was actually decided and run.
