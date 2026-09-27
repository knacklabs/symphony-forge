---
status: superseded
superseded_by: 0093-lean-forge-rebuild
confirmed_by: "Ravi"
date: 2026-08-09
stories: []
---

# Gate A requires a PR to declare every completed work record

## Context

FORGE-BOARD-1 shipped Gate A (`check_pr_ticket.py`): every PR must tie to a
complete on-board ticket. Its original contract was "exactly **one** declared
work record resolves" — one roadmap story (done-flip with added history) or one
work window (an added `plans/quickfixes/*.json` done record), named by a
`feat/<key>-` branch or a `Ticket:` line.

That "exactly one" is too narrow for a real pattern: a single review-driven
effort legitimately spans **more than one window**. You do the work in a lite
window, close it, get an independent review, then reopen a second window to
apply the review's fixes — all in one PR. Under "exactly one", such a PR could
only pass by declaring **one** of its windows and leaving the other silently
undeclared. That is a traceability hole (a completed work record with no
declaration) dressed up as a passing gate.

## Decision

Gate A now requires a PR to declare **every** work record it completes, not
exactly one. Concretely: let `completed` be the set of stories done-flipped
(with added history) plus window done-records added in `base..HEAD`. The gate
passes iff `completed` is non-empty **and** every member of `completed` is
declared (its key on a `Ticket:` line, or the story key inferred from a
`feat/<key>-` branch). A completed record with no declaration fails the gate;
extra declarations that resolve to nothing are ignored.

## Consequences

- **Stronger, not looser.** Single-record PRs behave exactly as before; the only
  new failure is a completed-but-undeclared record — the loophole is closed.
- **Multi-window PRs are first-class.** The review-then-polish flow (work →
  close → review → reopen → fix, one PR) passes by declaring both windows, and
  the PR stays fully traceable.
- Consistent with 0009 (frozen gate integrity): the harness evolves its own gate
  through a decision; vendored clients still receive it frozen between
  vendorings.
- Implementation: `check_pr_ticket.py` resolution logic + its self-tests
  (`test_gates.py`, the `pr_ticket` cases) updated together; the failure message
  now names the undeclared records.
