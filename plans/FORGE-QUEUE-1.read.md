---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-12T17:09:30.128927+00:00
seconds: 131.113
read_hash: 8b3b90b96bda282baa281d62ed8c14a002a3cd14
round: 3
passed: no
doc_seen: 143d83007042fa7dc198c39b00b97441783b8a08
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: a0609288b2bca388b7312d9771d6a0776cd15bd1
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a13103-5ad1-7cd2-bb82-fa7b99c4c937
session:
blocked_rounds: 3
loop_choice: accept
loop_reason: Owner rule for Harm 1-2: the only open note (an hour limit ending a live CI wait) is fixed in the plan: busy follows the recording process's identity
---
# Cold read notes

Written by `forge read`. Under every blocking finding, write one disposition line, amend the
doc, then run `forge read <doc>` again until a round has no blocking notes. Notes marked
`Advisory:` are recorded without requiring a disposition or another round:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

A finding inside What counts is cut or deferred. Keep one only when it falls outside that boundary
or is factually wrong, and give as the reason the Leave out line, the missing Raise line, the
cited fact that disproves it, or the human's `Decided:` line.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. Blocking: Concurrent complete land processes cannot guarantee oldest-first merges.
   Raise: Plan gap. [Plan:80](/plans/FORGE-QUEUE-1.md:80) starts independent `forge land <item>` children. Each calls merge immediately after its own close succeeds ([land.py:104](/src/forge/land.py:104)). A newer change with faster checks merges before an older one with slower checks. No merge-order gate is specified, despite Done-when 1 and its test requiring that order.
   Gain 4, Work 3, Harm 2
   Disposition: cut - Gain 4, Work 1, Harm 2 with the simple rule: the run starts changes oldest first and each merges when it passes; Done when 1 and its test now promise start order, not merge order.

2. Blocking: Reusing the existing retry path misses flaky checks after a distinct fast-test command passes.
   Raise: Not done. [land.py:140](/src/forge/land.py:140) requires a passing record for `test`, whereas [review.py:335](/src/forge/review.py:335) runs `fast_test`; the record includes the command string ([review.py:505](/src/forge/review.py:505)). Forge itself configures different commands. With only close's passing result, an unrelated first-attempt failure stops instead of retrying. Existing retry coverage hides this by setting both commands to `true` ([test_land_checks.py:23](/tests/test_land_checks.py:23)).
   Gain 4, Work 2, Harm 2
   Disposition: cut - Gain 4, Work 2, Harm 2: land's rule stays, and item 3 now counts a passed record for `test` or the command close ran (`fast_test`); its test uses a repo whose `fast_test` differs.

3. Blocking: Selection can start a second close on a change already being closed.
   Raise: Functional. [Plan:95](/plans/FORGE-QUEUE-1.md:95) selects `reviewing` changes and excludes only active `work` entries. An ongoing close registers a `review` entry ([review.py:699](/src/forge/review.py:699)); close has no per-item admission lock ([close.py:86](/src/forge/close.py:86)). Running `--all` while an existing close reviews therefore starts another review and concurrent commits and pushes in the same worktree. No rule or test covers this explicitly selected state.
   Gain 4, Work 3, Harm 2
   Disposition: cut - Gain 4, Work 2, Harm 2 with the simple rule: one run per repo holds a lock, and selection leaves out any change with any entry (work, review or test) in the machine's line; the test covers the second run.

4. Blocking: Holding an already-reviewed overlapping change does not prevent another review after the older change merges.
   Raise: Not done. The promise at [plan:12](/plans/FORGE-QUEUE-1.md:12) includes changes already under review, and selection includes ready changes. Current close merges main ([close.py:622](/src/forge/close.py:622)) and decides reuse from a fingerprint containing both file blob IDs ([review.py:164](/src/forge/review.py:164)). An older change to different lines of the same file changes that fingerprint, causing the newer, previously reviewed change to be reviewed again. The proposed test does not require a pre-existing review.
   Gain 4, Work 2, Harm 2
   Disposition: cut - Gain 4, Work 1, Harm 2: the promise now covers only changes not yet ready; a ready change is never held and keeps today's review rules; the test's held change has no earlier review.

5. Blocking: The overlap check misses the shared spotted file that close itself adds.
   Raise: Plan gap. [Plan:108](/plans/FORGE-QUEUE-1.md:108) checks existing git diffs. Two initially disjoint fixes can both gain advisory findings during their reviews; [spotted.py:187](/src/forge/spotted.py:187) records them in the shared `plans/spotted.json`, which [close.py:349](/src/forge/close.py:349) commits. Both closes then edit the same file concurrently. The plan explicitly requires no dependency on the in-flight change that removes this shared file, and its overlap test does not exercise generated spotted records.
   Gain 3, Work 2, Harm 2
   Disposition: cut - Gain 3, Work 1, Harm 2: the overlap check leaves out Forge's own record files (`.factory/`, generated files, the roadmap and spotted lists), which close's merge step resolves by itself; the test records spotted lines in two changes.

6. Blocking: The parent has no rule for surviving deletion of its starting worktree.
   Raise: Functional. [Plan:80](/plans/FORGE-QUEUE-1.md:80) isolates children but leaves the parent's working directory unspecified. On macOS or Linux, starting `--all` from a selected fix can let that fix's child remove the parent's current directory ([merge.py:165](/src/forge/merge.py:165)). That child's directory change does not move the parent; later launches or git commands using the original directory fail. The proposed tests do not run the queue from a worktree it merges.
   Gain 3, Work 2, Harm 2
   Disposition: cut - Gain 3, Work 1, Harm 2: the parent works from the main checkout for every git call and child; the test runs from a selected fix's worktree.

7. Blocking: QUEUE's Scope excludes the command page its required sync changes.
   Raise: Gate. [Plan:78](/plans/FORGE-QUEUE-1.md:78) changes the command listing, but [QUEUE's Scope](/plans/FORGE-QUEUE-1.md:149) omits `docs/commands.md`. Sync writes that page from the listing ([sync.py:527](/src/forge/sync.py:527)), and [test_split_page.py:27](/tests/test_split_page.py:27) requires the checked-in page to match. The builder must either exceed Scope or leave a required check failing.
   Gain 3, Work 1, Harm 1
   Disposition: cut - Gain 3, Work 1, Harm 1: both parts' Scope now holds `docs/commands.md`.

8. Blocking: The specified argument refusal reports the wrong problem.
   Raise: Gate. [Plan:77](/plans/FORGE-QUEUE-1.md:77) uses `bad_item` when both forms are supplied. For `forge land valid-fix --all`, [repo.py:54](/src/forge/repo.py:54) says the valid fix name is invalid and directs the user to `forge next`. It does not identify the conflicting arguments or give the usable invocation, contrary to the repository's refusal rule. No proposed test covers either invalid combination.
   Gain 2, Work 1, Harm 1
   Disposition: cut - Gain 2, Work 1, Harm 1, below the bar but a one-line wording fix: the plan names a new refusal that says to give one change or --all, with both forms as the next step.

No files changed; runtime tests were not run. These findings are from a static read.

## Round 2

9. Blocking: The ready bypass uses a stored status that close does not write.
   Raise: Not done. [Plan:132](/plans/FORGE-QUEUE-1.md:132) exempts changes whose status is `ready`, using selection from `repo.read_state`. Successful close leaves that status as `waiting for checks` ([close.py:353](/src/forge/close.py:353)) and writes a separate ready receipt ([close.py:403](/src/forge/close.py:403)). Forge derives readiness from a matching receipt and head ([nextstep.py:637](/src/forge/nextstep.py:637)). The specified predicate therefore holds ordinary ready changes; the revised test exercises only unreviewed changes and misses this.
   Gain 3, Work 2, Harm 2
   Disposition: cut - Gain 3, Work 1, Harm 2: readiness is now `forge next`'s own rule (`nextstep._item_readiness`: a clean receipt matching the head, checks not failing), never the stored status; item 2's test adds a ready change that merges without a wait.

10. Blocking: The new generated-file exemption includes user-owned Husky hooks.
   Raise: Plan gap. [Plan:128](/plans/FORGE-QUEUE-1.md:128) excludes every file returned by `sync.files`, claiming this matches close's automatic conflict handling. That inventory includes Husky `pre-commit` and `pre-push` hooks ([githooks.py:87](/src/forge/githooks.py:87)), but close explicitly removes them because their remaining content belongs to the user ([close.py:636](/src/forge/close.py:636)). Two fixes changing the same user hook would close concurrently, contrary to Done-when 2. The spotted-record test does not cover this exclusion.
   Gain 3, Work 2, Harm 2
   Disposition: cut - Gain 3, Work 1, Harm 2: the exemption now names exactly `plans/spotted.json` and `.factory/`; every other file, Husky hooks included, counts as overlap.

11. Blocking: The new busy-item exclusion cannot see a close waiting only for CI.
   Raise: Functional. After review and local tests finish, their machine entries are released ([review.py:699](/src/forge/review.py:699), [review.py:474](/src/forge/review.py:474)), while close continues waiting in `checks.wait` ([close.py:387](/src/forge/close.py:387)). Its state remains `waiting for checks`, so [plan:111](/plans/FORGE-QUEUE-1.md:111) selects it without finding a machine entry. The new queue lock covers another `--all` parent, not an existing single-item close or land waiting for CI; the proposed second-run test cannot catch this phase.
   Gain 3, Work 3, Harm 2
   Disposition: cut - Gain 3, Work 2, Harm 2: busy now also means an open run of any kind in the item's events (`board.active_runs`), which covers the `ci` run that `checks.wait` already records; a `ci` start over an hour old counts as ended; item 1's test adds a change waiting on CI.

No files changed; runtime tests were not run. These findings are from a static read.

## Round 3

12. Blocking: The one-hour expiry treats a live CI wait as an ended command.
   Raise: Functional. [Plan:115](/plans/FORGE-QUEUE-1.md:115) expires every open `ci` run after an hour. However, [checks.py:90](/src/forge/checks.py:90) continually extends the deadline while checks remain queued, so a close waiting over an hour for a busy shared runner is still alive. Its review and local-test entries have ended; expiring its CI entry lets `--all` start another close on that worktree. Age does not establish that the command died. The new test covers only a one-minute-old run and would pass with this defect.
   Gain 3, Work 3, Harm 2
   Disposition: cut - busy now follows the recording process's identity, not a time limit: a live CI wait stays busy, a killed close does not (Gain 3, Work 1, Harm 1)

Runtime tests were not run; this is a static plan finding.
