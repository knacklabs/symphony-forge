---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-14T19:22:36.834326+00:00
seconds: 78.804
read_hash: 430f8de60ef4fbb0509a99404586fce25609a40f
round: 3
passed: yes
doc_seen: 430f8de60ef4fbb0509a99404586fce25609a40f
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: bc889f190acfb15ce0ad9d5a2b4315f3e53cb8fb
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a13bd1-cadb-7d41-8991-0e2f83034b4a
session:
blocked_rounds: 0
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

1. Blocking: The person-object change breaks the existing board page.
   Raise: Functional. `plans/FORGE-BOARD-3.md:56–59` changes `approved_by` to an object, but `src/forge/board_visuals.py:297` passes it directly to `html.escape`, which requires a string. Other person fields render as dictionary text (`board_visuals.py:75–79`). No task scopes this consumer; the JSON-only tests would miss the failure.
   Gain 4, Work 2, Harm 3

   Disposition: cut
2. Blocking: The tasks leave nobody able to finish the board wiring within scope.
   Raise: Plan gap. `plans/FORGE-BOARD-3.md:87–92` gives board wiring to OWNERS before ASSIGN, KNOWN and RELEASES exist. Those later tasks scope neither `board.py` nor `board_facts.py`, although `src/forge/board.py:703–705` constructs the returned JSON. OWNERS names no callable contracts for their future modules. Assign the shared imports and output wiring to a small final wiring task.
   Gain 5, Work 2, Harm 2

   Disposition: cut
3. Blocking: A story owner cannot be preserved using only its parts’ Developer cells.
   Raise: Plan gap. `plans/FORGE-BOARD-3.md:60–62` stores whole-story assignment by filling only unassigned parts, while promising a story-level `owner`. If every part already has a developer, assigning the story to either of two different people produces identical storage. `src/forge/task.py:186–187` reads only individual row assignments. The story-owner source and its relationship to part overrides are undefined.
   Gain 4, Work 2, Harm 2

   Disposition: cut
4. Blocking: Unproven: item 2: an assignment reaches the developer’s checkout.
   Raise: Test. `plans/FORGE-BOARD-3.md:60–65` specifies a story-branch edit and next-step ordering, but no publication rule or second-checkout test. `src/forge/story.py:597–600` can read a local working-tree edit, so assigning and running `next` in one checkout can pass while the assignee’s machine sees the old assignment.
   Gain 4, Work 2, Harm 2

   Disposition: cut
5. Blocking: Default-branch review history cannot supply all historical kept findings after squash merges.
   Raise: Not done. `plans/FORGE-BOARD-3.md:70–73` restricts the source to review history on the default branch. Forge squash-merges (`src/forge/merge.py:97`), and earlier reviews live in successive state-file commits (`src/forge/review.py:617–628`). For items predating the persistent known-findings list, those earlier reviews are absent from the squash result. Existing recovery fetches the original pull-request head (`src/forge/backfill.py:50–65`); the plan does not include that source for KNOWN.
   Gain 4, Work 2, Harm 2

   Disposition: cut
6. Blocking: Unproven: item 3: each round survives normal history compaction.
   Raise: Test. `plans/FORGE-BOARD-3.md:66–69` promises individual round times but tests only a two-round fix. Shared history has a 20,000-byte budget (`src/forge/time_records.py:22`); compaction merges earlier rounds into one aggregate (`time_records.py:540–543`), losing their individual times. The repository already exercises long review histories in `tests/test_board_after_upgrade.py:213–230`. The retention rule and its command-level proof are missing.
   Gain 3, Work 2, Harm 2

   Disposition: cut
7. Blocking: Reachable tags do not necessarily identify releases.
   Raise: Plan gap. `plans/FORGE-BOARD-3.md:74–77` selects tags solely by reachability. Forge itself creates `forge-start/…` and `forge-plan/…` bookkeeping tags (`src/forge/task.py:136,153–157`); these become reachable when a client merges the corresponding branches with merge commits. The planned rule would present them as releases. No release-tag discriminator or test covers this normal client layout.
   Gain 3, Work 2, Harm 2

   Disposition: cut
8. Blocking: The documented release process records no tag-creation date.
   Raise: Plan gap. `plans/FORGE-BOARD-3.md:74–76` requires release dates and approval-to-release durations. `docs/guide.md:330` creates lightweight tags, which contain no tagger timestamp. Tagging an older merge commit later cannot reveal when tagging occurred; its commit date is a different fact. The plan must define the date’s meaning and the unknown-date behavior before builders can implement these fields without guessing.
   Gain 4, Work 2, Harm 2

   Disposition: cut

## Round 2

9. Blocking: The compatibility rewrite leaves the promised username display unmet.
   Raise: Not done. `plans/FORGE-BOARD-3.md:30` promises usernames beside names on the board, but lines 60–65 preserve existing person strings and leave HTML unchanged. `src/forge/board_visuals.py:75–79,227,297` renders only those existing names, ignoring the added login fields. The earlier crash is removed, but a board that still shows only git names would pass the new “still renders” check.
   Gain 4, Work 2, Harm 2

   Disposition: cut
10. Blocking: KNOWN and RELEASES cannot pass their required command-level tests before WIRING.
   Raise: Plan gap. `plans/FORGE-BOARD-3.md:108–110` gives these tasks only new helper modules and makes WIRING depend on their completion. Neither module reaches `forge board` until WIRING changes `src/forge/board.py:703–705`. Yet `AGENTS.md:121` forbids importing Forge in tests, and `src/forge/templates/brief.md:159–165,189` requires each task’s named boundary tests to pass. The new split therefore leaves their command-level proof dependent on a downstream task.
   Gain 4, Work 2, Harm 2

   Disposition: cut
11. Blocking: Release membership and the shared `released_in` result remain undefined.
   Raise: Plan gap. `plans/FORGE-BOARD-3.md:87–94,109` defines eligible tags and dates, but never defines which items each release carries, which containing tag supplies `released_in`, or that result’s mapping shape for WIRING. A story’s parts can land across two releases; completion already distinguishes individual task merges from story completion (`src/forge/story.py:874–901`). RELEASES and WIRING still need an agreed rule for that ordinary case.
   Gain 4, Work 2, Harm 2

   Disposition: cut

## Round 3

12. Advisory: The revised task chain serializes independent work because it shares board wiring.
   Raise: Plan gap. `plans/FORGE-BOARD-3.md:114–115` makes KNOWN wait for ASSIGN and RELEASES wait for KNOWN, although review findings consume no assignment data and releases consume neither. Their shared edits are the board imports and JSON assembly (`src/forge/board.py:26,703–705`). These links require complete upstream merges before work can start (`src/forge/task.py:273–276`). Combine KNOWN and RELEASES with their board wiring and command-level tests under one task.
   Gain 2, Work 2, Harm 1
   Disposition: keep - below the bar (live with)
