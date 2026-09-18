---
status: accepted
confirmed_by: "Nandu (chat, 2026-09-18)"
date: 2026-09-18
stories: []
---

# One task journal, read by both agents

## Context

The coordinator's reasoning reached the worker only through a brief composed
from the decomposition, the decisions and lessons matched by path globs; the
worker's side came back as a summary. On WF-BIO-1 T4 two instruction lists
never arrived because their globs missed the task's scope and nothing said
so; the worker never saw the full review output, the triage evidence, the
host's test failures, the user's decisions in chat, or what earlier rounds
fixed or rejected; a worker that exited at 01:41 was believed running until
02:26. The review brief was composed from the whole story and grew every
round (the lesson ledger once per task section, rulings six times, the plan
twice) until the reviewer had to be split into one-file groups.

## Decision

Every task has one append-only journal, `journal.jsonl` beside its other
evidence, rendered to `journal.md` on every append. Entries have a kind and
an actor and are validated: the harness writes contracts, launches, exits,
worker reports, proof output, review generations and scope; the coordinator
writes notes, decisions, triage verdicts, refusals and accepted flakes, all
through `forge journal add`; nothing is hand-written. The delegate brief
carries the standing instructions and everything appended since the worker's
last launch, and names the file for the rest; the worker's report cites the
entry ids it acted on. The review brief carries the reviewed task's journal
beside the diff; other tasks contribute their contracts and sealed identity
only, lessons are one line each with the text left in the tree, and rejected
findings are not repeated as lessons. The journal ships with the task: the
proof commit and the marker commit carry it.

## Consequences

- Nothing the coordinator records can fail to reach the worker without a
  printed reason, and the coordinator reads the worker's exit and report
  from the same file.
- The review brief is a function of the task, not of the story or of how
  many rounds have run; on T4's real inputs it drops from 472 KB to tens of
  kilobytes and the diff fits one prompt.
- A task reviewed under the previous brief re-reviews once after upgrade,
  because the approved-input section it is compared against changed shape.
- Lessons remain the durable cross-task ledger; per-task notes go to the
  journal, so the ledger stops growing with fix rounds.
