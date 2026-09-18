---
status: accepted
confirmed_by: "Nandu (chat, 2026-09-18)"
date: 2026-09-18
stories: []
---

# A task's proof runs once per tree

## Context

One implement, review, close cycle ran the project's full suite four to five
times on the host before CI ran it again. The worker ran the verify commands
and required tests while it worked, and `verify.py` on top. The coordinator
ran the suite by hand after committing, then `verify.py` again because the
review refused without a `verify.json`, and typed a `tests.json` record from
the worker's report. `task close` then ran the same verify commands and every
required test once more and recorded nothing reusable. On WF-BIO-1 T4
(2026-09-17) that was nine close attempts of ten to twenty-four minutes each,
the review three to four minutes of each; three to four hours of the task's
wall clock was the same tests re-running. The two command lists even
differed: `.envrc` named web and playwright, the decomposition named the four
suites, so build, lint and the API suite ran under both.

## Decision

`task close` runs the contract's verify commands and required tests once and
records the run as the task's `verify.json` and `tests.json`, bound to the
product tree digest and the contract that named the commands (`proof_key`).
A close over the same tree and contract reuses that record and runs nothing;
a changed tree or contract runs once more. Close commits the two files as
its own commit before the review, so the commit the marker names already
holds them and every sealed-state reader finds the proof there.

The worker still runs the same commands while it works, to fix what fails;
its run is not the proof. Nobody runs `verify.py` or the suite by hand before
close for a task-level run. The measurement lives in `verify.json`. The
worker's own automated record keeps its narrative; its commit binds it to a
tree, and after a fix commit the brief refuses the stale binding, which the
coordinator used to cure by re-recording the same report at every commit.
The proof re-binds the record to the measured commit (`worker_commit` keeps
the original, `bound_by: stage-proof`), and only while no review covers the
tree: the brief renders the record verbatim inside its approved-input
section, so an edit after a review would stale that brief. A task without
a record gets the harness record, except a user-facing task, whose record
must attest the design skills.

## Consequences

- Per fix cycle: the worker runs once, the harness runs once, CI runs once.
- A metadata-only commit (evidence, a converted brief, a lesson) costs no
  test minutes at close.
- `verify.json` gains `recorded_by`, `tree_digest`, `proof_key`,
  `required_tests` and `test_id_misses`. Readers use `ok`, `commit` and
  `status` as before.
- `verify.py` remains the story-level and standalone tool; the `.envrc`
  phases describe that run, the decomposition's `verify_commands` the task's.
- Required tests still run one process per id after the suites; reading them
  from the suites' own reports would need a runner-specific reporter and is
  left open.
