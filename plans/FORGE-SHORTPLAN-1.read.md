---
reader: codex (gpt-6-sol)
read_at: 2026-09-28T18:21:26+00:00
read_hash: 7f617f723b481bae3ae12686792c8614bbb94ff3
amended_hash:
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. Top-only approval conflicts with the existing confirmed approval contract.
   [plan-approval.md](/docs/specs/plan-approval.md:10) requires the human to see the exact saved plan body. This story hides the builder sections, but neither task reconciles that contract.
   Disposition: keep the confirmed plan-approval spec already asks for a reader-facing body with no paths or scope lists, and approval still binds the text the human reads; the top part is exactly that.

2. Pin what happens when detail numbers are missing, duplicated, or unmatched.
   The [story’s format contract](/plans/FORGE-SHORTPLAN-1.md:61) names the heading and numbering but gives no rule for malformed entries. Since the [current parser](/src/forge/story.py:265) reads top-level items independently, a detail could be silently omitted from a worker brief or review.
   Disposition: cut: details item 4 refuses an unknown or repeated number wherever the doc is parsed, and a missing entry means no details; tested.

3. Specify and prove the Codex approval display path.
   [forge next](/src/forge/nextstep.py:339) currently directs Codex to ask a fixed approval question without saying to show the plan first. The proposed approval test covers a top-only plan, but does not establish that a Codex user sees that top part before answering.
   Disposition: cut: details item 2 has forge next's Codex step say to show the top part first, with tests for both hosts.

## Round 2

4. [The guide](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-SHORTPLAN-1/docs/guide.md:76) still tells Claude users to submit the story doc as the plan. SPEC’s [scope](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-SHORTPLAN-1/plans/FORGE-SHORTPLAN-1.md:58) omits the guide, so a user following it would still see the builder sections. Add the guide and verify its approval instruction in SPEC.
   Disposition: cut: SPEC's Scope adds docs/guide.md and details item 2 names it.

5. I disagree that finding 2 is closed for every parser. [`forge task start`](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-SHORTPLAN-1/src/forge/task.py:130) reads task rows without `story.parse` and checks an approval hash that excludes details. A committed detail-only edit with an unknown or repeated number can therefore pass this path. BRIEF’s [scope and tests](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-SHORTPLAN-1/plans/FORGE-SHORTPLAN-1.md:48) omit `task.py` and a direct task-start refusal case.
   Disposition: cut: details item 4 has forge task start refuse too; task.py joins BRIEF's Scope; tested.

6. Done-when 3 requires uncovered results to remain sentence-only, but its [test instruction](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-SHORTPLAN-1/plans/FORGE-SHORTPLAN-1.md:45) checks only that details arrive. A BRIEF test needs two differently covered results and must assert, in both `forge work` and `forge close`, that the uncovered result’s details are absent. The [current worker brief](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-SHORTPLAN-1/src/forge/worker.py:308) sends every Done-when item together.
   Disposition: cut: details item 3 tests a covered and an uncovered result, the latter's details absent in both.

7. The top-only approval instruction has no fallback for an old-style doc without `## For the builders`; [an existing plan](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-SHORTPLAN-1/plans/FORGE-MERGE-1.md:50) has none. Done-when 4’s [tests](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-SHORTPLAN-1/plans/FORGE-SHORTPLAN-1.md:48) cover old-style work and close, but not renewed approval. Pin what SPEC shows for that input and test it.
   Disposition: cut: details item 2 shows an old-style doc whole, with an approval test.

8. BRIEF’s old-style work and close test does not specify a wrapped or nested Done-when item, though [existing plans use both](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-SHORTPLAN-1/plans/FORGE-FDE-1.md:42). The [current story parser](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-SHORTPLAN-1/src/forge/story.py:265) captures only the first line. Use a real multiline old-style item in BRIEF’s test and assert its full text reaches both worker and reviewer.
   Disposition: cut: details item 4 tests a wrapped old-style item reaching worker and reviewer whole.

## Round 3

9. The numbering contract still leaves duplicate **top-level Done-when numbers** undefined. [The current parser](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-SHORTPLAN-1/src/forge/story.py:265) silently keeps the last item, so a detail numbered `1` cannot be assigned unambiguously if two results are numbered `1`. BRIEF should require a refusal naming the duplicate and test it through `forge read`.
   Disposition: cut: details item 4 refuses a repeated Done-when number, tested through forge read.

10. Details item 4 promises refusal wherever the doc is parsed, but its [malformed-detail tests](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-SHORTPLAN-1/plans/FORGE-SHORTPLAN-1.md:50) cover only `forge task start` and `forge work`. [`forge close` has a separate review parser](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-SHORTPLAN-1/src/forge/review.py:95); the positive close test does not prove it refuses an unknown or repeated detail added after work. Add a malformed-detail close case to BRIEF.
   Disposition: cut: details item 4 tests the malformed-details refusal through forge close too.

