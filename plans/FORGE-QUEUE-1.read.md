---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-12T16:57:39.014654+00:00
seconds: 597.307
read_hash: d196daf4c45e2c93cc34a35a1f46ac3c944a0bd5
round: 1
passed: no
doc_seen: d196daf4c45e2c93cc34a35a1f46ac3c944a0bd5
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a13103-5ad1-7cd2-bb82-fa7b99c4c937
session:
blocked_rounds: 1
loop_choice:
loop_reason:
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
