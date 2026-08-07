---
slug: workflow-modes
title: A small supervised fix doesn't need the full loop
status: confirmed
saved: 2026-08-07T07:16:50+00:00
---

# A small supervised fix doesn't need the full loop

## Why

The factory loop is built for a bounded feature from a roadmap story: plan,
grill, decompose, verify, three reviews, outcome, ship. That is the right weight
for new capability work, and the wrong weight for the small fix that follows —
the two-line change a reviewer asks for after the PR is up, made while a human
watches the diff. Today the lifecycle is terminal at ship, and afterward the
always-armed planning lock leaves only two doors with nothing between them: run
the whole loop again, or open a trace-only escape hatch that records no review
at all. The planning lock exists to catch *agent drift*, not to distrust a
supervising human — so the supervised small fix is exactly the case the heavy
loop was never aimed at. The harness needs a proportionate lane, and because the
harness is vendored, every client should inherit it.

## Behaviour

A developer can select a lighter **mode** for a change, rather than being forced
through one fixed weight. The default mode is the full loop, unchanged and
mandatory for fresh roadmap stories. A **lite** mode gives a bounded, honest
lane for small supervised work:

- **It is entered deliberately and recorded.** A human opens lite mode with a
  reason and their name; the harness treats that as the authorization, not a
  phrase in a prompt. This keeps a drifting agent from relaxing its own guard.
- **It is bounded.** Lite work is capped in size; a change that outgrows the cap
  is routed back to the full loop, so "lite" cannot quietly become an untracked
  feature.
- **It leaves a durable trace.** What changed, why, and which files it touched
  are recorded against the window — the same question a reader asks six weeks
  later.
- **The fix still passes one review.** Before a lite change lands, it goes
  through a single review pass; nothing ships from lite mode unreviewed.
- **It works after ship.** Lite mode does not require an active story, so the
  common post-PR reviewer tweak is served without re-opening the whole loop.

The existing trace-only escape hatch keeps its current behavior; lite mode adds
the reviewed, bounded profile beside it.

## Acceptance criteria

- A developer can move a small change through a lighter path than the full loop,
  chosen deliberately, without editing gate state by hand.
- Selecting the lighter path is an attributed, recorded act (who, why) that a
  later reader can audit, and it records which files the change touched.
- A change made in the lighter path does not ship until it has passed one
  review with no blocking findings.
- A change that exceeds the lighter path's size bound is refused there and
  directed to the full loop.
- The lighter path is available after a story has shipped, not only during it.
- The full loop remains the default and is unchanged for fresh roadmap stories;
  the pre-existing trace-only hatch is unchanged.

## Boundaries

- Not a deploy or post-merge phase — this is about authorizing and recording a
  fix, not shipping or releasing it.
- Not a change to what the full loop requires, nor to the one-review-run
  contract; the lighter path reuses the same review, it does not invent a new
  one.
- The lighter path ships present-by-default in the vendored harness but is a
  pinned capability a client may remove (like any harness pin) if a stricter
  shop wants only the full loop.
- Which model performs a delegated fix, the exact commands, and the size bound
  are implementation choices for the plan and the governing decision, not this
  spec.
