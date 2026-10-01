---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-01T02:36:42+00:00
read_hash: 9aa7d0a19337df78cec5f401feb507fe8cf6f17b
round: 1
passed: no
doc_seen: 9aa7d0a19337df78cec5f401feb507fe8cf6f17b
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
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
