---
status: proposed
confirmed_by: ""
date: 2026-09-03
stories: []
---

# Each task's three-lens review is its recorded proof

## Context

Decision 0001 (D6) and 0007 set ONE branch-wide autoreview at the story's
review phase as the only review gate and the sole producer of
`.factory/reviews/*`, with per-stage local reviews recording nothing. Decision
0047 then moved shipping to per-task PRs: each task seals and merges on its own
before the next task starts. Under that model a story-level review that runs
only at closeout arrives after every task has already merged — so a task merged
through its own PR carries no recorded review at all. In practice R1-FOUND-1
already recorded each task's review at its seal; the documents lagged the
practice.

Observed in R1-FOUND-2A (2026-09-03): T1 and T2 merged with no reviews, verify,
or tests recorded; the board showed no proof for the story; the coordinator
had run an autoreview pass but, following "local reviews record nothing",
never recorded it. Separately, the adapter's wording for 0011 ("Review is
Claude's — run autoreview DIRECTLY") read as Claude reviewing inline. 0011's
intent was only to forbid the NESTED companion wrapper (a Codex job re-loading
the same skill one level deeper): the autoreview skill invoked with
`--engine codex` is still Codex doing the review — the coordinator merely
invokes it directly and watches it.

## Decision

Each task gets exactly ONE three-lens autoreview pass — quality, performance,
security — run by Codex through the autoreview skill (`--engine codex`),
invoked by the coordinator and never as a nested companion job (0011). It runs
once, after the task's implementation is complete and verified and before
`forge task pr-ready`; intermediate fix iterations do not re-run or record it.
Its three artifacts are recorded as that task's proof
(`.factory/stories/<key>/reviews/{quality,performance,security}.json`),
alongside the task's `verify.json` and `tests.json`. The coordinator releases
the pass with `forge review <task-id>`, WATCHES it like every Codex release,
and on findings drives Codex fixes and re-reviews until clean. The story-level
closeout re-verdicts the union of contracts across the shipped tasks (as
R1-FOUND-1's did) rather than being the first and only review.

This CLARIFIES 0001 D6 and 0007 for the per-task-PR model; it does not
reintroduce nested reviewers, and it does not change what the three lenses
check.

## Consequences

- A task cannot reach `pr-ready` without its recorded three-lens proof; the
  board shows proof per task as tasks ship, not only at story closeout.
- "Per-stage local reviews record nothing" now applies only to intermediate
  iterations; a task's final pass IS recorded.
- The WATCH rule names the review release alongside delegate and grill.
- `forge review <task-id>` is the single command that pins the ref, scopes the
  diff, composes the brief, releases Codex, and records all three artifacts —
  the coordinator no longer hand-assembles the skill invocation.
- Follow-up: CI should require a task PR to carry its completion marker and
  recorded proof, so a task merged outside this flow cannot silently skip it.
