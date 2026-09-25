---
slug: close-on-green-ci-and-clean-review
title: A task closes on a green CI run and a clean review
status: confirmed
saved: 2026-09-25T12:50:46+00:00
---

# A task closes on a green CI run and a clean review

## Why

Closing a task is where Forge spends most of its time and most of its failures. `task close`
runs the full suite locally, binds that run to a tree digest, a contract key and an environment
identity, commits it as its own proof commit, and then runs a review wrapped in three-lens markers,
per-contract verdict records, immutable review generations, a selected pointer and a "reviewed
meaning" identity. Every one of those bindings can go stale by itself. On one task, close took 4.5
hours after a clean build; another went through eleven "incomplete" rounds and two revoked review
stamps over four days. Eleven of the last 25 merged pull requests fixed Forge's own proof, review,
grill or Lite bookkeeping rather than the product. Meanwhile the pull request's CI already runs the
full suite on six runners in about five minutes, and that is the check that actually guards trunk.

The owner wants this cut first, before other stories, with one firm limit: "Lets not skip the
review the chances of regressions are higher, we fix one but regress more." So review stays
mandatory and looped; the bookkeeping around it goes. Decision 0092 records it.

## Behaviour

**When a task is done.** A task, and every Lite fix, is done when its pull request is open, the
full CI suite on the branch's latest commit is green, and the latest review round over the branch
has no P0 or P1 finding. `forge task close <id>` drives exactly that: push and open or update the
PR, run the review loop, wait for CI, then mark the task done.

**Review.** Every task and every Lite fix is reviewed by Autoreview, run once per round in the
task's worktree. Forge hands it plain review instructions: the task's declared scope and any files
changed outside it, the plan's "Done when" and acceptance criteria for this task, and the
test-audit rule. Autoreview's findings are the review. A P0 or P1 finding blocks: the coordinator
triages it (real or not, with the line that proves it), the worker fixes it, and close runs the
review again over the whole branch. P2 and P3 findings do not block; they are listed in the PR
body as advisory. Forge records one small result per round: the commit reviewed, the findings and
the status (clean or blocked). A review result for an older commit never counts for a newer one.
The exact rules are in "Rules in detail" below.

**CI is the proof.** Close does not run the test suite locally and records no proof files. It waits
for the CI checks on the PR's head commit. Green lets close finish; red stops close, names the
failing checks, and sends the task back to the worker; a new push means a new review round (if the
diff changed) and a new wait. The worker still runs tests while it works; that run is its own
business, not proof. The full suite keeps running on every PR on six duration-balanced runners and
stays a required check.

**Grills.** A spec, story plan, task plan, epic list or sign-off gets one cold read. The reader's
findings and what was done about each are written as a short list in a notes file beside the
artifact (never inside the human-facing plan body). Forge records who read it, when, and the git
hash of the file as read and after the one amendment. Nothing goes stale because other files
change afterwards.

**Lite fixes.** A Lite fix is opened with one ticket line and closes on the same rule as a task: PR,
green CI, clean review. Its window record keeps only the ticket, the branch and the commit it opened
at; the five-file limit stays and counts the files touched by the window's own commits. Window
manifests and stored budget bases are removed.

**What `.factory/` keeps.** The story plan, the task list with each task's status, the PR link, the
latest review result per task, and signals. Proof files, review generations, selected pointers,
lens files, grill byte bindings, window manifests and their migrations are no longer written or
read. Existing ones stay in git history.

**Smaller modules.** After the deletions, the largest remaining modules are split along clear lines
(stage state, scope, review run, findings, and `factory_lib` by domain) by pure moves with no
behaviour change, so parallel tasks touch different files and workers read less. The full suite is
green before and after the split.

**Unchanged.** One human plan approval per story, task scope shown to the reviewer and in the PR,
the functional check for user-facing tasks, the destructive-command denylist, the commit belt, the
sign-off gate, the ticket check, the roadmap, specs and decisions.

## Rules in detail

- **Unmet "Done when".** The review instructions tell the reviewer to report every "Done when" item
  or acceptance criterion the branch does not meet as a P1 finding titled `Not done: <item>`. An
  unmet item is a defect, so it blocks like any P1. There are no verdict records.
- **Triage.** The coordinator may dismiss a P0/P1 finding as not real only with a `file:line` that
  proves it; the dismissal and its reason are stored in the review result and listed in the PR
  body. Close counts only undismissed P0/P1 findings.
- **Failed reviews.** An Autoreview run that exits with an error, is interrupted, returns output
  Forge cannot read, or reports its review as incomplete produces no review result. Close retries it
  once, then stops and shows the helper's own error. Only a completed run counts, whether clean or
  with findings.
- **Which commit a review covers.** The review result is committed under `.factory/`. It covers the
  PR head when the head's product files (everything outside `.factory/` and `plans/`) are identical
  to the reviewed commit's, so recording the result or the task status never makes it stale.
- **Tests that must exist.** A task's required tests are part of the repository's test suite and run
  in CI; the review instructions list them and the reviewer reports a missing or hollow one as
  `Not done`. Close no longer runs per-task verify commands itself.
- **Which checks count.** `harness.yaml` names the required CI checks (`ci.required_checks`; this
  repository: `scaffold-check`, which fails unless all six test shards pass). Close reads the check
  runs and commit statuses of the reviewed PR head: every required check must be `success`; other
  checks may be `success`, `skipped` or `neutral`; any `failure`, `cancelled` or `timed_out` is red;
  a missing required check or an API error is "not green yet" with the reason. A client repository
  names its own test check there; if none is named, close refuses and `forge doctor` says why.
- **Bot commits after the run.** Later commits on the PR that only touch bookkeeping paths and skip
  CI (the pr-link backfill) do not change which commit close judges.
- **The PR gate.** The roadmap gate checks each new task marker against its committed review result
  (clean, covering the marker's product tree) instead of `verify.json`, `tests.json` and a selected
  review generation.
- **Old records.** Task markers already on trunk count as done without re-reading their proof.
  Tasks active and Lite windows open at the switch finish under these rules.
- **Changed grilled files.** `spec confirm` and plan approval refuse when the file's current git hash
  is neither the hash the cold reader saw nor the recorded amended hash.
- **In-flight plans.** The four active story plans change only in their technical notes (how a task
  closes); their "What changes for you" and "Done when" are unchanged, so under the one-approval
  rule they need no fresh human approval. The coordinator records each amendment.

## Acceptance criteria

- Every task and every Lite fix is reviewed: `task close` and Lite close cannot finish without a
  completed review result whose reviewed product files equal the PR head's.
- An unmet "Done when" item or acceptance criterion is reported as a P1 `Not done` finding and
  blocks; a failed or incomplete review run is retried once and then stops close.
- A user-facing task still needs its functional check before it is done.
- A P0 or P1 finding blocks close until the worker fixes it and a new review round over the new
  head commit has no P0 or P1 finding.
- P2 and P3 findings do not block and appear as an advisory list in the PR body; re-running close
  replaces only Forge's block in the PR body.
- The review instructions handed to Autoreview contain the task's declared scope, any out-of-scope
  changed files, the plan's "Done when" and the task's acceptance criteria, and the test-audit rule;
  a test asserts each is present.
- Close completes only after every CI check on the PR's head commit is green. A red check stops
  close, names the check, and leaves the task open; a pending check makes close wait (or return
  with "waiting for CI" and resume on the next run).
- A PR with no CI checks reported is not treated as green; close says so.
- The full test suite runs in CI on every harness PR as a required check.
- One cold read of a spec, plan, task plan, epic list or sign-off is recorded as reader, time and
  the file's git hash as read and as amended; its findings and dispositions are a list in a notes
  file beside the artifact. A later change to other files does not make it stale; a change to the
  file itself does.
- `harness.yaml` names the required CI checks; close judges the reviewed PR head by them and refuses
  in a repository that names none.
- The roadmap PR gate accepts a task marker with a clean committed review result and no longer
  requires `verify.json`, `tests.json` or a review generation.
- Lite fixes carry one ticket line and close with a PR, green CI and a clean review; no window
  manifest or budget base is written, and the five-file limit counts the window's own commits.
- Deleted, not disabled: local proof at close and its receipts, environment identity and reuse;
  `verify.json`/`tests.json` as close or PR authority; three-lens markers, lens tags, verdict records,
  review generations, `selected.json`, reviewed-meaning identity, stage review stamps and raw result
  archives; grill artifact deltas, input digests and staleness; Lite window manifests and budget
  bases. Their tests go with them.
- After the split, no Python module under `factory/scripts` is longer than 1,200 lines; the split
  moves code without changing behaviour and the full suite is green on the commit before and after.
- Existing records of these kinds in git do not break any command: the board, `forge next`,
  `pr-ready` and the CI gates ignore them.
- The four in-flight story plans (full access, simple upgrade, FDE, warm threads) are re-recorded
  against the new close rule before their first task starts.

## Success measure

- Metric: median time from the worker's last commit to a closed task (PR open, CI green, review
  clean), and the number of merged PRs per two weeks that fix Forge's own proof, review, grill or
  Lite bookkeeping.
- Baseline: close has taken from minutes to 4.5 hours after a clean build (one task needed four
  days); 11 of the last 25 merged PRs (to 2026-09-25) were bookkeeping fixes.
- Target: median close under 30 minutes, dominated by one review round and one CI run; at most one
  bookkeeping-fix PR per two weeks.
- Check date: 2026-10-23

## Out of scope

- Changing what Autoreview checks or how it works inside; it stays an external black box.
- Changing CI sharding, timeouts or the Windows job, beyond making the full suite a required
  check.
- The executor setting, warm Codex threads, the new upgrade flow, FDE discovery and full access;
  their stories are re-planned on top of this one.
- Rewriting old history records or migrating them; they stay as history.
- Merging PRs automatically; a human still merges.
