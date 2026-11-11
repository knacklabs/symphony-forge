---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-11T03:13:33.541920+00:00
seconds: 464.041
read_hash: 8bc9e812b17fa3c1bcc79cc51f2638e770430d7e
round: 2
passed: yes
doc_seen: 8bc9e812b17fa3c1bcc79cc51f2638e770430d7e
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 4810d8de0f67a8b750d02b7fbf90f56e15017b66
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1c885-61d2-73b0-bce0-db133fc404e2
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

1. Blocking: Not done: The review rule does not reach the first research page.
   Raise: Not done. [The plan](/plans/FORGE-PROSPECT-1.md:77) puts the rule only in the light review, but [review.py](/src/forge/review.py:861) uses that review only for an unsigned prototype with an accepted working-build decision or app code. A new repo without a starter has neither; an earlier-adopted live repo is also excluded.
   Case: normal use - A salesperson saves the research before the first prototype plan. The planned test uses a helper that [creates an accepted working-build decision](/tests/test_close.py:199), so it misses this path.
   Gain 5, Work 2, Harm 3
Disposition: cut - the review rule is removed; the plan now says the research page gets no review rule (the light review needs a working build, review.py:861-862), Done-when 3 no longer promises a review, and the marks are checked by the agent before it shows the proposal and by the Sales person, who sees every link.

2. Blocking: Data loss: A second pass can erase the first page and the chosen features.
   Raise: Data loss. [The plan](/plans/FORGE-PROSPECT-1.md:65) says a second pass rewrites the page and Git keeps the old one, while [the chosen features and changed words](/plans/FORGE-PROSPECT-1.md:75) live on that page. Git cannot recover a version that was never committed; [Forge also squash-merges fixes](/src/forge/merge.py:201), so intermediate commits are absent from the normal default-branch history.
   Case: normal use - The salesperson chooses a prototype, then asks for another pass before the research fix is committed.
   Gain 3, Work 2, Harm 4
Disposition: cut - Settled 11 now says a later research pass or a later choice adds a new dated part (`## Research of <date>`, `## Chosen prototype, <date>`) and never removes or rewrites an earlier part; Done-when 3 and test_3 now prove this rule.

3. Blocking: Plan gap: Choosing another option leaves the rejected proposal under “Chosen prototype.”
   Raise: Plan gap. [The plan](/plans/FORGE-PROSPECT-1.md:74) puts the recommendation and alternatives in separate sections. Its choice rule only renames the recommendation’s section and adds an option number; it does not put the selected option’s task and features in that section. The [prototype plan](/src/forge/templates/skill.md:646) is then written from the chosen task and features.
   Case: normal use - The salesperson picks the second option or changes the recommendation.
   Gain 4, Work 1, Harm 3
Disposition: cut - Settled 12 now appends `## Chosen prototype, <date>` holding the full chosen prototype (task and each feature line with its mark, copied from the chosen option with the Sales person's changes), and the plan's demo steps come from the newest chosen part; the proposal sections stay unchanged.

4. Blocking: Plan gap: A thin research pass can exhaust the budget before the similar-company study.
   Raise: Plan gap. [The ordered pass and shared limit](/plans/FORGE-PROSPECT-1.md:67) allow all searches or page reads to be spent on the prospect before the plan determines that findings are thin. [The thin-findings rule](/plans/FORGE-PROSPECT-1.md:71) then requires two or three similar companies within that same exhausted limit; the existing [pre-meeting step](/src/forge/templates/skill.md:615) has no budget rule that resolves it.
   Case: normal use - A small prospect has little public information, and the agent uses the limit looking for it.
   Gain 4, Work 1, Harm 3
Disposition: cut - Settled 4 now splits the limit: items 1 to 6 use at most 8 searches and 14 page reads, and the last 4 searches and 6 page reads are kept for similar companies and used only when findings are thin.

5. Blocking: Plan gap: The no-search path gives customer-sourced features incompatible labels.
   Raise: Plan gap. [The plan](/plans/FORGE-PROSPECT-1.md:72) requires every idea to say `not researched` without web access, while its next rule permits exactly one mark and its approved text requires customer words to say `heard from the customer`. The [current guide](/src/forge/templates/skill.md:31) also requires transcript points to name their source.
   Case: normal use - The salesperson supplies a transcript in a session without web search.
   Gain 4, Work 1, Harm 3
Disposition: cut - Settled 9 now gives one mark rule for every path: a transcript point is `heard from the customer: <file>` with or without web search, and `not researched` is only for an idea with no source when the session cannot search or the pass did not reach the item; Settled 8 defers to Settled 9.

6. Blocking: Functional: A valid choice creates a false research finding.
   Raise: Functional. [The proposed review rule](/plans/FORGE-PROSPECT-1.md:77) reports every unmarked line under `## Chosen prototype`. The plan itself requires a `- Chosen: yes (salesperson, <date>)` line there, which has neither a link nor one of the specified marks. The [light-review template](/src/forge/templates/review-light.md:10) has no distinction between that metadata and a feature.
   Case: normal use - The salesperson accepts a fully sourced proposal.
   Gain 3, Work 1, Harm 3
Disposition: cut - the review rule is removed (see note 1); the `Chosen by:` line is stated as not a feature and needing no mark.

7. Blocking: Not done: The review misses a similar-company feature without its required link.
   Raise: Not done. [The approved criteria](/plans/FORGE-PROSPECT-1.md:26) require a similar-company source to include a link, but [the proposed rule](/plans/FORGE-PROSPECT-1.md:77) accepts the words `from similar companies` alone. [Review instructions](/src/forge/review.py:344) provide no other research check.
   Case: normal use - A feature says `from similar companies: Acme` but omits the source link.
   Gain 3, Work 1, Harm 3
Disposition: cut - the review rule is removed (see note 1); Settled 9 requires `from similar companies: <company>` with a link, and test_2 asserts that list word for word.

8. Blocking: Not done: A research finding can stop the fix.
   Raise: Not done. [The plan](/plans/FORGE-PROSPECT-1.md:77) assumes the light review makes every research finding non-blocking. [Forge’s scoring](/src/forge/score.py:83) still blocks a light review when a finding scores Gain 5. The [planned test](/plans/FORGE-PROSPECT-1.md:90) returns a clean review, so it cannot detect this.
   Case: normal use - The only proposed feature has no source, and the reviewer scores that missing main requirement Gain 5.
   Gain 4, Work 2, Harm 3
Disposition: cut - the review rule is removed (see note 1), so no research finding can stop the fix; Notes score a review rule at 2 < 4 because it would need code to reach the page and stay non-blocking.

9. Blocking: Unproven: Item 1 does not test that every finding has a link.
   Raise: Test. [The planned test](/plans/FORGE-PROSPECT-1.md:82) checks the findings heading and an `Evidence:` field with a link, but does not check that the guidance requires a link for each item under that heading. The existing [outline test](/tests/test_aha_prepare.py:53) does not cover this new rule either.
   Case: normal use - The generated guide permits several company findings with no links while retaining a linked problem card; the planned assertions still pass.
   Gain 3, Work 2, Harm 3
Disposition: cut - Settled 6 now pins the sentence "Every finding under What we found has its own link to the public page it comes from; a finding without a link is not written.", and test_1 asserts it word for word in both hosts' synced skill, so a guide that allows unlinked findings fails.

## Round 2

10. Advisory: Plan gap: A customer’s correction can leave the prototype plan using the old task.
    Raise: Plan gap. [The plan](/plans/FORGE-PROSPECT-1.md:84) says the customer’s recap reply replaces the demo task in the brief, but the prototype plan takes its steps from the newest chosen part of the research page. It does not say that a customer correction adds a chosen part. The [current guide](/src/forge/templates/skill.md:620) treats that reply as the source of the demo task.
    Case: normal use - The salesperson chooses bookings, then the customer replies that the demo should track orders. The brief can say orders while the chosen part still says bookings.
    Gain 4, Work 3, Harm 3
   Disposition: keep - below the bar (follow-up)

11. Advisory: Plan gap: An idea based on the salesperson’s own notes has no source mark.
    Raise: Plan gap. [The plan](/plans/FORGE-PROSPECT-1.md:68) accepts the salesperson’s notes as input, but [its marks](/plans/FORGE-PROSPECT-1.md:75) cover customer words and a feature the salesperson adds in a reply, not an idea the agent derives from the salesperson’s own observation. The [current guide](/src/forge/templates/skill.md:793) recognizes the salesperson as a source.
    Case: normal use - The initial notes say the prospect tracks orders in a spreadsheet, but the web pass finds no public evidence of that. If the relevant research item was reached, the proposed tracking feature has none of the permitted marks.
    Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)
