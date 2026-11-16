---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-16T05:41:01.001589+00:00
seconds: 263.967
read_hash: d8170db0419c785540f8f9fcc8a9b4a14259094f
round: 2
passed: yes
doc_seen: d8170db0419c785540f8f9fcc8a9b4a14259094f
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 3a3340f899a819380c944302187c3eb5cb6dbf47
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1e2ce-498c-74b0-81e0-bf84165e7e4d
session:
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
or is factually wrong or not worth the change, and give as the reason the Leave out line, the
missing Raise line, the cited fact that disproves it, why it is not worth the change, or the
human's `Decided:` line.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. Blocking: The new option can break ordinary close calls from other Forge commands.
   Raise: Plan gap
   Case: normal use - `forge land` closes a completed part.
   The plan says to read `args.show`, but [land.py](/src/forge/land.py:64) calls close with arguments that have no `show` field. [merge.py](/src/forge/merge.py:172) has the same pattern. Directly following the plan raises an attribute error; the planned command test does not exercise these callers.
   Gain 4, Work 2, Harm 3
   Disposition: cut

2. Blocking: Not done: `--show` can change the repository after a handover.
   Raise: Not done
   Case: normal use - A teammate asks to see a review for an item that has no checkout on their machine.
   The required `_worktree` lookup calls [task.py](/src/forge/task.py:237), which fetches the branch, creates a checkout and can advance a local branch. That contradicts the promise that `--show` changes nothing.
   Gain 3, Work 2, Harm 3
   Disposition: cut

3. Blocking: Not done: `--show` can display an older close as the latest one.
   Raise: Not done
   Case: normal use - A teammate closes an item on a second machine while the first machine still has its older checkout.
   [task.py](/src/forge/task.py:241) returns the local checkout before checking the published branch. The planned early return reads that checkout without the remote reconciliation in [close.py](/src/forge/close.py:213), so it prints the older review.
   Gain 3, Work 2, Harm 3
   Disposition: cut

4. Blocking: Not done: The option fails in an existing checkout that still pins the earlier release.
   Raise: Not done
   Case: normal use - Forge is upgraded while a part created before the upgrade remains in its worktree.
   Before reaching the planned branch in `close`, [cli.py](/src/forge/cli.py:147) checks the checkout’s pin. [repo.py](/src/forge/repo.py:978) then runs the earlier release, which does not recognize `--show`. The planned test uses only the current release.
   Gain 3, Work 2, Harm 3
   Disposition: defer - named as an accepted limit in Risks

5. Blocking: Not done: A split decision changes the saved result after it was printed.
   Raise: Not done
   Case: normal use - A review stops with findings and the owner chooses to split them into a follow-up.
   [close.py](/src/forge/close.py:128) changes the saved review from blocked to clean and marks its findings as follow-ups, then returns without printing a new review. The proposed replay therefore differs from the last review output.
   Gain 3, Work 2, Harm 3
   Disposition: cut

6. Blocking: Not done: Findings cannot be shown after normal merge cleanup.
   Raise: Not done
   Case: normal use - A close reports advisory findings, the part is merged, and a teammate later asks to read those findings.
   [merge.py](/src/forge/merge.py:291) removes the remote branch and, for a clean checkout, its worktree and local branch. The planned [_worktree lookup](/src/forge/close.py:658) then refuses even though the merged record contains the review.
   Gain 3, Work 2, Harm 3
   Disposition: defer - named as an accepted limit in Risks

7. Advisory: Earlier releases printed findings in a different format.
   Raise: Functional
   Case: normal use - An upgraded repo shows a close from the earlier release that had only an advisory finding.
   The [earlier close](/tests/fixtures/forge-v1.2.2/src/forge/close.py:130) printed its priority. The [current print block](/src/forge/close.py:438) omits that priority when there are no blocking findings and adds a reason. Reusing it does not reproduce the earlier finding word for word.
   Gain 3, Work 3, Harm 2
   Disposition: defer - named as an accepted limit in Risks

8. Blocking: The planned comparison can pass while both commands truncate finding bodies.
   Raise: Test
   Case: normal use - The moved printer outputs only the first line of each finding body.
   [The plan](/plans/FORGE-FINDINGS-1.md:73) compares two outputs produced by that same printer. The named [existing test](/tests/test_close_explains_findings_and_requires_done_when.py:32) checks the score lines, so both tests can pass while the explanations are missing.
   Gain 3, Work 1, Harm 3
   Disposition: cut

9. Advisory: The dismissed-finding instruction contradicts the unchanged output instruction.
   Raise: Plan gap
   Case: normal use - A later review repeats advisory advice that was already recorded as known.
   [The plan](/plans/FORGE-FINDINGS-1.md:74) says a dismissed finding is not printed. But [close.py](/src/forge/close.py:438) prints advisory findings without filtering dismissals; the existing [close test](/tests/test_close.py:634) shows that such a dismissal occurs.
   Gain 3, Work 1, Harm 1
   Disposition: cut

## Round 2

10. Advisory: Plan gap: The fix test cannot reach its dismissal assertion.
   Raise: Plan gap
   Case: normal use - The test runs its fix variant with the specified blocking P1 finding.
   [The plan](/plans/FORGE-FINDINGS-1.md:88) immediately tries to dismiss the finding. But [close.py](/src/forge/close.py:412) stops a fix after its first blocking review, and the next close refuses before processing the dismissal. The cited [dismissal test](/tests/test_close_dismiss_open_findings.py:26) uses P0 findings instead.
   Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)

11. Advisory: Functional: An open finding can be labeled as a follow-up when no follow-up fix exists.
   Raise: Functional
   Case: normal use - A review raises a “Not done” finding about builder guidance rather than an approved acceptance item.
   [review.py](/src/forge/review.py:1108) uses `follow_up` to hold the reason that finding does not block; it does not create a fix. The [planned printer](/plans/FORGE-FINDINGS-1.md:72) treats every such value as a follow-up, although the promised states describe follow-ups as findings moved to a fix.
   Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)

12. Advisory: Plan gap: The guide conflicts with the handover instruction.
   Raise: Plan gap
   Case: normal use - An agent needs findings from a teammate’s later close.
   [The plan](/plans/FORGE-FINDINGS-1.md:10) says to run close locally first, while its [guide row](/plans/FORGE-FINDINGS-1.md:76) says never to run close again only to read findings. Local close is the path that [reconciles the published branch](/src/forge/close_remote.py:58).
   Gain 3, Work 1, Harm 1
   Disposition: keep - below the bar (follow-up)
