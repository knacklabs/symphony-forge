---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-11T16:33:33.355639+00:00
read_hash: 7ad9c46bda4b09d978e4850e33cc1ccb75a0a6c2
round: 1
passed: no
doc_seen: 7ad9c46bda4b09d978e4850e33cc1ccb75a0a6c2
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a12bc8-a7cd-7b21-a693-963671ac740e
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

1. Blocking: SCORES depends on an unspecified scoring rubric.
   Raise: Plan gap
   Item 1 requires “the four anchors from the design” (plan lines 139–141), but supplies neither those anchors nor a source containing them. The builder must invent the guidance reviewers will use to score notes.
   Disposition: cut

2. Blocking: The annotated Scope cells are not paths Forge can match.
   Raise: Plan gap
   The Tasks table includes entries such as `` `src/forge/score.py` (new) `` and function annotations containing commas. `task.cell_list` and `review.cells` split these literally; `review._within` accepts only paths, folders or globs (`src/forge/task.py:65`, `src/forge/review.py:96,482`). Required edits will appear outside Scope, and overlap detection will compare annotations instead of the actual files.
   Disposition: cut

3. Blocking: SCORES breaks existing review tests before BAR can update them.
   Raise: Plan gap
   SCORES makes new unscored findings unreadable, but existing-test updates belong to BAR, which starts afterward. The shared `finding` helper still produces unscored bodies (`tests/test_close.py:60–64`), including the P0 refusal case at line 268. SCORES owns neither that helper nor its existing tests, contradicting the promise that each merge leaves main consistent.
   Disposition: cut

4. Blocking: New cold reads are explicitly allowed to violate “every note is scored.”
   Raise: Not done
   Item 1 promises scores on every new note. The unscored rule also applies to “a reader that forgot the line,” saving and judging that new note by its old label (plan lines 123–124). This exception is broader than the promised compatibility rule for pre-upgrade saved reads.
   Disposition: keep - below the bar (Gain 2, Work 1, Harm 1): a tolerant fallback while readers learn the score line.

5. Blocking: The review Harm floor cannot inspect migration titles.
   Raise: Not done
   The floor explicitly depends on a finding’s title naming a migration, but `_finding` is instructed to call `normalise` on its body alone (plan lines 118–119, 135–136). A migration title with `Raise: Functional` and low scores in the body receives no automatic floor. The named test exercises a migration read note, not this review path.
   Disposition: cut

6. Blocking: Workers still select repair findings by priority instead of the bar.
   Raise: Functional
   `worker._fix_round` selects only undismissed P0/P1 findings (`src/forge/worker.py:364–374`). A P2 scored Gain 3, Work 1, Harm 1 will block close but disappear from the worker’s repair brief; a below-bar P1 remains in that brief. No task owns this caller, and the bar test stops at close.
   Disposition: cut

7. Blocking: Light reviews filter out findings that the new bar requires to block.
   Raise: Functional
   Item 2 says a prototype review counts `block` outcomes, but light reviews invoke Autoreview with `--max-priority P0` (`src/forge/review.py:581–584`). A P1 finding scored Gain 5 or Harm 4 is removed before Forge evaluates its scores. The plan owns `blocking`, but not this filtering path.
   Disposition: cut

8. Blocking: Sign-off reviewers receive no score instructions despite mandatory score validation.
   Raise: Functional
   SCORES adds scoring guidance under “How to report.” `review.signoff` sends only the separate sign-off block (`src/forge/review.py:665–673`), while its results still pass through `_finding`. An ordinary sign-off finding without the newly required line becomes unreadable; sign-off receives only one attempt (`review.py:590`). No task or test covers this prompt variant.
   Disposition: cut

9. Blocking: Owner-accepted review findings are omitted from the promised accepted context.
   Raise: Not done
   Item 3’s new `$accepted` block includes owner-accepted read notes and earlier below-bar review findings, but excludes owner-accepted blocking review findings. Existing `_rulings` skips accepted dismissals, and `_settled` excludes them from settlement (`src/forge/review.py:415–418,449–456`). An ordinary later review can therefore reopen an owner-accepted finding without new harm evidence.
   Disposition: cut

10. Blocking: Automatic narrowing checks fewer notes than the owner’s safety condition permits.
    Raise: Not done
    Item 4 requires every open note to have Harm 1 or 2, but its implementation rule checks only findings **at the bar** (plan lines 176–178). A stop containing a repeated Harm 2 blocker and an undismissed Harm 3 follow-up would qualify for automatic narrowing. The prerequisite’s `_answer_by_default` processes every undismissed finding, including that Harm 3 finding; the named test contains no mixed case.
    Disposition: cut

11. Blocking: The promised 30-minute rule has no cold-read implementation owner.
    Raise: Plan gap
    Item 4 covers read and review stops, but BAR assigns the default answer only to `close.py`. The prerequisite `stop-default-answer` implements review stops through `close.default_due` and `_answer_by_default`; its `story.read` still waits for an explicit read-loop choice. Neither BAR’s read scope nor its test describes automatic narrowing of a stopped read.
    Disposition: keep - below the bar (Gain 2, Work 2, Harm 1): the default was set for review stops; reads can follow later.

12. Blocking: Adding guide paragraphs leaves existing coordinator instructions contradicting the bar.
    Raise: Not done
    The plan specifies guide additions, while the shipped guide requires every in-boundary P0/P1 finding to receive a fix round and forbids dismissal for low value (`src/forge/templates/skill.md:1109–1114`). It also describes unconditional three-round stops at lines 1217–1235. Those instructions conflict with the new score gate and coordinator autonomy; checking that the new paragraph appears does not prove the delivered guide is consistent.
    Disposition: cut

Read-only inspection; runtime tests were not run. These findings identify plan gaps, not verified runtime failures.
