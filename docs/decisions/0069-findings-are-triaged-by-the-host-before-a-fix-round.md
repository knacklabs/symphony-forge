---
status: accepted
confirmed_by: "Nandu (chat, 2026-09-13)"
date: 2026-09-13
stories: []
---

# Review findings are triaged by the host before a fix round

## Context

WF-1 T5 (2026-09-12/13) took six three-lens reviews and eight fix rounds for
one task. The record of those rounds shows one habit behind most of them: the
coordinator read the review's findings and delegated them to the worker as
written, one file at a time.

- Review 1 raised 15 blocking findings. Eleven were wrong, and died only when
  the coordinator opened the code the diff called: `request()` already threw on
  a non-2xx, so the multipart helper did not "return errors as data"; the
  write DTOs accepted no `siteId`, so the screens could not "omit" one.
- Reviews 3 to 6 each raised the same class in a different file: freeze the
  form while a write is unresolved, reconcile after a lost response, validate
  the trimmed value. The worker fixed the one file the lesson named, and the
  next review found the next file. The coordinator wrote at 05:11 UTC: "I
  wrote each lesson against the file the review named, when I could have swept
  every write form myself and handed Codex the complete list the first time."
- With no way to record a factual refutation, each one went into the lessons
  ledger, which is meant for reusable knowledge and now carries 96 entries.

The reviewer sees the diff and cannot see more without losing the diff. The
coordinator sees the whole repo, has the time between review and delegate, and
is the one composing the fix round. The check belongs there, and it was being
skipped.

## Decision

Between a review that records blocking findings and the fix round that
answers them, the coordinator triages every finding and records the triage:

- **real**: the `file:line` that proves it, and every place in the repo where
  the same contract applies and still fails, so the fix round closes the class
  and not the one file the review cited; optionally what must not change.
- **not a defect**: the `file:line` that refutes it and why. This is
  `forge review --reject` on evidence rather than on a citation; the finding
  moves to `rejected_findings`, is ledgered so the next review carries it, and
  appears in the PR body for the human.

`forge review <id> --triage` records it, checking that every cited line exists
in the worktree. The fix brief renders the triage beside each finding, and
marks a finding without one as an unverified claim. `forge delegate` prints a
warning naming how many findings are untriaged. The review's own next-step
hint says to triage first.

This is not a gate. The owner chose enforcement by visibility over refusal: a
gate that acts on an unverified claim is what made the review loop expensive,
and adding another refusal is not the remedy. The launch proceeds; the gap is
said out loud where the coordinator is looking.

## Consequences

- A wrong finding costs the coordinator minutes, not the worker a round.
- A real finding reaches the worker with its full instance list, so one fix
  round closes a class. T5's rounds 5 to 8 were one class each.
- Contradictions between a review and its own earlier ruling surface at the
  coordinator's desk on the second round, while the code is open, rather than
  as a decision record on the fifth.
- The lessons ledger stops being the channel for round-to-round fix
  instructions; the triage record is.
- Cost: five to ten minutes of coordinator reading per round.
