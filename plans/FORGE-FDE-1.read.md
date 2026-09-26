---
reader: codex (gpt-6-sol)
read_at: 2026-09-26T07:36:14+00:00
read_hash: e19cacad35b62b1081c69c9c2d16f6a685d0fb7c
amended_hash: 666e9aa504ccfe72a131260b9699a988c9efd5ac
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. The story conflicts with the accepted discovery decision and the current confirmed spec.
   [Decision 0089](/docs/decisions/0089-fde-discovery-without-gstack.md) says discovery needs no gstack bundle; the [spec](/docs/specs/fde-discovery.md) says gstack is removed and names `forge payback`. The planned spec fix does not resolve the accepted decision. Reconcile both authorities before approval.
   Disposition: keep the owner chose (2026-09-26) to record "gstack stays, only for office-hours" in the amended spec, not a new decision; the Notes now say decision 0089 is narrowed, not replaced.

2. The option recommendation has no decision rule.
   `forge spec payback` gives a verdict for one build option, but Done when 3 requires a recommendation among two to four options, including “don’t build.” The story does not say how to compare multiple build options or break ties. PAYBACK, the first task using this command, should pin that contract.
   Disposition: keep the rule is now in the Notes ("Choosing among options": fewest months among build or smallest-slice answers, ties to the smaller build, else don't build or find out first), pinned by PAYBACK.

3. The discovery prompt would recur after discovery is complete.
   The proposed `forge next` condition checks only for an empty roadmap and no active work. After the discovery fix closes, those conditions can still hold even with a filled problem card. Define what stops the prompt or advances it to the next planning step.
   Disposition: keep the prompt now also needs no filled card, and once a card is filled `forge next` names writing the spec instead (Notes, "Discovery first").

4. MEASURE must pin the shared `forge next` seam.
   MEASURE and DISCOVER both change `src/forge/nextstep.py`’s `_report` output. Their tasks do not define how a due check and a discovery prompt compose or take precedence. MEASURE is first and should pin that behavior with a crossing test.
   Disposition: keep MEASURE now pins the seam: a due check is listed before the discovery prompt, with one crossing test (Notes, "Order").

5. Simpler: office-hours integration → the agent’s existing interview.
   Done when 1 names office-hours, but the story gives no observable discovery result that its interview fallback cannot produce. State what the third-party skill uniquely supplies, or use the single interview path for both cases.
   Disposition: keep the owner chose discovery by size (2026-09-26); the Why now says what office-hours adds: a longer design session that challenges the premise, weighs alternatives and ends in a design doc.
