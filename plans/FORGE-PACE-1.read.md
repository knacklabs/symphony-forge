---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-15T09:54:23.314488+00:00
seconds: 363.776
read_hash: f40a349c3280ed3feac5f285a5dba296a0fee5c9
round: 1
passed: no
doc_seen: f40a349c3280ed3feac5f285a5dba296a0fee5c9
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a13ef6-7126-7692-8ac4-4f759a6cdc3a
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

1. Blocking: Prototype design approval has no defined path.
   Raise: Plan gap. `plans/FORGE-PACE-1.md:37` requires prototypes to receive design approval with a plan, but its implementation at lines 64–73 covers story plans only. Prototypes use fixes; `src/forge/story.py:122–123` refuses story creation before sign-off, and `src/forge/task.py:381–386` creates fixes without a plan or design reference. The required prototype approval artifact and command are unspecified.
   Gain 5, Work 3, Harm 3

   Disposition: cut
2. Blocking: Exporting the design after approval prevents the preceding cold read from passing.
   Raise: Plan gap. `plans/FORGE-PACE-1.md:66–70` says to obtain plan approval, then copy the artboards and images into the repository, while requiring `forge read` to refuse until those images exist. The cold read precedes approval (`src/forge/templates/cold-read.md:3`). Following the stated order stalls every new user-facing story.
   Gain 4, Work 1, Harm 2

   Disposition: cut
3. Blocking: The proposed design reference does not bind approval to the approved design.
   Raise: Not done. `plans/FORGE-PACE-1.md:68` places `Design:` below the builder heading. Approval hashes exclude that section and all image contents (`src/forge/story.py:651–660`, `src/forge/task.py:70–74`). After approval, replacing the reference with another populated folder would satisfy the proposed gate while workers receive a different design. No rule or test covers this ordinary design revision.
   Gain 4, Work 2, Harm 3

   Disposition: cut
4. Blocking: Routing by changed files cannot select the first fix worker.
   Raise: Plan gap. `plans/FORGE-PACE-1.md:77–81` selects and preserves the first round’s kind from changed files. A newly started fix contains only its state record (`src/forge/task.py:381–386`); worker selection happens before its builder runs (`src/forge/worker.py:119–138`). The plan supplies neither an initial classification input nor a rule for this empty-diff case. Its routing tests do not specify that normal starting state.
   Gain 5, Work 3, Harm 3

   Disposition: cut
5. Blocking: “Full proof at sign-off, as today” relies on a contract that does not exist.
   Raise: Plan gap. `plans/FORGE-PACE-1.md:83–87` defers full proof to sign-off without defining its whole-product source or mapping. Existing proof lists map an individual change’s Done-when items to tests (`src/forge/templates/review.md:74–89`). Sign-off bypasses that input and constructs a separate snapshot-review prompt (`src/forge/review.py:976–984`, `src/forge/templates/review.md:297–304`). The builder cannot determine what complete proof must be collected or what its absence must refuse.
   Gain 5, Work 3, Harm 3

   Disposition: cut
6. Blocking: SIGNOFF and HANDOFF share an undefined evidence record.
   Raise: Plan gap. `plans/FORGE-PACE-1.md:92–98` saves a review result, commit, answers and rules, then expects that record to supply proven outcomes, proving tests and decisions. The existing sign-off reviewer returns only a commit (`src/forge/review.py:927`), and acceptance records `reviewed_commit` (`src/forge/records.py:286`). Neither the producer’s task nor an earlier task pins the additional fields, their sources or their format for HANDOFF.
   Gain 5, Work 2, Harm 3

   Disposition: cut
7. Blocking: The unchanged sign-off test can pass without implementing review reuse.
   Raise: Test. `plans/FORGE-PACE-1.md:94–95` requires two acceptance calls to run one review. Existing code already does that when the first call accepts: the second returns immediately for an accepted decision (`src/forge/records.py:240–242`). The actual duplicated-review path is review before the customer reply, followed by acceptance after recording it (`src/forge/records.py:286–301`). The named test does not require that path and therefore permits the reported problem to remain.
   Gain 4, Work 2, Harm 3

   Disposition: cut
8. Blocking: The hand-off implementation covers only the first production story.
   Raise: Not done. `plans/FORGE-PACE-1.md:21–22` promises inherited prototype proof for **each new story**, but lines 96–100 prescribe and test it only for the **first** story after sign-off. Story creation independently starts from its template each time (`src/forge/story.py:148–151`); nothing carries that first story’s section into subsequent stories. The second story can repeat the planning and cold-read work this change promises to eliminate.
   Gain 4, Work 1, Harm 2

   Disposition: cut