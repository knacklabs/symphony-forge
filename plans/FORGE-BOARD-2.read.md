---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-10T11:59:25.857853+00:00
read_hash: bc0464c34624d76599c6b4dd83a156689c07640c
round: 11
passed: yes
doc_seen: bc0464c34624d76599c6b4dd83a156689c07640c
spec_seen: 9c543b4bb7136c37f92d34771337a9fdac3693a9
notes_seen: f114e54ab668741b1fbb9ba78995cf3eed5cf166
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc, then run
`forge read <doc>` again for the next round, until a round finds nothing:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

A finding inside What counts is cut or deferred. Keep one only when it falls outside that boundary
or is factually wrong, and give as the reason the Leave out line, the missing Raise line, the
cited fact that disproves it, or the human's `Decided:` line.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. The waiting-for-approval rule accepts stale reads.
   Raise: Functional. Details 1 uses `passed: yes`, but `story.gate` checks the actual round result and whether the document changed. Editing a plan after a passing read would leave the board requesting approval while `forge next` requests another read. The counts test covers only fresh notes.
   Disposition: keep: waiting for approval now uses `story.gate`, the check forge next uses; the counts test adds a plan edited after a passing read, which counts as planning.

2. Ready-to-merge counts still depend on an unpublished local receipt.
   Raise: Not done. Details 1 reuses `nextstep._item_readiness`, which requires `.git/forge`’s close receipt and a matching local branch. A teammate who only fetches has neither receipt nor necessarily that branch, so the same part becomes “in progress” there. No task replaces this local readiness source.
   Disposition: keep: the shared record carries the clean-review commit, and `nextstep._item_readiness` falls back to PR head equals that commit with checks not failing, so forge next and the board agree on a teammate's machine; the counts test runs on a second clone.

3. Local history can override—and subsequently overwrite—a more complete pull-request history.
   Raise: Functional. Details 5 prefers local logs whenever any records exist. After another teammate continues an item, the original machine retains an incomplete history but still selects it. Its next close can publish that incomplete history over the complete record. The second-clone test uses empty logs and misses this normal handoff.
   Disposition: keep: `time_records.merged` unions the PR record with local logs (deduplicated); close, forge merge and the board all use it; the How it went test has machine B continue machine A's item and checks neither overwrites the other.

4. No task defines how a story’s working and waiting intervals are derived.
   Raise: Plan gap. The Runway requires segmented building-story bars. The prerequisite `where-time-went` implementation explicitly excludes story rows from `time_records.item`; the proposed fallback reads an individual item’s PR body. There is no rule for combining its parts’ histories, concurrent intervals, or committed plan-read rounds. HISTORY’s test exercises only a fix.
   Disposition: keep: `time_records.story` pins story runways (working where any part or plan read round works, waiting where none works and any waits, unknown otherwise, each instant once); the How it went test adds a story case.

5. Conflict waits are never published when close stops.
   Raise: Not done. Details 2 records the conflict wait through `repo.record_event`, which writes an uncommitted local log, immediately before refusing. That refusal precedes normal PR publication. Another teammate cannot see the conflict or its age after fetching; the proposed test observes only the originating machine.
   Disposition: keep: on a conflict stop close records the wait and calls `close.refresh_record` on the PR before refusing; the Needs you test checks it on a second machine.

6. Clearing a review-loop choice can leave teammates waiting for an already-made decision.
   Raise: Functional. The plan adds a push when the stop is created, but not when its choice is recorded. In the prerequisite close implementation, `--resolve narrow` and `--resolve split` save the choice and return before pushing. Other machines retain the published unchosen stop.
   Disposition: keep: close pushes and refreshes the PR record after recording a `--resolve` choice, as after the stop; the Needs you test clears the wait on both machines.

7. A pending worker question prevents the close that is supposed to publish it.
   Raise: Plan gap. Details 2 promises publication at the next close, but close refuses an unanswered question before `_publish`. The specified hidden record also has no pinned question payload or shared equivalent of `question_id`. The local-question test cannot prove the promised publication.
   Disposition: keep: forge work publishes the question and its answer to the PR record when a PR exists (shared fields `{id, reason, since, question}`), and it stays local before a PR, as the spec says; close no longer has to publish it.

8. Older human-merge waits have no discovery rule after upgrading.
   Raise: Not done. Details 2 recognizes merge waits only from a new local event or the new hidden PR record. An older open PR waiting for human merge has neither. It disappears from Needs you rather than appearing with an unknown wait time. The upgrade test contains only merged items.
   Disposition: keep: an open PR ready by the shared rule (or, with no record, a clean review and green checks at its head) in a human-merge repo shows in Needs you with an unknown wait; the upgrade test adds such a fix.

9. The 1,000-PR cap silently truncates required team facts.
   Raise: Scale. A team merging 200 PRs per week produces 1,200 PRs across the required six weeks. The prescribed all-state list cannot contain that history, before accounting for open and closed PRs. No completeness rule marks truncated trends unknown or preserves omitted outstanding waits.
   Disposition: keep: GitHub reads are two cached calls, open PRs plus merged PRs searched from the window start; a list at its 1,000 cap marks the uncovered trend weeks unknown (pace reads git) and flags missing waits; the GitHub test covers the cap.

10. Keeping the seven-day item trim contradicts the promised folded history.
    Raise: Not done. The JSON section retains that trim, while Done when 8 requires every story and fix below the first screen, including done work. The renderer may use only machine output; old finished fixes are absent from `items`, so their rows and details cannot be rendered.
    Disposition: keep: the page renders from `machine_board(…, trim=False)`; only the JSON keeps the 7-day trim; the below-the-fold test includes a fix finished 10 days ago.

11. Unproven: item 6’s visible trends and around-Forge list.
    Raise: Test. TRENDS owns item 6 but has no rendering files in Scope. RUNWAY covers only items 7 and 8. The trends test checks JSON, and neither Runway test requires the visible weekly splits or around-Forge list. All specified tests could pass with that entire page section missing.
    Disposition: keep: RUNWAY now covers item 6 too and draws the trends rows and around-Forge list; a `trends` page test checks them.

12. The task graph permits consumers to start before their required producers.
    Raise: Plan gap. TRENDS’ upgrade test requires `merged_by` and the new time output delivered by HISTORY, but TRENDS depends only on FACTS. PANE must read PRODUCT.md, produced by RUNWAY, but depends only on TRENDS. These required dependencies are missing.
    Disposition: keep: TRENDS now runs after WAITS (which runs after RECORD and COUNTS), and PANE after PAGE, which writes PRODUCT.md in its first commit.

13. Shared guide paragraphs unnecessarily serialize every task.
    Raise: Plan gap. All five tasks include `src/forge/templates/skill.md`; task-start admission rejects overlapping file scopes even when edits concern different paragraphs. Assign the guide updates to one final wiring task rather than making independently buildable work overlap solely through that file.
    Disposition: keep: every skill.md edit moved to one last task, WIRING, after all others, with its own guide test.

14. Removing `stage_counts` breaks an existing test outside every task’s Scope.
    Raise: Gate. `tests/test_machine_views_recent_finished_items.py:211` indexes `stage_counts`; its comparison at line 196 also excludes only the old aggregate field. No task owns updating this file for `team`. The planned removal therefore leaves the suite red with the required repair outside Scope.
    Disposition: keep: tests/test_machine_views_recent_finished_items.py is in COUNTS's scope, the task that removes `stage_counts`.

15. Split: FACTS → counts and cached PR acquisition; owner waits and blockers.
    Raise: Plan gap. FACTS combines a new derivation module, readiness/count changes, caching, close publication changes, review-history extraction, and four new command-level test files. That Scope suggests substantially more than the stated approximately 400-changed-line task limit.
    Disposition: keep: FACTS is split into RECORD, COUNTS and WAITS, each at most about 400 changed lines and three Done-when items.

16. Split: RUNWAY → renderer migration; Runway layout and interactions.
    Raise: Plan gap. RUNWAY combines removal of roughly 200 lines of old derivation/rendering functions, moving statistics, replacing the HTML page, new interval drawings, map collapse, detail rendering, responsive themes, product context, and test migration. This exceeds the requested task-size boundary.
    Disposition: keep: RUNWAY is split into PAGE (frame, renderer migration, lower half, PRODUCT.md) and RUNWAY (first screen and trends), both user-facing.

17. The empty-repo go-live result has two contradictory requirements.
    Raise: Plan gap. “New and existing repos” requires “Not enough history to estimate” with no history. Details 4 requires `done` whenever remaining parts are zero—which is also true immediately after init. The plan does not choose which result takes precedence.
    Disposition: keep: go-live checks "not enough history" first, then "done", then about or range; the pace test covers a fresh repo and an older one with nothing remaining.

18. Unproven: item 3’s looping duration.
    Raise: Plan gap. Details 3 pins duration starts for stalled and dependency-blocking rows, but not looping rows. `review.blocked_rounds` returns only an integer. Builders must choose whether age starts at the first blocked round, the third, or the later stop; the test checks presence and reasons without proving that duration.
    Disposition: keep: `review.blocked_rounds` returns the count and the first consecutive blocked round's date, the looping row's time runs from it, and the blocked test checks a 30-hour duration.

19. The first-screen test contradicts its own fixture and acceptance criterion.
    Raise: Plan gap. Its fixture has two blocked rows, but its assertions require “exactly 5 rows per list.” Done when 7 requires *at most* five. The test contract cannot be satisfied faithfully for that fixture.
    Disposition: keep: the fixture now expects 5 Needs you rows with "and 2 more", 5 In progress rows with "and 1 more", 2 Blocked rows with no "more", and no list over five rows.

No files changed; tests were not run. Runtime behavior remains unverified.

## Round 2

20. Disputed keep 3: the shared record cannot transmit a wait’s ending.
    Raise: Functional. The format carries only `open_waits`, without closed wait IDs or end times, yet merging requires “an end on either side.” If machine B answers A’s question and publishes an empty list, A’s stale logs still contain the open wait and can resurrect it. Absence cannot distinguish a cleared wait from an unpublished local wait.
    Disposition: keep: the shared record now carries every wait as `{id, reason, since, ended}` and never drops an id; a wait is open only when no side has an end; the Needs you test has B answer A's question and checks A's stale log does not bring it back.

21. Disputed keep 2: an existing local receipt still grants readiness for an outdated branch.
    Raise: Functional. Details 1 preserves today’s receipt-versus-local-head rule. After B pushes another commit, A’s fetch updates `origin/<branch>` but leaves its local branch and receipt matching the old commit. A can report ready while B reports in progress. The second-clone test covers missing receipts, not stale receipts after a handoff.
    Disposition: keep: readiness now always compares the clean-review commit (receipt or shared record) with the PR's head from GitHub or origin, never the local branch, in forge next too; the counts test has A keep a stale receipt after B pushes, and both report in progress.

22. Disputed keep 5: a conflict on the first close has no pull request to refresh.
    Raise: Not done. Details 2 assumes “the PR exists.” In `close.py`, `_merge_default` runs before the first `_publish`; a normal first close can therefore stop on a conflict before creating any PR. `refresh_record` only updates an open PR, leaving this conflict unpublished. No rule or test covers that path.
    Disposition: keep: a conflict on a first close with no PR now shows only on that machine until the next publish carries it, the same rule as a worker question; the Needs you test checks that local case.

23. Disputed keep 9: the oldest returned merge does not establish which weeks are complete.
    Raise: Scale. At 200 merges per week, the six-week query exceeds its cap. The prescribed search does not request merge-date ordering, so returned rows need not form a complete suffix by merge time. Omitted PRs can belong to weeks still reported as known, including the around-Forge list’s last seven days. [GitHub CLI’s query construction](https://github.com/cli/cli/blob/trunk/pkg/cmd/pr/shared/params.go#L219-L248) provides no such ordering guarantee.
    Disposition: keep: merged pull requests are now read with one date-bounded search per week (plus the open list, eight calls cached together for 60 s); a week whose search hits the cap is unknown, and so is the around-Forge list when its weeks are capped; the GitHub test covers it.

24. Disputed keep 12: the revised task graph still starts consumers before their producers.
    Raise: Plan gap. PAGE starts after COUNTS, whose wait and blocker fields remain null, but must prove sorting by facts delivered by WAITS. PANE’s required parity test compares against RUNWAY’s first screen, yet PANE need not wait for RUNWAY. COUNTS also needs the six-week query boundary before TRENDS delivers `full_weeks`; that shared helper needs an earlier owner.
    Disposition: keep: PAGE now runs after WAITS, PANE after RUNWAY, and COUNTS owns `full_weeks`, which TRENDS reuses.

25. WIRING postpones guide updates beyond the change that requires them.
    Raise: Gate. AGENTS.md requires coordinator or worker guidance updates “in the same change,” with omissions reported as P1. Each preceding task merges separately, while WIRING waits until all have merged. COUNTS can therefore ship its changed JSON contract and readiness rule with the old guide. My earlier consolidation suggestion missed this gate.
    Disposition: keep: WIRING is dropped; each task updates its own skill.md paragraph in the same change, and the graph never runs two tasks that list skill.md at once.

26. Review-round merging does not define how finding classifications are recomputed after a handoff.
    Raise: Plan gap. The prerequisite `time_records.item` computes new versus repeated findings from local history. B’s first local review can classify A’s repeated finding as unknown. The proposed merge only unions round records; it does not recompute classifications using the combined history. The specified test checks agreement and retention, so both machines can agree on an incorrect unknown classification.
    Disposition: keep: after merging records, the time breakdown and each round's new versus repeated findings are recomputed from the combined rounds; the handoff test has a finding first seen on A repeated on B and counted as repeated on both machines.

27. Unproven: item 9’s compatibility with an older Forge that has no `team`.
    Raise: Test. PANE promises to accept absent `team`, but its new test uses the new fixture, and that shared fixture is updated to include `team`. Existing older-version coverage tests rejection of `--json`, not valid older board JSON without `team`. These tests can pass while the pane fails in a normally pinned older repo.
    Disposition: keep: PANE first copies today's tests/fixtures/board.json to tests/fixtures/board-previous.json, and the pane test checks that it draws the live rows with no team lines from it.

No files changed; tests were not run. Runtime behavior remains unverified.

## Round 3

28. Disputed keep 21: a stale receipt still overrides a newer valid shared review.
    Raise: Functional. Details 1 chooses the local receipt whenever it exists, falling back to the shared record only otherwise. After B closes the newer commit cleanly, A’s old receipt fails the PR-head comparison while B’s current record passes. A reports in progress and B reports ready. The counts test stops after B pushes, before B closes again.
    Disposition: keep: the shared record now holds `clean_reviews: [{commit, at}]`, merged by union; ready means the PR head is in the local receipt or that list and checks are not failing; the counts test has B close the newer commit clean and both machines report ready.

29. Disputed keep 27: PANE copies the previous-board fixture after COUNTS has changed it.
    Raise: Plan gap. COUNTS updates `tests/fixtures/board.json` for the new contract and merges before PANE starts. PANE’s instruction to copy that file unchanged therefore captures the new board containing `team`, contradicting the required older-board fixture without `team`. The snapshot needs an owner before that update.
    Disposition: keep: COUNTS, the first task that changes tests/fixtures/board.json, first copies it unchanged to tests/fixtures/board-previous.json; PANE only reads that snapshot.

30. Disputed keep 22: the local-only conflict exception changes the confirmed behaviour.
    Raise: Not done. The unchanged confirmed spec explicitly permits pre-PR worker questions to remain local, but promises merge conflicts in every teammate’s Needs you view. The revised builder details instead omit first-close conflicts from other machines until publication, while Done when 2 still requires every such wait. This narrows the promised behaviour without a recorded human decision.
    Disposition: keep: the confirmed spec stands; on a first close that stops on a conflict, close pushes the branch and opens the pull request with the open conflict wait in its record, then refuses; only a pre-PR worker question stays local; the Needs you test has B see A's first-close conflict.

31. Looping detection still prefers a stale local branch after a handoff.
    Raise: Functional. Details 3 passes the local branch to `review.blocked_rounds` whenever one exists. If A retains one blocked round and B pushes three consecutive blocked rounds, A’s fetch updates only `origin/<branch>`; A’s board still examines its old branch and omits the looping item. The blocked test covers only one machine.
    Disposition: keep: every board read of review history and readiness, `blocked_rounds` included, uses `nextstep.review_ref`: the PR's head unless the local branch contains it; the blocked test has A keep one blocked round while B pushes three, and A shows looping after a fetch.

32. Shared readiness can recommend a merge that the receiving machine cannot run.
    Raise: Functional. In an agent-merge repo, `nextstep._item` recommends `forge merge` for ready items. The revised rule grants readiness without a local receipt, but `merge.py` still refuses without that receipt and requires a local worktree. No task owns this continuation path; the second-clone test checks readiness without executing its recommended command.
    Disposition: keep: `forge merge` still requires a local receipt; an item ready only through the shared record still counts ready, and its next step there is `forge close <item>`, which re-verifies and writes the receipt; COUNTS says so in its guide paragraph, and the counts test runs that step on the second clone.

33. RECORD does not define how conflicting `clean_review` values merge.
    Raise: Plan gap. The shared format includes `clean_review`, but `time_records.merged` specifies reconciliation only for intervals, rounds and waits. After reviews on two machines, their clean-review commits can differ. Readers and writers need one rule selecting or invalidating that field; neither the handoff test nor the counts test proves this conflict.
    Disposition: keep: `clean_reviews` is a list merged by union on commit, so two machines' clean reviews never conflict; the counts test covers clean reviews from both machines.

No files changed; tests were not run. Runtime behaviour remains unverified.

## Round 4

34. Disputed keep 32: `forge close` also requires a local worktree that fetching does not create.
    Raise: Functional. A teammate who clones the default branch and fetches can now see shared readiness, but the recommended `forge close <item>` immediately reaches `_worktree` and refuses: “Forge has not started … in any worktree of this repo.” The plan defines no step to obtain that worktree. A second-clone test that creates one beforehand would bypass the failing continuation.
    Disposition: keep: without the item's worktree, a shared-only ready item now shows a plain line naming its starter who merges it, with no runnable command; `forge close` is offered only where the worktree exists; the counts test covers both; taking over another person's item stays out of scope (Notes).

No files changed; tests were not run. Runtime behaviour remains unverified.

## Round 5

35. The shared-only ready next step ignores `merge = "human"`.
    Raise: Functional. Details 1 tells a teammate without the worktree that the starter must merge from their machine, regardless of the merge setting. In a default human-merge repo, the owner can merge the ready PR on GitHub without either the worktree or a local receipt. The new line incorrectly redirects that owner to the starter; its test requires the same unqualified instruction.

No files changed; tests were not run. Runtime behaviour remains unverified.
   Disposition: keep: the no-worktree line now follows the merge setting: agent merge names the starter, human merge gives forge next's existing merge-on-GitHub line; the counts test covers both.

## Round 6

36. No findings.

No files changed; tests were not run. Runtime behaviour remains unverified.
   Disposition: keep: not a finding; the reader reported none (numbered by mistake).

## Round 7

37. No findings.

Tests were not run; runtime behaviour remains unverified.
   Disposition: keep: not a finding; the reader reported none (numbered by mistake).

## Round 8

38. No findings.

Tests were not run; runtime behaviour remains unverified.
   Disposition: keep: not a finding; the reader reported none (its tests-not-run note had a trailing clause the parser missed; fix read-note-tail).

## Round 9

39. Backfill labels unrecorded elapsed time as working.
    Raise: Functional. Item 10 counts everything between a start commit and the next review commit as building or fixing. An item started Friday and resumed Monday therefore acquires a weekend of working time without activity evidence, contradicting the confirmed spec’s requirement that unsupported spans remain unknown.
    Disposition: cut: the backfill now leaves building, fixing and reviewing unknown (commits are moments, not spans); the upgrade test checks no working seconds between start and review commits.

40. The backfill retry instruction stops working once the upgrade merges.
    Raise: Functional. Item 10 tells users to rerun `forge upgrade` after a failed backfill. `upgrade.py` refuses when the requested release is already pinned, before reaching close. After the upgrade merges, that retry cannot rebuild the missing histories; BACKFILL owns no change to this route.
    Disposition: cut: a failed backfill leaves a local marker and the next forge close on that machine retries it; the line says so, and the upgrade test retries through a later close.

41. Unproven: item 10: rebuilding reviews after squash merge and branch cleanup.
    Raise: Plan gap. Forge squash-merges and removes the item’s local branch and worktree; GitHub commonly deletes its remote branch too. Individual review commits are not ancestors of the squash commit. Item 10 specifies neither retrieval of the PR’s original commits nor a test without surviving item refs, although rebuilding their rounds requires that history.
    Disposition: cut: the backfill fetches each in-scope PR's refs/pull/<number>/head, which GitHub keeps after the branch is deleted, and reads its original commits; the upgrade test deletes the 3-week-old fix's branch locally and on origin.

42. The shared record has no owner for preserving rebuilt provenance.
    Raise: Plan gap. BACKFILL introduces `rebuilt: true`, but RECORD’s schema and `merged` rules omit it, and `from_body` ignores unknown fields. BACKFILL’s Scope excludes `time_records.py`. The plan does not pin how parsing, subsequent closes and merged records retain the label required by item 10.
    Disposition: cut: RECORD now owns `rebuilt` in the record, and `time_records.merged` keeps it when either side has it; the upgrade test re-closes the open fix and still sees "rebuilt from history".

43. Backfill’s six-week window includes older work.
    Raise: Functional. Item 10 uses the weekly-search window, which contains six completed weeks plus the current partial week. On Sunday that includes merges almost seven weeks old, while the owner-facing requirement says items merged earlier than six weeks keep unknown times. The three-week and eight-week fixtures miss this boundary.
    Disposition: cut: the backfill cuts at exactly 42 days, using the weekly searches only as its source; the upgrade test, clock on a Sunday, rebuilds a fix merged 41 days ago and not one merged 43 days ago.

44. The new building rule excludes an unstarted dependency bottleneck.
    Raise: Functional. Item 3 selects “blocks the most” only from building stories. With the revised counts, an approved story whose parts have not started is excluded—even when its first part blocks several unfinished parts in another story. The existing blocker test does not cover this normal cross-story case.
    Disposition: cut: blocks the most now ranges over parts of every approved story, started or not, across stories; the blocked test uses an unstarted story's first part blocking a chain into another story.

45. PAGE and RUNWAY must prove features delivered by later tasks.
    Raise: Plan gap. Browser proof requires every listed task to verify the completed first screen and dependency graph before close. PAGE precedes RUNWAY, and GRAPH follows RUNWAY and PANE. PAGE cannot prove RUNWAY’s first screen, and neither PAGE nor RUNWAY can prove GRAPH’s implementation before their own merges.
    Disposition: cut: each page part proves in the browser only what it delivers at its close, and GRAPH, the last to change the page, reruns every check on the finished page.

46. Required screenshots are outside every producing task’s Scope.
    Raise: Gate. Browser proof requires PAGE, RUNWAY and GRAPH to commit PNGs under `docs/board-screens/`. None of their Scope cells includes that directory, so all three required proof commits introduce files outside their authorized scope.
    Disposition: cut: docs/board-screens/ is in the Scope of PAGE, RUNWAY, NAV and GRAPH, the parts that commit screenshots.

47. Split: PAGE → renderer migration; navigation and story histories.
    Raise: Plan gap. PAGE now combines the old-page removal and replacement layout with sticky navigation, folding sections, story keys, shipped guidance changes, cold-read history extraction and three additional test files. This expanded Scope exceeds the approximately 400 changed-line boundary that previously required splitting the renderer work.
    Disposition: cut: PAGE keeps the renderer migration and lower half; a new part, NAV, after RUNWAY and beside PANE, takes the section bar, folds, story keys with the AGENTS.md line, and story histories, with its own tests.

Tests were not run; runtime behaviour remains unverified.

## Round 10

48. The history range is empty for an ordinary merge commit or fast-forward merge.
    Raise: Functional. Item 10 reads from the current default branch’s merge base to the PR head. After either merge type, that head is already an ancestor of the default branch, so the merge base equals the head and the range contains no review commits. Fetching the retained pull ref does not fix this; the new test targets squash merges.
    Disposition: cut: the rebuild now walks back from the pull head to the item's own start commit, never a merge base; the upgrade test adds a fix merged by an ordinary merge commit and one fast-forwarded, each keeping its rounds.

49. Backfill introduces a record without defining how legacy readiness survives it.
    Raise: Plan gap. Item 1 permits the legacy clean-state fallback only when neither a receipt nor a shared record exists. BACKFILL creates that record but supplies no reconstruction rule for `clean_reviews`. On a teammate’s clone without the old receipt, a previously ready PR consequently loses its readiness evidence. The upgrade test does not check readiness on that clone after backfill.
    Disposition: cut: the rebuilt record lists in `clean_reviews` every pushed head whose state file shows the older clean-and-ready rule; the upgrade test checks a second clone without the receipt reports the open fix ready.

50. Unproven: item 10: a failed publication after successful GitHub reads.
    Raise: Plan gap. The retry marker is deleted “once GitHub answered,” without requiring every PR update to succeed. A successful list followed by a failed PR-body edit leaves an item unreconstructed. The plan pins no completion rule retaining the retry marker in that case; its wholly failing GitHub stub does not prove this path.
    Disposition: cut: the retry marker is deleted only when every in-scope item then has a record, so any failed read or PR body write keeps it; the upgrade test fails one body edit and the next close completes it.

Tests were not run; runtime behaviour remains unverified.

## Round 11

No findings.
