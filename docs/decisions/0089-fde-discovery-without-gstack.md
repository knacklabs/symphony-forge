---
status: accepted
confirmed_by: "Ravi Kiran Vemula"
date: 2026-09-24
stories: []
---

# The Forge skill owns discovery as an FDE; gstack and direnv are removed

## Context

Forge is mostly run by forward deployed engineers who were never trained in
product work, for customers who often don't know what to build. Discovery was
delegated to gstack's office-hours skill, a large third-party bundle whose
only other ties to Forge were a migrate command, doctor checks that clone and
install it, ignore rules, and a direnv requirement that exists only to pin
gstack's store. Nothing else in Forge calls a gstack skill.

## Decision

The Forge skill itself makes the agent act as an FDE: it finds the real
problem by asking one question at a time about what actually happened, offers
two to four options including not building and the smallest testable slice,
picks by a simple payback rule, and writes a success measure (metric,
baseline, target, check date) into the spec so the result is checked after
ship. It explains in one line why it asks each question, so FDEs learn
product thinking over time. impeccable remains the tool for product UI design.

gstack is removed from Forge: its command, doctor checks, ignore rules,
settings and docs. direnv is no longer required; Forge reads `.envrc`
directly. The project's recorded gstack history is archived under
`docs/context/`.

## Consequences

- Discovery has one owner inside Forge, and no third-party bundle is needed.
- The skill stays lean (asking rules, discovery questions, payback rule);
  worked examples, a question bank and a customer call script live in a
  reference file the agent opens when needed.
- Questions about facts offer neutral choices with no recommended answer, so
  the customer's evidence is not led; questions asking the human to decide
  keep a recommended option first.
- Amends 0012: project history lives in decision records, `docs/context/`
  and `docs/memory/`; `.gstack/` is no longer a project memory location.
- Client repos keep any existing gstack ignore and `.envrc` lines; they are
  harmless and protect people who still use gstack personally.
- Developer setup loses the direnv step.
