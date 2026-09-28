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

