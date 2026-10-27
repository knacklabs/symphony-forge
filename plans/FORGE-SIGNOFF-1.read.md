---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-27T09:14:04.870516+00:00
seconds: 443.934
read_hash: bb64eeb813cfd2596a0c0e40ab9057ab574f8d5d
round: 1
passed: no
doc_seen: bb64eeb813cfd2596a0c0e40ab9057ab574f8d5d
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a17c9c-9fc5-7a93-a3fe-28c5d96d651e
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

1. Blocking: The answer command can create an accepted sign-off without running sign-off checks.
   Raise: Functional
   Case: normal use - the agent records the read-back answers under the slug `client-signoff`.
   [The plan](/plans/FORGE-SIGNOFF-1.md:226) writes an accepted record for any valid slug. [Prototype detection](/src/forge/repo.py:701) treats an accepted `*-client-signoff.md` as sign-off. This bypasses the customer evidence, canvas checks and blocking-decision check in `decision_accept`.
   Gain 4, Work 2, Harm 3
   Disposition: cut - the answer command takes no slug and names its records client-answers or decided-by-default, so it never writes or accepts a sign-off record

2. Blocking: An embedded question’s scores replace the cold-read finding’s scores.
   Raise: Plan gap
   Case: normal use - a finding contains the required open-question block followed by its own final score line.
   [The planned prompt](/plans/FORGE-SIGNOFF-1.md:193) inserts a separately scored question inside the finding. [score.parse](/src/forge/score.py:27) selects the first score line, and [the reader](/src/forge/story.py:389) uses it to determine whether the finding holds. A low-ranked question can therefore make a blocking finding pass. Neither task owns this consumer change.
   Gain 4, Work 2, Harm 3
   Disposition: cut - inside a cold-read note the question block has no score line; it sits before the note's own score line, which scores both, so the note keeps its scores

3. Blocking: The proposed demo check treats permission to build as an existing working build.
   Raise: Functional
   Case: normal use - the owner accepts the prototype-build request before implementation starts.
   [Item 4](/plans/FORGE-SIGNOFF-1.md:295) uses `design.working_build`, but [that helper](/src/forge/design.py:69) returns true for an accepted build request even when no app exists. With init’s Dockerfile, `forge next` still requests a demo address before there is anything to demo.
   Gain 3, Work 2, Harm 3
   Disposition: cut - the demo address check uses design.has_app_code on the default branch, not design.working_build

4. Blocking: The Build-mark check also rejects previously accepted sign-offs.
   Raise: Functional
   Case: normal use - an upgraded client reruns acceptance of its existing sign-off.
   [The plan](/plans/FORGE-SIGNOFF-1.md:299) adds an unconditional check inside `_signoff_design`, while promising already-signed repos need no Build marks. [Accepted records with `design_checked`](/src/forge/records.py:255) enter the recheck path and call that helper, so their unchanged older canvas now fails.
   Gain 3, Work 2, Harm 3
   Disposition: cut - the Build mark check runs only for a sign-off record that is still proposed, so an accepted record's recheck is never held

5. Blocking: Every answers record omits a reason the owner explicitly required.
   Raise: Not done
   Case: normal use - either answer mode records a complete question.
   [The specified record](/plans/FORGE-SIGNOFF-1.md:242) includes `Why we ask` and `Why this default`, but omits `If the default stands`. [The owner addition](/plans/FORGE-SIGNOFF-1.md:398) requires that consequence in the answers record too. The proposed test checks only `Why we ask`, so it misses this omission.
   Gain 4, Work 1, Harm 2
   Disposition: cut - the answers record now keeps If the default stands beside Why we ask and Why this default, and test 2 checks all three

6. Advisory: The prescribed fixtures cannot produce two required prototype-test outcomes.
   Raise: Test
   Case: normal use - builders use the helpers named in the plan.
   [The positive demo test](/plans/FORGE-SIGNOFF-1.md:315) uses `_client(working_build=True)`, which [omits the prototype stage](/tests/test_proto_signoff.py:103). The adopted blocking test uses a [fixture explicitly marked live](/tests/fixtures/adopted-v1.2.2/client/forge.toml:4). Both paths require an unsigned prototype; the planned setup never establishes that state.
   Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)

7. Blocking: Unproven: item 5 does not test incomplete blocking questions.
   Raise: Test
   Case: normal use - a question names a Build now screen but lacks its due date.
   [The contract](/plans/FORGE-SIGNOFF-1.md:141) explicitly includes incomplete items in `blocking`, but [test 5](/plans/FORGE-SIGNOFF-1.md:339) exercises only complete questions. An implementation that filters incomplete items out before checking sign-off passes the described tests while allowing this expressly covered blocker through.
   Gain 3, Work 2, Harm 3
   Disposition: cut - test 5 now has an incomplete question on a Build now screen that blocks and prints not written yet
