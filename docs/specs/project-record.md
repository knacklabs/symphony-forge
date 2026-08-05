---
slug: project-record
title: The project knows what it built
status: confirmed
saved: 2026-08-05T21:20:10+00:00
---

# The project knows what it built

## Why

A read-only audit of this repo on 2026-08-06 measured what the in-repo record
actually covers. The story spine is good — roadmap story, plan, decomposition,
stages, verify/tests/reviews, outcome, archived to `.factory/history/<issue>/`
— and it covers roughly half the work.

- **30 of 188 substantive commits (16%) trace to nothing** but a commit
  message; 22 of those touch product code. Among them are two of the largest
  features in the repo: the lifecycle board itself and the client-signoff gate.
- **30 of 36 merged PRs are invisible in-repo.** A search for PR numbers across
  `plans/`, `.factory/` and `docs/` returns nothing. The only link between a PR
  and its work is the GitHub merge commit, which does not survive the account.
- **`quickfix.files` is empty in 29 of 29 real records.** `claim_files` is
  reached only on the planning-lock denial path, so an active story never
  claims, and `PLANNING_WRITE_OK_FILES` exempts common targets outside one. The
  five-file budget that makes the escape hatch *bounded* therefore never binds,
  and the ledger cannot say what an ad-hoc change touched.
- **Two shipped stories have no outcome at all** — FORGE-INIT-1 and
  harness-v2-wedge have `.factory/history/` directories but never appeared in
  `plans/roadmap.json`. `events.jsonl` independently shows 5 `shipped` events
  for 7 history directories.
- **`.factory/events.jsonl` holds 314 committed events across 29 types and has
  no reader.** `pr_ready` slices it per story; the board reads only quickfix
  `done` events. The cross-story spine already exists and nothing surfaces it.
- **`plans/roadmap.json` has lost items to merges twice**, leaving "reattach the
  epic the merge dropped" commits behind. Decision 0022 made the ledgers
  conflict-free directories; the roadmap stayed a single mutable file.

This is not one repo's housekeeping. Symphony Forge is vendored, so every
client inherits the same capture model — and `forge adopt` exists for repos
with existing work, so a client's record begins mid-history with everything
before it invisible.

## Behaviour

### The record answers "what happened", from the events already committed

`forge history` reads `.factory/events.jsonl` and prints it filtered by story,
event type, or date range. No new capture: the data is committed today and has
no reader. This lands first because it makes every remaining gap visible.

### Work outside a story leaves the same shape of trace

A quickfix window records what it touched, not only why. **Recording and
bounding are separated**, because they answer different questions: every path
that authorizes a product write during an open window records the file against
it, while the five-file budget still binds only where the quickfix is itself
the authorization. Inside an approved story a task's write scope already bounds
the work, and a second competing budget there would refuse honest edits; but
the window must still say what it touched.

A merged PR is linked to the work it shipped by **one** home, not three: an
event in `.factory/events.jsonl`. It is the only ledger that is cumulative,
committed, never pruned, and already spans stories — so the link survives a
clone with no remote and `forge history` surfaces it without a second reader.

### The record states where it begins

`forge init` and `forge adopt` write a boundary marker: the date, the commit,
and how many commits precede it. The board reports "record begins here; N
commits precede it" rather than implying the project started at adoption.
Missing history is stated, never reconstructed — a fabricated record reads as
authoritative and is worse than an acknowledged gap.

### Shipped stories keep their outcome

A story that reaches `pr_ready` without an outcome is already refused. The two
that predate that gate are **marked as predating it, not backfilled**. An
outcome states what someone can now do, written by whoever shipped it; deriving
one from a plan months later reconstructs intent and presents it as record.
Marking them costs a line and stays true.

## Acceptance criteria

- `forge history` answers what happened for a given story, event type, or date
  range, reading only `.factory/events.jsonl`, and its output names the events
  that have no story attribution rather than hiding them.
- A quickfix window records every product file it claimed, including inside an
  approved story where claiming does not happen today; and a window that
  exceeds its budget is refused where the quickfix is the authorization.
- Every shipped story in `plans/roadmap.json` has an outcome, or carries an
  explicit marker that it predates the outcome contract. No outcome is written
  after the fact for work whose author did not state one.
- The durable record links a merged PR to the work it shipped, and that link
  survives a clone with no GitHub remote.
- `forge init` and `forge adopt` write a boundary marker naming the date, the
  commit, and the count of preceding commits; the board reports it rather than
  implying the record is complete.
- Nothing in this story invents history. Where a record is missing and cannot
  be reconstructed from committed evidence, the boundary marker says so.

## Boundaries

- No new database, service or index. The record is files in the repo.
- No rewriting of git history and no synthesised outcomes for past work.
- `forge history` reads; it never writes.
- The roadmap's merge fragility is named here but fixing it (making
  `roadmap.json` conflict-free the way 0022 made the ledgers) is a separate
  decision, not smuggled into this story.
- Cross-worktree board visibility and task depth on cards are a different
  capability — the board's view, not the record's completeness.
