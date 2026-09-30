---
reader: codex (gpt-6.1-sol)
read_at: 2026-09-30T20:35:49+00:00
read_hash: 503dd97d59dd60a3919dda4336c5198eb89cdb17
round: 2
passed: no
doc_seen: 503dd97d59dd60a3919dda4336c5198eb89cdb17
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 87e236921ef07b7f28a58d36f348cc4ee44eed90
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc, then run
`forge read <doc>` again for the next round, until a round finds nothing:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. Gap: item 1 treats an interrupted or failed first build as already built.
   [worker.py:116](/src/forge/worker.py:116) commits `working` before launching the worker, and failure leaves that status behind. The proposed “anything except started goes straight to close” rule skips recovery. Pin the recovery decision and test a failed or interrupted first build followed by another land run.
   Disposition: cut land builds at status `started`, or `working` with no review recorded, so a failed or stopped first build runs again; LAND tests a failed first build then a second land run.

2. Gap: items 2 and 5 cannot stop on a Claude worker’s question through the existing close refusal.
   Claude output is streamed by [worker.py:424](/src/forge/worker.py:424), while question recording happens only on the Codex path. Close reads that recorded question. LAND needs to own the shared question behavior and its worker change; test the stop under both worker families.
   Disposition: cut item 2 now says only a Codex worker's question stops land (worker.py:88 and :184 record questions only for Codex rounds); Claude-worker questions are named Out of scope and item 5 leaves per-family worker behaviour to forge work and close.

3. Gap: item 2 assumes the worker receives every check that close calls red.
   [checks.py:37](/src/forge/checks.py:37) rejects named skipped or neutral checks and cancelled checks, but `worker._failing` includes only bucket `fail`. GitHub exposes separate `skipping` and `cancel` buckets. Pin how these refusals reach the brief, and test them without an automatic re-run. [GitHub CLI documentation](https://cli.github.com/manual/gh_pr_checks).
   Disposition: cut a red refusal leads to a fix round only when `worker._failing` is not empty; a cancelled or named skipped check stops land with close's red refusal, tested in LAND with no worker call and no re-run.

4. Gap: items 1 and 3 promise recovery after any stop but skip an unfinished Forge merge once GitHub reports merged.
   [merge.py:104](/src/forge/merge.py:104) can refuse branch or worktree cleanup after the merge succeeds. Another land run takes the merged shortcut and never retries that work. This differs from the explicitly excluded cleanup after a human merge; pin and test recovery after Forge’s own partial merge.
   Disposition: cut on an already merged pull request land runs `merge.merge` when the repo lets the agent merge and a clean ready record remains (as forge next reads it); LAND tests recovery after a failed remote-branch deletion.

5. Gap: item 4’s attempt check does not enforce one re-run across interruptions before the attempt advances.
   The documented timeout leaves attempt 1 and tells the user to run land again, which qualifies the same job for another re-run request. Pin how an accepted but not yet reflected request is detected, and test two invocations before the attempt advances.
   Disposition: cut `land._rerun` writes `.git/forge/reruns/<head>` before its first request and never requests again for that head; CHECKS tests a second land run after a re-run that never started.

6. Trap: quoted Git paths and rename detection can invalidate item 4’s changed-file check.
   Plain `git diff --name-only` quotes unusual filenames and reports post-image names, so a log naming a Unicode filename or a rename’s old path can escape comparison. Use NUL-delimited filenames and include both rename endpoints; prove both cases in CHECKS. [Git documentation](https://git-scm.com/docs/git-diff).
   Disposition: cut changed files come from `git diff --name-only -z --no-renames`, and CHECKS tests a non-ASCII filename and a renamed file's old path.

7. Unproven: item 1’s successful pending-check recovery and generic stop behavior.
   LAND specifies only checks that remain pending, plus conflict and question stops. Add pending-then-green coverage and refusal cases for a failed worker, an unsynced upgrade and no named checks, asserting the stop line, original refusal, next step and exit code.
   Disposition: cut LAND adds pending-then-green, a failed worker, no checks named and an unsynced upgrade, each asserting the stop line, refusal, next step and exit code.

8. Unproven: item 2’s shared round budget and preservation of earlier dismissals.
   Four blocked reviews prove only the review counter; an empty dismissal record does not prove existing dismissals survive. Add alternating review/check failures that exhaust one three-round budget, and a previously dismissed finding that remains dismissed.
   Disposition: cut LAND adds alternating review and check failures sharing one three-round budget, and a finding dismissed before land ran that stays dismissed.

9. Unproven: item 3’s forced human hand-off for migration and adoption items when agent merges are enabled.
   The migration case asserts no worker call, while ordinary human-setting coverage does not exercise this override. Extend LAND’s cases to assert the URL hand-off and zero merge calls for both kinds under `merge = "agent"`.
   Disposition: cut LAND adds migrate and adopt fixes under `merge = "agent"` giving the hand-off line and no `gh pr merge`.

10. Unproven: item 4’s all-eligible multi-check path and failed eligibility lookups.
    The two-check case proves only the veto path. CHECKS needs successful eligible jobs sharing a run, plus unreadable attempt data and failed log retrieval, proving unavailable evidence cannot authorize a re-run.
    Disposition: cut re-runs go per run with `gh run rerun <run> --failed`; CHECKS adds two eligible jobs in one run, an unreadable attempt and an unreadable failed log.

## Round 2

11. Gap: item 1’s revised build rule conflicts with its “built fix with no worker call” test.
    A successful `forge work` also leaves status `working` with no review: [worker.py:116](/src/forge/worker.py:116) sets that status, and successful completion never replaces it. Land would rebuild an ordinary completed first build, not only an interrupted one. Pin whether that completed work is reused, and make LAND’s test exercise the actual post-work state.
    Disposition: cut land rebuilds a `working` item only when the branch's last commit is still Forge's `is working` state commit (worker.py:116-117), so a completed build goes to close; LAND's no-worker test uses a fix at `working` with a worker commit after it.

12. Unproven: item 3: the pull request merges between land’s initial lookup and close.
    [close.py:67](/src/forge/close.py:67) returns 0 for an already merged pull request without creating a Ready record. The initial merged shortcut does not cover this transition; land could then report `not_ready` or hand off a merged pull request. Pin routing back through the merged path and test this transition in LAND.
    Disposition: cut land reads the pull request again after every close that returns 0 and takes the merged path when it is merged; LAND tests a pull request merged between land's first look and close's.
