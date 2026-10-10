---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-10T03:07:02+00:00
read_hash: ee66620d08c255c7472cecf320be3f3a4515f77c
round: 10
passed: yes
doc_seen: ee66620d08c255c7472cecf320be3f3a4515f77c
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 17d359d2b8a4d73e030854c3d77df798ad2156c6
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc, then run
`forge read <doc>` again for the next round, until a round finds nothing:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. The first-screen promise cannot hold for an unbounded team backlog.
   Behaviour 1 requires every human-waiting item and one bar per active story without scrolling. Twenty approvals alone can exhaust a laptop screen. Pin a viewport and bounded summaries with access to the complete lists; clarify how this applies to the Claude Code terminal pane.
   Disposition: keep: the first screen is pinned to a 1440x900 window with at most five rows per list and the full lists below; the pane shows only the summary lines.

2. Unproven: item 4: “recent pace” does not define a reproducible forecast.
   Define which planned work qualifies, what counts as finished, the pace window, and how its endpoints produce the range. With zero completions or insufficient history, a builder could invent a range and satisfy the current wording. Require an explicit unavailable estimate when evidence cannot support one.
   Disposition: keep: the estimate is pinned (remaining parts of approved stories over the 3- and 6-week average merge rates, merges from git), with an explicit "not enough history" note.

3. A fetch cannot deliver the team-wide activity and waiting evidence this spec promises.
   `src/forge/repo.py` stores timings and events in uncommitted `.git/forge/`; machine queues are local too. Someone fetching another developer’s branch receives neither. Pin what evidence is shared and how, or explicitly show unavailable remote activity and durations as unknown. Upgrading cannot reconstruct those facts from git and GitHub.
   Disposition: keep: owner chose (2026-10-09) that close writes each item's time breakdown and rounds into its pull request so every board reads them from GitHub; live machine facts stay local and show only there.

4. Unproven: item 5: recorded stage durations do not establish working versus waiting time.
   Existing stages are Build, Tests, Review, CI and Merge; they do not partition machine-queue waits, unanswered questions and approval waits. Build can also contain tests. Define interval boundaries and overlap handling so a worker testing during Build cannot be counted twice, and unrecorded gaps cannot become invented waiting time.
   Disposition: keep: working and waiting are defined by recorded intervals counted once; unrecorded time shows as unknown, never as waiting.

5. Unproven: item 3: the rules selecting and ranking attention items remain ambiguous.
   The current board marks an item stalled after 24 idle hours, but the spec neither adopts that rule nor defines another. Pin which states qualify, when each human wait begins and ends, how repeated requirements are identified, and whether “blocks the most” counts direct or transitive dependants. Otherwise two implementations can produce different priority lists from identical evidence.
   Disposition: keep: stalled is 24 hours without recorded activity, looping is three or more blocked review rounds, waits run between the records that create and clear them, and blocking counts direct and indirect dependants.

6. The promised ownership answers exceed the identity evidence specified.
   “Who started it” does not establish who currently owns it or who is free or overloaded. Existing approval display uses a git commit author, which need not identify the human who approved; parts and fixes also need an explicit rule for whether approval applies. Either narrow the role promises to recorded attribution or define authoritative responsibility and approval evidence, with unknown when absent.
   Disposition: keep: the spec shows who started and who approved as recorded, or unknown; who is free or overloaded moved to Out of scope beyond counting each person's started items.

7. Unproven: item 2: the counting and completion rules are not pinned.
   Define the mapping for approved-but-unstarted stories, stories whose parts are ready to merge, and missing or malformed plans. Define whether “finished” means merged or another event, and how the seven-day total separates stories, parts and fixes. Current JSON omits old finished rows, so the six-week pace also needs historical aggregates in the shared JSON contract.
   Disposition: keep: story, part and fix states are mapped, finished means merged, they are counted separately, and pace reads merge dates from git rather than the board's recent rows.

8. The first-screen “In progress” section omits active fixes.
   Behaviour 1 gives bars only to stories, although the Why explicitly identifies buried open fixes as a problem. A repo running only fixes could show no named work in progress until below the fold. Include active fixes in the bounded progress summary.
   Disposition: keep: In progress now has a row per open fix as well as a bar per building story.

9. Trap: no network in CI: item 7 has no executable upgrade or recovery contract.
   `forge upgrade` currently installs, syncs and closes an upgrade fix; it does not invoke an agent to recover history. Name where that work runs, which facts it may recover, where results belong, and how repeat runs preserve existing evidence. Require unavailable GitHub evidence to remain explicitly unknown, and verify recovery without live network access for an earlier adopted client.
   No files changed; runtime and visual checks were not run. The findings concern approval-contract gaps.
   Disposition: keep: the upgrade guide runs one Forge command that fills missing facts from git and GitHub, adds only what is missing, and leaves unreachable facts unknown.

## Round 2

10. Disputed keep 7: the new counting definitions still overlap.
    A drafted plan awaiting approval has “no approved plan,” so it qualifies as both no-plan-yet and planning or waiting-for-approval. A ready part is also started and unmerged, hence in-progress. Define exclusive classification precedence; otherwise totals and the forecast’s unknown backlog can contradict the cards.
    Disposition: keep: states are now exclusive by an ordered rule for stories and for parts and fixes.

11. Disputed keep 2: the forecast formula can violate “never a single date.”
    If two parts merge every week, the three- and six-week averages produce identical endpoints. Zero remaining parts also produces identical endpoints. Pin truthful displays for these cases without inventing uncertainty. Acceptance criterion 4 and the success measure must also permit the insufficient-history fallback already allowed by criterion 1.
    Disposition: keep: equal endpoints show "about" one date with "pace has been steady", nothing remaining says done, and criterion 4 allows these and the no-history note.

12. Disputed keep 5: the stalled rule includes finished and deliberately unstarted work.
    “Items with no recorded activity for 24 hours” includes last month’s merged fixes and old backlog items. Those can occupy the urgent summary despite needing no action. Restrict stalled eligibility to specified unfinished states; unavailable activity evidence must remain unknown.
    Disposition: keep: stalled covers only started, unfinished parts and fixes, and items whose activity can't be seen are left out.

13. Unproven: item 2: the new readiness definition contradicts `forge next`.
    `nextstep._item_readiness` retains readiness when a clean close receipt matches the current commit and checks are running or unavailable; the spec requires green checks. Conversely, “clean review and green checks” omits the requirement that the review cover the current commit. Choose one shared rule so an old clean review cannot make changed work ready.
    Disposition: keep: ready to merge uses forge next's shared rule (clean review of the current commit, checks not failing).

14. Unproven: items 3 and 5: publishing history only through close misses waits the board must show.
    A worker can ask its first question before any pull request exists, and a planning story has no defined pull request for its reader history. Close also currently publishes before its CI wait finishes; a subsequent human-merge wait ends after close returns. Keep the owner’s chosen PR storage, but pin the publication lifecycle and the destination for stories so these records become visible without another discretionary close.
    Disposition: keep: every close and the merge update How it went; story reads are in committed read notes; a pre-PR question shows locally until the next close.

15. Cut or defer: item 6: phone layout remains required after phones moved out of scope.
    The Out-of-scope section excludes showing the board on a phone, while criterion 6 still requires a phone column layout. Remove that requirement or explicitly retain responsive layout within scope.
    Disposition: keep: narrow windows stack to one column; only phone and client audiences stay out of scope.

16. Disputed keep 9: the recovery command still has no defined write destination.
    The revised text names its sources and missing-only policy, but never says where recovered facts are added. Copying git facts into `.factory` would conflict with the repository’s “one home per fact” rule. Pin the destination and why recovery needs a write rather than the board reading the existing evidence.
    No files changed; runtime checks were not run. These are specification gaps, not demonstrated runtime failures.
    Disposition: cut: the upgrade writes nothing; the board reads older items' facts straight from git and GitHub.

## Round 3

17. Disputed keep 14: “again at merge” does not cover the default human-merge path.
    A human merging in GitHub runs neither close nor `forge merge`; the latter refuses when merge is configured as human. Pin how that path completes the published history, or derive the final merge wait from GitHub when reading the board. Otherwise the human wait can remain unfinished in “How it went.”
    Disposition: keep: a human merge on GitHub ends the last wait at the PR's merge time read from GitHub.

18. Disputed keep 11: equal forecast endpoints do not prove that pace has been steady.
    Six weekly completion counts of 0, 6, 0, 0, 0, 6 give identical three- and six-week averages despite bursty delivery. Use “the two pace estimates agree,” or require an actual stability rule before claiming steady pace.
    No files changed; runtime checks were not run. These findings concern specification rules.
    Disposition: keep: the wording is now "the two pace estimates agree", claiming nothing about steadiness.

## Round 4

19. Disputed keep 18: acceptance criterion 4 still requires steady pace for the single-date fallback.
    Behaviour now allows equal estimates without claiming steadiness, but criterion 4 retains “when the pace has been steady.” The bursty example from finding 18 therefore still passes Behaviour and fails acceptance. Change criterion 4 to “when the two pace estimates agree.”
    No files changed; no runtime checks run. This is a remaining contract contradiction.
    Disposition: keep: criterion 4 now says "when the two pace estimates agree".

## Round 5

No findings.

## Round 6

No findings.

## Round 7

20. Cut or defer: per-person merged pull request trends.
    Raise: Plan gap. Behaviour 5 and acceptance criterion 7 add six weeks of historical throughput for each author. The Why asks who owns current work and what waits on them; historical merge counts answer neither. The success measure and recorded owner decision require team status and a planned-work forecast, neither of which needs per-person throughput.
   Disposition: keep: owner chose (2026-10-09) to show team and per-person weekly merged work through Forge and around it, each person's own trend with no ranking, so a team sees how much ships outside Forge; the Why and Options weighed now record it.

## Round 8

No findings.

## Round 9

21. The new column rule has no valid layout for cross-story dependency cycles.
    Raise: Plan gap
    Behaviour 2 and acceptance criterion 7 put each part one column after its latest prerequisite. Two story plans waiting on each other make that impossible.
    `src/forge/story.py:930–941` explicitly permits cross-story cycles; their tasks wait in `forge next`. Ordinary edits to separate plans can therefore produce supported inputs that the new graph has no rule for displaying.
   Disposition: keep: behaviour 2 and criterion 7 now say parts waiting on each other in a loop share the earliest column they could otherwise take, labelled as waiting on each other.

## Round 10

No findings.
