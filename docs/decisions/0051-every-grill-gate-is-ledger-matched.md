---
status: superseded
confirmed_by: "Nandu"
date: 2026-09-05
stories: [upgrade-preserves-doc-contracts]
superseded_by: 0067-rounds-rebind-to-their-gate
---

# Every grill gate is ledger-matched and floors at one round

## Context
<!-- Why this decision was needed; the forces at play. -->

Decision 0048 required grill rounds to match the `AskUserQuestion` ledger that
only `post_tool_use.py` can write, and gave each gate a floor. It applied that
to four gates. `GATE_ROUND_FLOORS` held `spec`, `requirements`, `plan` and
`task`; the provenance check ran under `if args.gate in GATE_ROUND_FLOORS`, so
`signoff` and `epics` were not merely unfloored — they skipped the check
entirely. Both recorded a `pass` with an empty `rounds` list and satisfied
their downstream gate.

The two that escaped are not minor gates. `signoff` guards the client->PM
handover that every later gate treats as settled, and `epics` guards the
roadmap import. Both were passable with nothing behind them.

The cause was structural rather than an oversight at one line. The six gates
were enumerated in eight places — the runner's label map and its two
hand-written artifact lookups, the recorder's floors, its `--gate` choices, its
story-scoping tuple and its evidence filename branch, `forge.py`'s own choices
list, and the schema's prose — with nothing holding them in agreement. They
drifted in two directions at once: the runner could locate two of six, so four
gates could not be released through the ledgered launcher at all, and the floor
map covered four of six.

A floor was also being read as a target. `spec` and `plan` sat at two rounds,
which invites stopping at two. The floor is the point below which a grill is
not evidence; convergence is the actual bar, and no number expresses it.

## Decision
<!-- What was decided, in one or two sentences. -->

**All six gates are ledger-matched, each with a floor of one round.** The
provenance check is unconditional — there is no gate it can skip. `signoff` and
`epics` therefore answer to the same rule as the rest: rounds matched against
the ledger, no round reused across grills, `frontier_empty` attested on the
last one. This extends 0048's provision to the two gates it missed and lowers
`spec` and `plan` from two rounds to one; every other provision of 0048 stands.

**One round is a floor, never a target.** Stated once in the gate table and
carried verbatim into the cold-read brief and into the recorder's refusal:
grill until a round comes back clean and the next one stays clean.

**A gate is defined in exactly one place.** `grill_gates.GATES` holds one row
per gate — where its artifact lives, its floor, whether it is story-scoped, and
where its evidence is filed — with no optional fields. The runner, the
recorder, the CLI and the test suite derive from it. A gate that can be
recorded but not run, or gated but unfloored, is no longer a state this harness
can express.

**The plan gate interrogates the draft.** Plan save refuses without a passing
grill, so the saved copy cannot exist at grill time; `--file` names the draft
and the recorded plan is the fallback.

## Consequences
<!-- What follows: tradeoffs accepted, doors closed, work implied. -->

- `signoff` and `epics` are now recorded by the coordinating Claude session
  rather than by a read-only Codex run on its own, because a round must be a
  question actually put to the human. This is the substantive cost of the
  decision and it is accepted: a gate nobody was asked about was not a gate.
- All six gates can be released through `./forge grill run`, so every grill is
  ledgered with a pid and a dead one is reported rather than inferred from
  silence. Four gates previously had no such path.
- `spec` and `plan` drop from two rounds to one. This is a loosening of the
  number and a tightening of everything else; the number was never what made
  those gates hold, and treating two as sufficient was the failure mode worth
  removing.
- Grills already recorded stay valid. `require_grill` checks verdict, commit
  stamp, freshness and digest, never the round count, so raising a floor binds
  at record time only and does not retroactively break a repo that has already
  passed a gate. Any future floor change inherits that property.
- Adding a gate is adding a row. The eight-copy enumeration that produced this
  defect is gone, and the row cannot be declared with a column left blank.
