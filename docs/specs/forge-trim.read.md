---
reader: codex (gpt-6-sol)
read_at: 2026-09-27T16:14:04+00:00
read_hash: 7a3185bcf6296de9c76946eb072d70936ec3396d
amended_hash: 4d31ccc99f924ca22e1dcb4d10a1b2b23fe3984b
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. The line target and acceptance criterion disagree.
   The ceiling test counts every newline under `src/forge`; the unchanged tree has 7,961. Removing exactly 400 lines passes the criterion in [forge-trim.md](/docs/specs/forge-trim.md:57) but leaves 7,561, missing the target of 7,560. Pin one exact baseline and one required net reduction. The “about 415” audit also leaves little stated allowance for new shared code.
   Disposition: keep pinned the baseline at 7,961 by the ceiling test's count and the target at 7,561 or fewer

2. The proposed story-doc helpers do not yet have one shared contract.
   [task.py](/src/forge/task.py:38) strips section bodies and hashes missing sections; [story.py](/src/forge/story.py:205) retains section bodies and returns no hash when a section is missing. [review.py](/src/forge/review.py:58) and [records.py](/src/forge/records.py:417) parse further variants. Pin which results each caller must retain before requiring one implementation.
   Disposition: cut helper merging is out of scope now; the target is met by the named removals

3. The shared write helper needs its safety behavior pinned.
   [sync.py](/src/forge/sync.py:139) refuses a path resolving outside the repo; [story.py](/src/forge/story.py:523) and [records.py](/src/forge/records.py:429) do not perform that check. “File read and write helpers become one” does not say how the shared helper preserves the containment check and existing refusal.
   Disposition: cut no shared write helper is introduced

4. Removing the own-repo migration path leaves its refusal unspecified.
   [migrate.py](/src/forge/migrate.py:176) currently recognizes Forge’s source repo before planning, and its own-repo path avoids client deletions. The spec should say how `forge migrate` refuses there after removal, so the client migration path cannot treat a source checkout as a copied-in client.
   Disposition: keep forge migrate refuses before any change in Forge's own repo

5. Cut or defer: consolidation beyond the reduction needed to meet the pinned target.
   The spec requires every helper group in [forge-trim.md](/docs/specs/forge-trim.md:31) to move to one place, but gives no net savings by group. The line target supports the smallest set of safe removals and merges that reaches it; the remaining merges need a stated reason.
   Disposition: cut the spec now names only the removals that reach the target
