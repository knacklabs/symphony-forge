---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-01T03:28:47+00:00
read_hash: 115f4015e8a6f8faebe876c7cfedfabd54b0f4fd
round: 3
passed: no
doc_seen: 115f4015e8a6f8faebe876c7cfedfabd54b0f4fd
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 7e9df5f55c6bd3019dc0d2e30c11f563c4c06fc7
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc, then run
`forge read <doc>` again for the next round, until a round finds nothing:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. Item 1 records the reviewer’s citation, which can point to the wrong file for an outside-change problem.
   [review.md:150](src/forge/templates/review.md:150) requires every finding to cite a changed file; item 1 copies that location into the list. Advice about an untouched dependency can therefore create a hotspot in its caller. SPOT must pin how reviews identify the actual problem file and test that case.
   Disposition: keep the review's cited path and line are recorded as they are, now stated in item 1 with a test; src/forge/templates/review.md:150 pins every finding to a changed line, and the Decided line on what reviews report makes their advice findings spotted items as they stand.

2. Item 5 can stop a change for a problem its prerequisite fix cannot reach.
   Findings may concern a newly added file or missing behavior introduced by the stopped change. But [task.py:230](src/forge/task.py:230) starts fixes from the default branch, where that file or behavior may not exist. Pin which findings can trigger this stop and prove the branch-only-file case in `tests/test_hotspot_stop.py`.
   Disposition: cut a file only on the item's branch never stops it (item 5's one rule: F must be a file on the default branch), with its test.

3. Unproven: item 1 accepts incomplete entries that later features cannot reliably consume.
   The reader checks only string `key`, `path`, `kind` and `status`, while hotspots and stops also require `from`, `item`, `text` and numeric `round`. An entry containing only the four checked fields passes the stated validation. Pin validation for every consumed field and test the advertised refusals through close and next.
   Disposition: cut spotted.read now refuses anything but exactly the listed fields with their types and values; a missing-field test added.

4. Item 1’s recovery command cannot repair a corrupt default-branch list.
   Checking out `origin/<default>:plans/spotted.json` restores the same corruption when the default branch is unreadable, and fails when that file is absent there. Pin a working recovery for both states and test it in `tests/test_spotted.py`.
   Disposition: cut the refusal's repair is the default branch's copy when that reads, else git rm; both tested, and running the repair is tested.

5. Item 1’s sorted-file contract conflicts with the unchanged merge driver.
   [sync.py:225](src/forge/sync.py:225) preserves ours’ order, then appends theirs’ new entries. Individually sorted branches can therefore merge into an unsorted list. Either relax the ordering contract or assign sorting to the merge path; test additions whose keys interleave.
   Disposition: cut the sort rule now applies to Forge's writes only; nothing reads the file's order; the interleaving merge test keeps every entry.

6. Items 1 and 5 contradict each other about when Forge writes the list.
   Item 1 permits changes only in a review commit; item 5 requires a separate carry-on commit containing the list. Explicitly permit that exception, or fold the update into the next review commit, and make the commit-history test cover resumption.
   Disposition: cut the carry-on commit is gone; resuming forces a new review, whose review commit carries the state.

7. Unproven: item 1 loses new worker observations when close reuses its review.
   Recording runs only in the new-review or dismissal branch. A new empty or bookkeeping commit carrying `Spotted:` can leave the review fingerprint unchanged, so its observation is never recorded. Pin collection on this path and test it without another Autoreview call.
   Disposition: cut record runs on every close that reaches the review step, reused review included, and close commits when it changed the list; tested with an empty Spotted commit and no Autoreview call.

8. Item 3 leaves the blocking count ambiguous when several kinds qualify.
   With two distinct items reporting `bug` and three reporting `simplify`, “count those items” could produce different counts. Pin the selection rule and test it in `tests/test_hotspots.py`, alongside the promised `open` precedence when both hotspot rules qualify.
   Disposition: cut the blocking count is the largest distinct-item count of any one kind; tested, with the open-wins case.

9. Unproven: items 3 and 5 promise runnable commands without proving Windows shell argument handling.
   `shlex.split` proves POSIX tokenization; the harness invokes Python directly. Assign command round-trip checks through PowerShell and cmd, including punctuation in finding text, or state which shells the printed commands support.
   Disposition: cut fix texts keep only letters, digits, spaces and .,:;/_- and recorded paths only letters, digits and ._/-, so double quotes hold plain text in POSIX shells, PowerShell and cmd; tested.

## Round 2

10. Trap: shell quoting: item 5 bypasses item 1’s safe-path restriction.
    `flagged` and `F` now come directly from blocking findings. An existing file such as `src/$cache.py` can reach `fix_text`, which embeds its path unchanged inside double quotes; shells can expand it. Apply the safe-path rule to stop candidates and prove this case in `tests/test_hotspot_stop.py`.
    Disposition: cut a stop file must pass item 1's path rule too, else the review refuses with blocked as today; the `src/$cache.py` case is tested.

11. Item 1’s claim that recording never makes a review stale contradicts the fingerprint implementation.
    [review.py:120](src/forge/review.py:120) includes planning files named in a fix’s done-when. If that text names `plans/spotted.json`, recording after review changes a fingerprinted file. Pin consistent treatment of this generated file and add that regression to `tests/test_spotted.py`.
    Disposition: cut review.fingerprint skips plans/spotted.json even when a fix's done-when names it (review.py added to SPOT's scope); tested with no second Autoreview call.

12. Item 5 now resumes before the required simplifying fix has merged.
    Any merged change to `F`, including unrelated formatting, releases the stop permanently. Done when 5 and the guide still require the simplifying fix to merge first. Align the resumption condition with that promise and test an unrelated change arriving while the fix remains open.
    Disposition: keep (revised in round 3) the item carries on once F's content on the default branch differs from the stop's; the printed fix does that, and one content check also survives promotion to a story and repeated why texts (findings 17 and 19), where any fix-identity rule needs more cases; the wait still holds against changes to other files, tested (plans/FORGE-SPOTTED-1.md item 5).

13. Risks omits the new deletion of recorded observations during repair.
    When the default copy is unreadable, item 1 recommends deleting the entire list, including otherwise valid entries surrounding one malformed entry. Prefer restoring a readable version where available, name any remaining reset loss under Risks, and test preservation of existing observations.
    Disposition: cut the repair restores the newest readable copy in the default branch's history, so no readable entry is lost; rm only when no readable copy ever existed; tested.

14. Finding 2 is only partly cut: branch-introduced defects in existing files still produce unreachable fix requirements.
    A repeated `Not done` finding about a new endpoint in an existing `api.py` passes the default-file check, but its fix starts without that endpoint. The generated done-when can require implementing the stopped change rather than simplifying its baseline. Pin a reachable simplification criterion and prove this case in `tests/test_hotspot_stop.py`.
    Disposition: cut the stop's fix no longer carries the review's findings; it asks only to simplify F as it is on the default branch; tested that the done-when holds no finding title.

15. Unproven: item 5: `F` disappears from the default branch.
    The new rule explicitly resumes when `F` is gone, but the tests cover only changed contents. Add the deletion case, including the expected refusal when merging it conflicts with the stopped branch’s edits, and verify resumption after resolution.
    Disposition: cut (revised in round 3) F deleted on the default branch resumes like a change; the merge first hits close's existing conflict refusal (src/forge/close.py:192), and once resolved the next close carries on; tested.

## Round 3

16. HOT → STOP is now an artificial dependency caused by shared wiring.
    Notes explicitly says STOP uses no name HOT adds. Move their shared `nextstep.py`, Hotspots guide section and synced-copy edits into a small final wiring task; let the implementation tasks follow SPOT, with output tests owned by the wiring task.
    Disposition: keep STOP and HOT both edit nextstep.py's `_report`/`_item` (src/forge/nextstep.py:144, :393) and the skill template with its two synced copies, so running them one after the other avoids conflicts in shared files; a fourth wiring task would add a task and a handoff for no gain at this size.

17. Unproven: item 5: promoting the required fix to a story leaves the original item waiting forever.
    [story.py:711](src/forge/story.py:711) deletes the fix state and transfers it to a task. After that task merges, no matching state exists under `.factory/fixes/`. Pin resumption through the supported promotion flow and prove it in `tests/test_hotspot_stop.py`.
    Disposition: cut resumption now reads only F's content on the default branch, so a fix promoted to a story (src/forge/story.py:711) resumes the item when its task merges.

18. Item 1’s repair cannot reconstruct observations from earlier branch reviews.
    A finding recorded in round 1 may disappear from round 2’s clean result. Restoring only the default branch’s list loses that branch-only entry, and recording the latest result cannot recreate it. Preserve the branch’s readable history too, and test this sequence in `tests/test_spotted.py`.
    Disposition: cut the repair restores the newest readable copy in the branch's own history, which holds its earlier review commits and merged default commits; a round-1 entry dropped by round 2 comes back, tested.

19. Item 5’s assertion that no earlier fix can have the same why is unsupported.
    [task.py:224](src/forge/task.py:224) accepts arbitrary, repeated why text; only fix names are made unique. A previously merged fix with the generated why would immediately release a new stop. Pin exclusion of fixes already merged when the stop was recorded and test that case in `tests/test_hotspot_stop.py`.
    Disposition: cut resumption no longer matches why texts or fix records, only F's content changing since the stop, so an earlier fix with the same why can't release it.
