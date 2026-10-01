---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-01T01:10:05+00:00
read_hash: 4cb7eb8f392866adefd2afec162b09624d90dedc
round: 3
passed: yes
doc_seen: 4cb7eb8f392866adefd2afec162b09624d90dedc
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: d720528a6c713ef0a1b9db98463900c33bf62c9a
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc, then run
`forge read <doc>` again for the next round, until a round finds nothing:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. P1: UPGRADE can land without the skill or brief update required in the same change.
   `AGENTS.md:53–55` requires that update whenever a command changes. The Tasks table gives all such files to independent GUIDE. Put the minimum command guidance in UPGRADE and leave GUIDE disjoint prose, or land the command and guidance together.
   Disposition: cut: UPGRADE now owns the skill's command row and Upgrade section (Tasks table); GUIDE keeps only the README and guide.

2. UPGRADE’s scope excludes an existing test that the new command necessarily breaks.
   `tests/test_split_commands_rest.py:45` invokes the exact help comparison against `HELP_GOLDEN` in `tests/test_split_commands.py:15`. Adding `upgrade` changes top-level help. Assign the necessary expectation update to UPGRADE; its current Tests cell authorizes only the new test file.
   Disposition: cut: UPGRADE's Tests cell adds `tests/test_split_commands.py`, whose help golden gains `upgrade` (item 1).

3. Item 3 contradicts the promised release sync: settings beyond the version can change.
   The approved-facing text promises every setting stays unchanged. Yet `sync._codex_config` changes `features.hooks = false` to `true` (`src/forge/sync.py:150–179`), and sync updates Git’s merge-driver setting. State the exception for Forge-managed settings explicitly and test preservation of user-owned settings.
   Disposition: cut: the promise now names settings in Forge's settings file; item 2 says sync's `.codex/config.toml` refresh is Forge's own files and tests a user setting there survives.

4. The interruption promise has an uncovered gap before the fix records its identity.
   `task._new_checkout` creates the branch and worktree before writing state (`src/forge/task.py:115–117`). An interruption between those operations leaves a folder without the recorded why that rerun requires. Pin safe recovery or an explicit exception, and prove that boundary in `tests/test_upgrade_command.py`.
   Disposition: cut: item 1's Rerun takes up a folder with no state and no commit of its own, and its test is in UPGRADE's list.

5. Retrying the unnamed-release command can start another upgrade instead of continuing.
   A first `forge upgrade` can fail installing one release; if another release appears before retry, resolving “newest” again selects a different fix. Recovery is specified only for the same named release. Define whether unnamed retries resume the pending target or require the user to name it, and test newest changing between attempts.
   Disposition: cut: item 1 refuses while an upgrade fix for another release is open, naming it; a test changes newest between two runs.

6. Rerun does not define how it protects other work in the upgrade checkout.
   The dirty-file refusal checks the main checkout, while resumption trusts an existing fix’s why. Uncommitted edits to its generated skill or host settings can then be overwritten or included when sync’s files are committed. Pin which existing changes are resumable and refuse other work without modifying it; add that refusal case to UPGRADE’s tests.
   Disposition: keep per `Decided: leftover upgrade folder: reuse only when clean, else refuse naming it (owner, 2026-10-01)` in Notes; item 1's Rerun and Tests now say so.

7. Unproven: item 1: release sync failure and nonzero close propagation.
   The proposed cases cover install failure and successful close, but do not explicitly prove that sync failure prevents commit/close, or that close’s output and exit code survive the shared release runner. Add those cases to `tests/test_upgrade_command.py`, including retry after partial sync.
   Disposition: cut: item 1's Failure and Tests cover a failed sync (no commit, no close, rerun to Ready) and a refusing close's output and exit code.

8. Unproven: item 2: committing sync deletions and excluding Git hook shims.
   Marker and host-hook assertions do not prove deletion staging or the separate Git-shim filter. Exercise a release that deletes `CLAUDE.md` and a checkout with `core.hooksPath = ".husky/_"`; assert the deletion is committed and new shims are excluded. Existing synced-check tests exercise close, not this command’s commit step.
   Disposition: cut: item 1's step 6 and Tests cover a sync deletion in the commit and `core.hooksPath = ".husky/_"` shims left out.

9. Unproven: item 3: both promised settings refusal paths.
   The CRLF test proves a successful edit. It does not prove that an unsupported version-line edit leaves bytes unchanged, or that release settings validation refuses without rewriting models or proceeding to commit/close. Assign both negative cases to `tests/test_upgrade_command.py`.
   Disposition: cut: item 3's Tests add the uneditable version line (refused before anything is created, bytes unchanged) and the release's settings refusal (no commit, no close, models untouched).

## Round 2

10. Disputed keep 6: the new state-less recovery can adopt work whose upgrade ownership is unproven.
    At `plans/FORGE-UPGRADECMD-1.md:94–96`, no state and no new commits do not exclude uncommitted files in an unrelated same-name worktree. Sync can overwrite those bytes before close’s review sees them. Require a pristine checkout for this recovery path, and add a dirty-orphan refusal test to `tests/test_upgrade_command.py`.
    Disposition: keep per `Decided: leftover upgrade folder: reuse only when clean, else refuse naming it (owner, 2026-10-01)` in Notes; item 1's Rerun refuses an unclean leftover folder and UPGRADE's Tests cover it.

11. Split: UPGRADE → VERSION and UPGRADE; it now covers four Done-when items.
    The revised Tasks row exceeds the three-item limit. VERSION can own the byte-preserving version edit and shared release runner in `repo.py` (items 1 and 3), pinning their callable contracts first. UPGRADE then owns the command, both-host refresh and required skill update (items 1, 2 and 4), after VERSION.
    Disposition: cut: VERSION (`repo.set_version`, `repo.run_release`; covers 1, 3) now comes before UPGRADE (covers 1, 2, 4) in the Tasks table.

## Round 3

No findings.
