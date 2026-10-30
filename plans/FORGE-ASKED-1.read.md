---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-27T10:29:33.641307+00:00
seconds: 62.37
read_hash: 52ed2b5f1aa322ac2ebae7b9fa2370ec62ad37d5
round: 4
passed: yes
doc_seen: 52ed2b5f1aa322ac2ebae7b9fa2370ec62ad37d5
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: b3f849d5ebbef85fbe885b01752b9ba592eef953
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a17ca5-0bd1-7e91-8dfe-e17dc10271cb
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

1. Blocking: Lowering Gain does not guarantee that a below-cost review note lets work continue.
   Raise: Plan gap
   [The plan](/plans/FORGE-ASKED-1.md:106) says Gain 2 or less is sufficient, with no review-code changes. However, [review.py:1067](/src/forge/review.py:1067) marks a finding against an approved Done-when item as required, and [review.py:229](/src/forge/review.py:229) blocks it regardless of scores. The pinned instructions leave this precedence unresolved.
   Case: normal use - a reviewer requests a missing, explicitly promised check, scores its added work below cost, and close still blocks despite Gain 2.
   Gain 4, Work 2, Harm 2
   Disposition: cut

2. Blocking: The pinned changes leave canvas requirements that contradict the Build now scope.
   Raise: Plan gap
   [Text C](/plans/FORGE-ASKED-1.md:247) says never to check code against the canvas. Yet [review.md:66](/src/forge/templates/review.md:66) still requires a P1 for any component or field missing from the owned design’s SCREENS.md. [brief.md:48](/src/forge/templates/brief.md:48) and [worker.py:598](/src/forge/worker.py:598) also instruct workers to build those canvas fields. None of these instructions is reconciled by the prescribed edits.
   Case: normal use - a production story touches a screen whose canvas includes a later field; the worker must build it and the reviewer must flag its absence, despite the narrower signed scope.
   Gain 4, Work 2, Harm 3
   Disposition: cut

3. Advisory: Cold-read limits will not appear in Known issues as promised.
   Raise: Not done
   [Done-when item 2](/plans/FORGE-ASKED-1.md:64) promises this for both reads and reviews. [story.py:389](/src/forge/story.py:389) gives below-bar read notes dispositions and saves them in the read document, but does not populate a known-findings list. [known_issues.py:134](/src/forge/known_issues.py:134) reads saved known lists and review history, not cold-read documents. The planned test checks Known issues only after a review, so it misses this gap.
   Gain 3, Work 3, Harm 2
   Disposition: keep - below the bar (follow-up)

## Round 2

4. Blocking: Finding 2 remains open for unsourced fields on a Build now screen.
   Raise: Plan gap
   The new [text I](/plans/FORGE-ASKED-1.md:354) filters screens but still requires every component and field their SCREENS.md sections list. It therefore preserves the field requirement in [review.md:66](/src/forge/templates/review.md:66) and [brief.md:48](/src/forge/templates/brief.md:48) for included screens. This contradicts the amended Risks rule that an unsourced canvas field on such a screen is not built.
   Case: normal use - the story names the Customers screen and its name field, while its canvas also shows an unrequested loyalty field. Text I still tells the worker to build both fields and the reviewer to flag the loyalty field’s absence. The added test assertions only check the screen-filtering phrases, so they pass with this contradiction.
   Gain 4, Work 2, Harm 3
   Disposition: keep - The owner rules that a field shown on a signed Build now screen is in scope because the sign-off is its source; recorded in the builder notes

## Round 3

No findings.

## Round 4

No findings.
