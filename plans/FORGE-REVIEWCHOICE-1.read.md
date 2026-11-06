---
reader: codex (gpt-6.1-sol)
read_at: 2026-11-06T11:24:44.644483+00:00
seconds: 233.796
read_hash: 5a24845f942d79764efd67a6f8a59b6dcf0f9f5a
round: 1
passed: no
doc_seen: 5a24845f942d79764efd67a6f8a59b6dcf0f9f5a
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1b097-0bb0-7e72-87f8-79189b13965c
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

1. Blocking: The permanent skip refusal loses earlier blocks when another clone continues the work.
   Raise: Plan gap.
   Case: normal use - another developer continues a branch after a blocking review was fixed and a later review passed.
   The plan checks only the current saved review and local events (`plans/FORGE-REVIEWCHOICE-1.md:70,87`). Events live in the uncommitted Git directory (`src/forge/event_log.py:42-51`, `src/forge/repo.py:474-479`); `time_records.read` reads that local log (`src/forge/time_records.py:60-63`). The second clone has a clean saved review and no earlier blocked event, so the prescribed check permits the skip despite Done-when 2. The proposed tests stay in one clone.
   Gain 4, Work 2, Harm 3
   Disposition: cut - the skip refusal now reads the committed review history (`review._history`), not the local event log, so another clone sees every earlier blocked round; Done-when 2 and Callers/Blocked-before evidence amended, and test_2 adds a second-clone case.

2. Blocking: The retry rule contradicts the promise that a skip covers only its original commit.
   Raise: Plan gap.
   Case: normal use - the default branch changes while close waits for CI, requiring close to update the item.
   The plan requires another explicit skip for a later commit (`plans/FORGE-REVIEWCHOICE-1.md:35`), but explicitly preserves the skip when close retries on a changed head (`:69`). That retry follows `_merge_default` and detects a different commit (`src/forge/close.py:475-482`). Carrying the skip into the new review branch authorizes another commit without the person's renewed request. These two instructions require different behavior.
   Gain 4, Work 2, Harm 3
   Disposition: cut - the retry copies in close drop the skip, so a changed item gets a model review and an unchanged one reuses its saved skip; the Risks trade-off now says the skip covers the changes it was given for, and test_1 adds both retry cases.

3. Blocking: A skipped item still cannot use `forge land` without an installed review tool.
   Raise: Functional.
   Case: normal use - a person closes with a skip on a machine without Codex or Claude, then runs the promised merge flow.
   The plan promises this setup and says `forge land` merges the skipped item (`plans/FORGE-REVIEWCHOICE-1.md:79,89`). However, land calls close again using a namespace without the skip options (`src/forge/land.py:53-54,93`). The planned exception to `review.require_engine` applies only to an explicit skip; that check precedes reuse of the saved review (`src/forge/close.py:201,303`). A missing configured tool therefore refuses the command (`src/forge/review.py:832-842`). The planned merge tests exercise only `forge merge`.
   Gain 3, Work 2, Harm 3
   Disposition: cut - the engine check at close.py:201 is skipped for a skip and for a saved skipped review, so land and merge reuse it with no tool; `review.run` still refuses when a model review is needed. test_2 adds a land case with no review tool.

4. Advisory: Split: SKIP → skip behavior and delivery guidance.
   Raise: Plan gap.
   The SKIP row covers four Done-when items, exceeding the stated maximum of three (`plans/FORGE-REVIEWCHOICE-1.md:111,126`). Its dependency on ROUNDS is justified solely by the guidance text checked by `test_4` (`:128`); the runtime changes use separate existing locations (`src/forge/close.py:352-360,410`). A final guidance task owning that text and its tests would remove this text-only ordering between the behavior tasks.
   Gain 2, Work 2, Harm 1
   Disposition: cut - the part was split: SKIP covers Done-when 1 and 2, and a tests-only part, WORDS, covers 4 and 5; each part keeps the guide text for its own behaviour, so the text is not split from its code.
