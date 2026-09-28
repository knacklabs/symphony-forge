---
reader: codex (gpt-6-sol)
read_at: 2026-09-28T15:50:11+00:00
read_hash: 681c20e42cbf8596b0ec19010db15c8a4143e6f6
amended_hash:
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. The plan does not preserve the same reader across rounds.
   `forge read` currently chooses the reader from the app coordinating that invocation ([story.py](/src/forge/story.py:153)). Running a later round from the other app switches reader families. Pin whether Forge uses the recorded reader or refuses a mismatched invocation.
   Disposition: cut: item 1 keeps the recorded reader family and refuses a round from the app that is itself the reader.

2. The pass gate needs a rule for confirmed specs.
   `spec confirm` changes the spec’s frontmatter after its passing read, and `spec measure` later changes its body ([records.py](/src/forge/records.py:163)). A pull-request check against the full `read_hash` would reject those existing flows. Define which changes require another round and how the check recognizes permitted confirmation or measurement changes.
   Disposition: cut: item 2 gates only unconfirmed specs; a confirmed spec's confirm and measure changes need no new round.

3. An approved story can start tasks after its Tasks table changes without another read.
   `forge next` checks the read only while approval is pending, and `forge task start` checks an approval hash that excludes the Tasks table ([nextstep.py](/src/forge/nextstep.py:226), [task.py](/src/forge/task.py:137)). Pin the post-approval gate and add `src/forge/task.py` to the owning scope if task start must refuse.
   Disposition: cut: item 2 adds forge task start to the gate, so a changed Tasks table needs a passing round; task.py is in GATES' Scope.

4. SPEC needs to pin the round-notes contract that LOOP will parse.
   The plan names `round` and `passed`, but does not define how to identify a round’s exact `No findings.`, number findings across rounds, or dispose of a new `Disputed keep` before the next read. Existing notes also lack those fields; specify how old unapproved reads continue and how previously approved stories retain approval ([story.py](/src/forge/story.py:491)).
   Disposition: cut: Notes pin the round contract (round, passed, ## Round <n>, numbering, old notes as round 1); item 3 says how a disputed keep is disposed; item 2 says old approved stories keep approval.

5. Unproven: items 1–3: round recovery and refusal paths.
   The Tests cells name files but no cases for an unavailable Codex conversation, a failed or discarded round, legacy notes, a changed approved Tasks table, spec confirmation, or a disputed keep settled by the human. Put the required cases in the relevant Done-when items and their tests in the owning task’s Tests cell.
   Disposition: cut: items 1 and 2 now name each recovery and refusal case their tests cover.

6. Item 5 does not pin how a learned trap reaches the outcome pull request.
   `forge story done` currently opens a fix containing only state changes ([story.py](/src/forge/story.py:224)). Specify the skill step that checks the review-round threshold, edits `AGENTS.md` in that fix, and verifies the trap ships with the outcome.
   Disposition: cut: item 5 says the agent adds the trap lines in the outcome fix's worktree and commits them before closing it.

7. Split: LOOP → round execution and pass gates.
   LOOP owns three Done-when items across six Python modules, two docs, an adapter, and the real-SDK tests; its scope suggests more than about 400 changed lines. Put round execution in one task and approval, spec, PR, and post-approval gates in a following task.
   Disposition: cut: LOOP is split into ROUNDS (items 1, 6) and GATES (item 2, after ROUNDS).

