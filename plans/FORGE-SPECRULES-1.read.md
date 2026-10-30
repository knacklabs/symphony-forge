---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-27T09:06:13.058293+00:00
seconds: 278.756
read_hash: 23d175f73e830cbdd03a214341ba034212b48698
round: 1
passed: yes
doc_seen: 23d175f73e830cbdd03a214341ba034212b48698
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a17c97-f1cd-7342-b8b0-71d443cc1520
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

1. Advisory: Unproven: item 2: the accept test cannot detect README lines leaking into its output.
   Raise: Test.
   Case: normal use - accepting a decision that changes `R-1` in a newly initialized repo.
   `plans/FORGE-SPECRULES-1.md:98-102` adds `R-1` references to the README, which init delivers through `src/forge/init.py:344-349`. However, the accept fixture at `plans/FORGE-SPECRULES-1.md:158-173` searches only for `R-13` and supplies no matching README line. An implementation that excludes cold-read notes but includes README files would pass every planned test while violating Done-when 2.
   Gain 3, Work 1, Harm 1
   Disposition: keep - below the bar (follow-up)
