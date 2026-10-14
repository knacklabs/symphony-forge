---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-14T10:45:11.365762+00:00
seconds: 60.457
read_hash: cef3d39f7200ce97d57a71ddac49452b85f3e31f
round: 3
passed: yes
doc_seen: cef3d39f7200ce97d57a71ddac49452b85f3e31f
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: d1126cc014fa25d9a8e1ed8ff499f1837110b866
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a139f3-034c-7512-adbd-14602c90991a
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

1. Blocking: Story planning is promised in totals but has no receipt attribution rule.
   Raise: Plan gap. [item-cost.md:77](/docs/specs/item-cost.md:77) includes planning, while lines 58–66 allow only build, read and review activities and prohibit using the parent session’s total. Planning happens in the coordinator after [story.py:162](/src/forge/story.py:162), outside a recorded worker run. When that session plans multiple stories, the builder has no rule for attributing its turns or recording unavailable planning usage.
   Gain 3, Work 1, Harm 3
   Disposition: cut

2. Blocking: The compaction contract cannot reconstruct all promised board totals.
   Raise: Plan gap. [item-cost.md:119](/docs/specs/item-cost.md:119) requires preserving token totals by model and activity, but the board also needs estimated cost and the unknown-run share. Two runs using the same model and activity can have different billing bases; token totals alone cannot distinguish them or retain the number of unknown attempts. [time_records.py:591](/src/forge/time_records.py:591) explicitly selects the fields retained after raw rows are folded. The required retained information is incomplete for a fresh clone.
   Gain 4, Work 2, Harm 3
   Disposition: cut

3. Blocking: Adding task times contradicts elapsed time when tasks run concurrently.
   Raise: Plan gap. [item-cost.md:74](/docs/specs/item-cost.md:74) says story totals add each part once without distinguishing additive token counts from overlapping time intervals. Two simultaneous one-hour tasks would produce two hours of summed elapsed time for a story that elapsed one hour. The current implementation unions intervals and resolves overlapping activity in [time_records.py:705](/src/forge/time_records.py:705). The spec leaves competing aggregation rules for elapsed, waiting and automation time.
   Gain 3, Work 1, Harm 3
   Disposition: cut

4. Blocking: One cache-write rate per model cannot price supported Claude cache durations.
   Raise: Plan gap. [item-cost.md:69](/docs/specs/item-cost.md:69) specifies one cache-write count and rate per model. Claude supports five-minute and one-hour cache writes at different prices, including an API-user setting documented in the [Claude environment reference](https://code.claude.com/docs/en/env-vars). Headless workers receive the worker environment at [worker.py:638](/src/forge/worker.py:638). The same receipt can therefore represent differently priced usage, with no rule selecting the rate or marking the estimate incomplete.
   Gain 3, Work 2, Harm 3
   Disposition: cut

5. Advisory: Cut or defer: plan-limit monitoring has no stated need or success measure.
   Raise: Plan gap. [item-cost.md:72](/docs/specs/item-cost.md:72) adds account-level quota monitoring. The Why identifies missing item costs, and the success measure at line 138 measures token coverage and compaction preservation; neither identifies a problem that quota monitoring solves. It is already a separate roadmap story at line 134, but remains part of this spec’s acceptance criteria.
   Gain 3, Work 1, Harm 2
   Disposition: cut

## Round 2

No findings.

## Round 3

No findings.
