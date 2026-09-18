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

The proof is written to the same file. Every verify command and required
test records its exit, elapsed time and output tail as a `proof` entry, so a
failure is read from the record and not from a scrollback. A command that
fails once and passes on an immediate re-run is a `flake` entry carrying its
first output; the seal refuses it until the test is fixed or the coordinator
records `flake-accepted` for that command with a reason (T4 re-ran one
2-second cleanup grace four times, blindly). On Windows the proof refuses to
start below the free commit memory `harness.yaml` sets (`proof:
min_free_memory_gb`), instead of dying twenty minutes in.

The worker asks for what it cannot run. A proof the sandbox cannot execute
(on Windows the profile caches and store-linked `node_modules` are
unreadable by its restricted account) is requested with `forge proof run`;
the harness waiting on that worker runs exactly that declared command on the
host, writes the result under `.forge-cache/` where the worker reads it, and
journals it. Nothing the worker types runs on the host. Worker caches live
under `<worktree>/.forge-cache/`, excluded from Git.

Scope is declared before the write. `forge stage amend-scope --path <p>
--reason ...` records a path the coordinator has decided belongs to the task;
the next write is admitted, the brief shows it and the measurement honours
it, with no refusal, signal and resume between (T4, 14:03). The launch record
carries the effective scope and the admission compares against it.

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
- `forge next` names the worker's last exit code and what its report cited,
  from the journal, before proposing the next action.
- A flake is never shipped silently: it is fixed, or accepted by name with a
  reason that the journal keeps.
