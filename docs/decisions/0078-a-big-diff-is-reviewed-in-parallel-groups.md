---
status: accepted
confirmed_by: "Nandu (chat, 2026-09-15)"
date: 2026-09-15
stories: []
---

# A big diff is reviewed in parallel groups, each retried on its own

## Context

Decision 0069 made the review one helper call that publishes one immutable
generation. The helper splits any prompt over 512 KB into chunks and runs them
one after another inside that call. On WF-1A T1 (2026-09-14) a 900 KB diff
became four chunks of twenty to forty minutes each: over an hour per review
round, where the three parallel lenses it replaced took minutes. One chunk
came back truncated and the whole hour was refused; nothing inside the call
could be retried alone, and the lockfile alone was a chunk's worth of bytes
nobody needed to read.

## Decision

Forge splits before the call, and only when the helper would split anyway.
The product diff's files are dealt into the fewest groups whose prompt
(brief, dataset and diff) fits under the helper's limit. Each group gets its
own review worktree and one three-lens Codex run; all groups are released
together and joined. A group's bundle is only its files' diff, but its tree is
the whole task tip, so a verdict on a contract whose change sits in another
group is read from the tree (0076), never guessed; the group's brief says
which files it holds and which it must read. A diff that fits in one prompt
is one group: the same single call as before.

A group whose result would be refused at record time is re-run alone, at most
twice, with the refusal's cause turned into one instruction in its brief. The
raw output of every attempt stays in the control directory. After the second
retry the review stops and names the cause.

The group results are merged into the exact shape the helper uses for its own
chunks: one finding per location and title, each body prefixed with its chunk
label, the worst verdict per contract winning, every pass preserved. The
recorder, the projection, closeout, the board, triage and rejection read that
shape unchanged; no schema changes. 0069's "one helper call" is amended to
"one immutable record": the record is still one generation with one selected
pointer.

Lock and generated files (`pnpm-lock.yaml`, `package-lock.json`, `yarn.lock`,
minified and map files, snapshot and generated directories) are put back to
the task base in the review tip. They ship, they stay in the reviewed scope
and the stamp; their bytes are not sent to the reviewer.

## Consequences

- A WF-1A-sized diff runs as two or three groups at once; the round takes as
  long as its slowest group instead of the sum of its chunks.
- A malformed group costs one group's time, with the cause in the retry
  brief, instead of the whole round.
- Small tasks are unchanged: same prompt, same single call, same record.
- Found by the group run and fixed here: on the combined path a partial
  or missing contract verdict raised no blocking finding, so the stage was
  stamped clean and `task close` sealed it. The quality lens now carries
  one `plan-contract-partial|missing` blocker per such verdict, fail-closed,
  as the per-aspect recorder always did; `forge review` reports what was
  recorded, not what was projected.
- Found by the new close test and fixed here: after a post-seal fix,
  `task close` reopened, reviewed and re-sealed, but the seal's pre-seal
  proof check rendered the brief section from the previous marker's
  commit and refused the resealed task. A pre-seal check now reads the
  current inputs, as the brief it checks was written from.
- A verdict record is forge's to scope, a defect is the helper's. The
  helper sets aside any finding located outside its bundle; a set-aside
  verdict record (a contract read in another group's file, or in
  unchanged code, 0076) is validated and counted by forge, and its trust
  check is exact: kept findings plus set-aside records are the raw
  findings. A set-aside defect still refuses the result. Found on
  WF-BIO-1 T2 (2026-09-16), where a two-file docs group could never pass.
- The reviewer never sees a lockfile diff; `package.json` changes are still
  reviewed. A folder named `generated/` is treated as generated output.
- `FORGE_REVIEW_SPLIT_BYTES` lowers the split point for probes and tests.
