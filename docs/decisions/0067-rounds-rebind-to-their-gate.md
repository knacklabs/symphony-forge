---
status: accepted
confirmed_by: "Ravi"
date: 2026-09-11
stories: [GATES-1]
supersedes: 0051-every-grill-gate-is-ledger-matched
---

# A question round belongs to its gate and story, and may be reused there

## Context

Decision 0051 made every grill gate ledger-matched: a recorded pass must cite a
real AskUserQuestion round, and no round is reused across grills. That stopped
passes being recorded against questions nobody asked, which was the right
problem to solve.

The rule is enforced by consuming rounds found in previous grill records, so a
round is spent the first time any pass claims it. In a per-task flow that turns
out to punish the ordinary case. A gate is re-recorded whenever its findings are
resolved, its contract is corrected, or an earlier gate moves, and each
re-recording demands a brand new question. When the frontier is genuinely closed
there is nothing left to ask, so the question gets invented purely to satisfy the
recorder.

On one client task that produced roughly fifteen owner questions, several of
which existed only because a pass could not otherwise be recorded. Asking a
person to choose between options that do not matter is worse than not asking:
it spends their attention and teaches them that the questions are noise.

The implementation also cannot express what 0051 intends. Ledger rows carry the
question, its options, the answer and a session id. They carry no gate and no
story, and a globally recorded gate receives no issue at all, so "reused across
grills" can only be approximated by consuming rows globally.

## Decision

A question round belongs to the gate and story it was asked for, and may be
reused when re-recording THAT gate for THAT story. It is never reused across a
different gate, a different story, or a different task.

Provenance is already recorded, in where the evidence lives, so nothing new is
stamped onto a round. A ledger round is written into the active story's
directory, and a recorded pass is written to a path already unique per gate,
story and task. Reuse therefore follows from location: a pass does not treat its
OWN previously recorded rounds as spent, which is what makes re-recording free,
while any other pass still spends them, which is what keeps a round from
crossing to a different gate, story or task.

No round written before this decision changes meaning, because no round changes
at all.

The floor 0051 set is unchanged: every gate still requires at least one real
round, and a pass still cannot be recorded against a question nobody asked.

## Consequences

- Re-recording a gate after resolving its findings no longer manufactures a
  question, which is the only case this relaxes.
- Neither the ledger nor the round schema changes. The rule lives entirely in
  the recorder's consumption walk, which reads provenance from where evidence is
  already written, so there is no legacy class and no migration.
- 0051 was thought to leave a hole where a globally recorded gate could consume a
  round asked during another story. It does not: the recorder only ever reads the
  ACTIVE story's rounds plus the global ones, so another story's rounds were
  never reachable. An attempt to close that non-existent hole by making
  non-story-scoped gates read only global rounds broke the ordinary flow instead,
  because spec, signoff and epics are recorded while a story IS active and their
  rounds live in that story's directory. Nothing changes for those gates.
- 0051 is retired. Its intent, that no gate is satisfied by a question nobody
  asked, is carried forward intact.
