---
status: accepted
confirmed_by: "vrknetha"
date: 2026-08-05
stories: [PH-4]
---

# Responsive Proof Without A Browser

## Context

PH-4's last acceptance criterion says the bundled example "reads correctly at
desktop, tablet and mobile widths". As written that is prose: nothing fails when
it stops being true. The board already has breakpoints at 900px and 620px and a
viewport meta tag, and no test touches any of them.

The obvious proof is a headless browser. The project-hierarchy spec forbids it in
the same breath as the rest of the board's shape: no new database, UI framework
or build step, one self-contained HTML file. A browser is a heavier dependency
than any of those, and it would be vendored into every client repo. Screenshot
diffing is worse still — not deterministic across machines, and a rendering
difference is indistinguishable from a regression.

The competing risk is real: a deterministic proof that never opens a browser
cannot see that a layout looks wrong. Claiming otherwise would put a judgment
call behind a gate that only checks structure.

## Decision

"Reads correctly at three widths" is proven in two halves, and the split is
explicit about which half proves what.

**Deterministic, in the test suite:** the breakpoints exist, and at each width
the content that width must show is present and reachable — not removed, not
clipped by an overflow rule, and not dependent on a hidden element. This is a
structural check on the served page and its CSS, and it is what CI enforces.

**Judgment, in the phase-7 functional check:** the story is `user_facing: true`,
so the functional check already runs. Whether the page actually *reads* well at
each width is answered there, by something that renders it.

No browser dependency is added to the harness or to any client repo.

## Consequences

- The gate catches the failure it can actually catch — content dropped or
  clipped at a breakpoint — and does not pretend to catch visual quality.
- The functional check gains a named responsibility instead of an implicit one,
  so "looks right on mobile" has an owner rather than being assumed.
- Cost accepted: a layout that is structurally intact but visually poor passes
  CI. That is the honest boundary of a structural test, and the functional check
  is where it is caught.
- If the board ever grows a genuine need for rendered assertions, that is a new
  decision with a named consumer — not a dependency added quietly under this one.
