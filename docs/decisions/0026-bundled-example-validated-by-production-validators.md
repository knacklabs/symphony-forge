---
status: accepted
confirmed_by: "vrknetha"
date: 2026-08-05
stories: [PH-4]
---

# Bundled Example Validated By Production Validators

## Context

PH-4 requires a bundled example project that "passes the production validators
and reads correctly at desktop, tablet and mobile widths". No example exists
today: the board's tests build a temp repo with `forge init` and hand-seed state
inside the test, so nothing demonstrates the board against a realistic project,
and nothing catches a board that renders blanks where a hierarchy should be.

Three forms were available, and they fail differently:

- **A test fixture** — seeded JSON shaped to make assertions pass. It drifts from
  the gates it is meant to demonstrate: PH-1/2/3 tightened brief, spec, epic and
  story capture, and a fixture written against the old shape keeps passing
  because nothing production ever reads it.
- **Generated at test time** — build the example by running the authoring
  commands. That proves the generator works, not that the page reads correctly,
  and it leaves nothing a human can open.
- **Checked-in source** — a minimal repo-shaped tree a person can actually serve.

## Decision

The bundled example is **checked-in source, validated by the production
validators**.

> **Correction, 2026-08-06 (PH-4 implementation).** This decision originally
> added "and served by the flag that already exists: `./forge board --repo
> <example>`". That is wrong and was never implemented: `board.py` resolves
> `index.html` from the `--repo` TARGET, so a data-only tree has no page to
> serve. Making it work needs the page to resolve from the running code —
> deferred as **D-0005**, because PH-4's approved plan scopes that task to
> example/tests/docs and declares CLI/ops unchanged by design. The example is
> validation-only until D-0005 is taken up. The confirmed substance of this
> decision — checked-in source that the production validators must accept —
> is unchanged.

It is a minimal repo-shaped tree — `docs/product/BRIEF.md`, one confirmed
capability spec, and a `plans/roadmap.json` carrying two epics, at least one
blocked story and at least two startable ones — chosen so the frontier, the
blocked explanation and the epic breakdown each have something real to show.

A test runs the **production** brief, spec and roadmap validators over it: the
same functions `record_signoff.py`, `forge spec confirm` and the roadmap
authoring routes call. Not a parallel fixture-only check.

## Consequences

- The example fails when a capture contract changes, which is the point: a
  tightened gate breaks the build rather than silently leaving a stale demo.
- A field the capture gates would refuse cannot reach the screen as an empty box
   — the failure the project-hierarchy spec names directly.
- It becomes a real onboarding artifact: a new engineer runs one command and sees
  a populated hierarchy instead of an empty board on a fresh repo.
- Cost accepted: the example is maintained content. It is deliberately minimal to
  keep that cost small, and CI validation makes the maintenance forced rather
  than forgotten.
- It does not replace the existing temp-repo board tests, which cover live state
  transitions a static example cannot.
