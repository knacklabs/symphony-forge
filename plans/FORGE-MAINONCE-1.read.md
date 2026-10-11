---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-11T08:08:12.258204+00:00
read_hash: 402721c3de22fdf105fd71f283c1e22dfc60dfd7
round: 1
passed: no
doc_seen: 402721c3de22fdf105fd71f283c1e22dfc60dfd7
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a129f9-1302-7a41-b794-06da2773a6d8
session:
blocked_rounds: 1
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

1. Blocking: Item 4 still permits two changes to clash over spotted records.
   Raise: Not done. The plan writes status changes into the file containing the entry (`plans/FORGE-MAINONCE-1.md:122`). Two fixes naming the same path both close its open entries with different `closed_by` values (`src/forge/spotted.py:162`), changing identical lines in another item's file or the legacy list. Their product edits can be disjoint. The proposed test covers concurrent additions, but not concurrent closures.

Disposition: cut

2. Blocking: Item 2's review-reuse promise contradicts the preserved fingerprint implementation and required unchanged test.
   Raise: Not done. When main changes different lines in a reviewed file, merging it changes the base and head blob hashes used by `review.fingerprint` (`src/forge/review.py:145`), so close runs another review despite no new worker edits. `tests/test_merge_refreshes_behind_base.py:167` explicitly requires that extra review, while the plan requires this test to remain unchanged and promises reuse (`plans/FORGE-MAINONCE-1.md:101`). Neither task owns the required change to that fingerprint calculation.

Disposition: cut

3. Blocking: Skipping a clean default merge breaks re-closing the owner's merge-setting fix.
   Raise: Functional. Contrary to `plans/FORGE-MAINONCE-1.md:91`, close's mechanical merge-setting check compares HEAD directly with `origin/<default>` (`src/forge/close.py:154`). If checks stop the owner's fix, another pull request adds an unrelated file, and the owner follows the printed `forge close` retry, the proposed merge gate skips merging. The mechanical check then treats that file's absence as an extra change and refuses the valid fix. The generic-fix test does not cover this documented setting flow.

Disposition: cut

4. Blocking: The nested task-record layout lacks a rule preventing writes through linked task directories.
   Raise: Security. Tasks write to `plans/spotted/KEY/TASK.json`, but the added link refusal names only `plans/spotted` (`plans/FORGE-MAINONCE-1.md:120`, `:129`). A linked `plans/spotted/KEY` can direct the writer outside the checkout while both `plans/` and `plans/spotted/` are ordinary directories. The existing safeguard checks only `plans/` and the legacy file (`src/forge/spotted.py:133`); the plan supplies no rule or test for the new intermediate directory.

Disposition: cut

5. Blocking: The promised rollback restores a reader that cannot discover records written after upgrade.
   Raise: Plan gap. The Risks section promises that per-change records remain readable after reverting (`plans/FORGE-MAINONCE-1.md:56`). Reverting SPOTTED restores `spotted.read`, which reads only `plans/spotted.json` (`src/forge/spotted.py:79`). The new files survive, but disappear from Forge's problem inventory and hotspots. No rollback compatibility rule or proof covers that promise.

Disposition: cut

6. Blocking: The test contract prohibits the reviewer stubs its prescribed scenarios require.
   Raise: Plan gap. The plan permits faking only GitHub and elapsed time (`plans/FORGE-MAINONCE-1.md:72`), yet requires deterministic blocked and clean reviews and assertions that no additional review runs. Its recommended `client` fixture depends on `env`, which stubs Autoreview and Codex (`tests/test_close.py:219`). Using that fixture violates the stated restriction; omitting those stubs leaves the required review scenarios nondeterministic.

Disposition: cut

Read only; no runtime tests were run.
