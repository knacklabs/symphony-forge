---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-11T09:26:58.182344+00:00
read_hash: adb38ab59435bcf98c85e73ea24b5f50078d4ffb
round: 2
passed: no
doc_seen: adb38ab59435bcf98c85e73ea24b5f50078d4ffb
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 7e09660d978a17e2ddbba26a7157292f4ccb47d1
conversation: 01a12a0d-b795-74e2-83ae-0c4b25007a01
session:
blocked_rounds: 2
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

1. Blocking: The three-part chain contradicts the promise that each pull request shows only its own changes.
   Raise: Not done.
   `plans/FORGE-STACK-1.md:36` requires this throughout the unmerged stack, but lines 164–166 explicitly allow the top pull request to show inherited history after the middle part replays. The item-3 test checks only line counting, so it does not prove the promised pull-request diff.

Disposition: cut

2. Blocking: The start rule accepts an outdated clean review.
   Raise: Plan gap.
   `plans/FORGE-STACK-1.md:74–76` checks only the pushed state's `review.status`. A normal worker retry after failed CI preserves that review while changing and pushing code (`src/forge/worker.py:148–175`). A dependent part can therefore start from changes that have never passed review. The START tests cover only a freshly reviewed head.

Disposition: cut

3. Blocking: Reusing the review after replay leaves a review commit that the required pull-request check rejects.
   Raise: Plan gap.
   Item 4 requires replay plus clean-review reuse (`plans/FORGE-STACK-1.md:117–122`). Replay removes the original commits; the existing reuse path updates fingerprints but retains `review.commit` (`src/forge/close.py:180–189`). `src/forge/prcheck.py:212–215` rejects a review commit outside the new ancestry. The planned test uses stubbed GitHub checks and never proves that the real `forge hook pr-check` passes after replay.

Disposition: cut

4. Blocking: A new stacked part can inherit the older Forge release from a part started before upgrade.
   Raise: Functional.
   The upgrade promise preserves previously started parts (`plans/FORGE-STACK-1.md:45–49`), while the start rule branches directly from their remote heads (lines 76–77). That also inherits their older `forge.toml`; the carried files contain only the story documents and state (`src/forge/task.py:287–292`). Commands in that checkout run the older pinned release (`src/forge/repo.py:603–638`), which lacks stacked-task closing. The upgraded fixture starts its work after upgrading and does not exercise this normal mixed-version case.

Disposition: cut

5. Blocking: CLOSE's required prerequisite is missing from its After cell even though the prerequisite now has a name.
   Raise: Plan gap.
   `plans/FORGE-STACK-1.md:157–160` requires CLOSE to follow the other story's main-merge change, but its task row lists only START. The locally available `story/FORGE-MAINONCE-1:plans/FORGE-MAINONCE-1.md:162` names that task `ONCLASH`. Without the link, CLOSE can start before it; overlap checks do not block work that has not started.

Disposition: cut

No files changed; runtime tests were not run. These are plan findings, not runtime verification.

## Round 2

6. Blocking: The new start rule can admit another part before its blocker has replayed onto main.
   Raise: Plan gap.
   `plans/FORGE-STACK-1.md:76–80` allows B once its parent A has merged, without checking that B has replayed. When A and B change the same code and test files, B's old review fingerprint can still match: `src/forge/review.py:134–160` hashes changed filenames and head blobs, not the baseline or ancestry.
   Thus, after A merges but before `forge close B`, C can start on B's old head. B's subsequent replay rewrites C's base, contradicting the two-deep guarantee at lines 171–174. The planned refusal test covers only A still unmerged.

Disposition: cut

No files changed; runtime tests were not run. The replay-before-start guarantee remains unproven.
