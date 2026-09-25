---
status: accepted
confirmed_by: "Ravi Kiran Vemula"
date: 2026-09-25
stories: []
supersedes: 0069-combined-review-generation
---

# A task closes on a green CI run and a clean review

## Context

Closing a task has become the slowest and most fragile part of Forge. Close runs the full
test suite locally, binds the result to a tree digest, a contract key and an environment
identity, commits it as a separate proof commit, then runs a review that is wrapped in
three-lens markers, per-contract verdict records, immutable review generations, a selected
pointer and a "reviewed meaning" identity. Each of those bindings can go stale on its own,
and most close failures in recent stories were the bookkeeping disagreeing with itself,
not the code being wrong. The same full suite then runs again in CI on the pull request,
which is the check that actually guards trunk. Grill records and Lite windows carry the
same kind of byte-level binding for the same reason.

The owner set one limit on simplifying this: "Lets not skip the review the chances of
regressions are higher, we fix one but regress more." Review stays mandatory and looped;
what goes is the machinery wrapped around it.

## Decision

A task, and every Lite fix, is done when three things are true: its pull request is open,
the full CI suite on that branch's latest commit is green, and the latest Autoreview round
over the branch has no P0 or P1 finding.

- **Review stays mandatory.** Every task and every Lite fix gets an Autoreview run with
  Forge's review instructions: the task's scope, the plan's "Done when" and acceptance
  criteria as plain instructions, and the test-audit rule. P0/P1 findings block; the
  worker fixes them and Autoreview runs again, until a round has none. P2/P3 findings are
  listed in the PR as advisory. Forge records one small result per round: the commit
  reviewed, the findings and the status. Host triage of findings (0075) stays.
- **CI is the proof.** Close no longer runs the suite locally, records proof receipts,
  environment identity or proof reuse, or treats `verify.json`/`tests.json` as authority.
  Close waits for the branch's CI full suite on the PR head; red sends the task back to
  the worker with the failing checks named. The full suite keeps running on every PR as a
  hard gate.
- **Grills are one cold read.** The reader's findings and their dispositions are written
  as a short list in the plan or spec; Forge records who read, when and at which commit.
  No byte binding, input digests or staleness on uncommitted canon.
- **Lite windows** keep one ticket line and the mandatory review; manifests and budget
  bases go.
- **`.factory/` keeps only** the plan, the task list, per-task status, the PR link and
  signals.

Unchanged: one human plan approval per story, task scope shown to the reviewer and in the
PR, the destructive-command denylist, the commit belt, the sign-off gate, the roadmap,
specs and decisions.

## Consequences

- Close becomes: open or update the PR, run the review loop, wait for CI. A close failure
  now means a real finding or a red test, never a stale stamp.
- Local test runs become the worker's own business while it works; they are not proof.
- A repo whose CI does not run its tests has no proof. `forge doctor` and close name that
  instead of passing silently.
- Existing proof, review generation and grill records stay in git as history; nothing
  reads them as authority any more.
- Supersedes in full: 0069 (combined review generation), 0077 (contract verdicts as
  finding records), 0078 (parallel review groups: Autoreview splits large diffs itself),
  0079 (task proof once per tree), 0073 and 0067 (grill round reuse and rebinding).
- Supersedes in part: the proof and review-publication parts of 0054 and 0064; the review
  stamp, `delta_id` and proof steps of 0066; the "three lenses" wording of 0011, 0031 and
  0076 (0076's "review runs read-only in the task worktree and reads what it cites"
  stands); the grill-round floors and frontier rule of 0048; the grill staleness rules of
  0052 and 0090; the grounding-digest part of 0044; the "everything stays committed" list
  of 0025; the Lite budget and manifest parts of 0031.
- 0049 (per-task review proof) was never accepted and is left as history.
