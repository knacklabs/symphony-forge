---
reader: codex (gpt-6-sol)
read_at: 2026-09-29T03:44:18+00:00
read_hash: 6d991c50eabb038e34edfe4cc9554f3bc74bbe11
amended_hash:
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. Unproven: Done-when items 1–5 have no confirmed spec to trace to.
   No linked confirmed spec was found, and the [product brief](/docs/product/BRIEF.md) does not state these upgrade behaviors or a success measure.
   Disposition: keep this story comes from a reported bug, not a planned feature; the Why states the evidence, and Notes say so.

2. Trap: item 3’s “open fix” exception needs a precise eligibility rule.
   [check_pin](/src/forge/repo.py:290) currently checks only the caller’s pin. PENDING must pin which fix states, branches, and local worktrees count as pending, and what happens if more than one qualifies; otherwise an old worktree could keep the default branch’s version gate open.
   Disposition: cut: details item 3 pins the rule: a local worktree on an unmerged fix/ branch pinning exactly the installed version; the first when several.

3. Trap: items 3 and 4 must route through the CLI version gate.
   [cli._run](/src/forge/cli.py:73) calls `check_pin` before either command handler. The approval warning and `forge close` folder message cannot work from a mismatched checkout through handler changes alone. Pin the command-specific routing and test the public commands.
   Disposition: cut: details item 3 puts the exception in repo.check_pin called from cli._run, skips it for forge hook, and tests public commands.

4. The PENDING → SYNCED After link exists only because both edit `doctor.py`.
   The [story](/plans/FORGE-UPGRADE-1.md) gives that as its sole reason. Assign the shared `doctor()` comparison and wording seam to one task, or put the shared edit in a small last wiring task; retain After only for a code dependency.
   Disposition: cut: only DOCTOR changes doctor.py; SYNCED reuses its comparison; no After link.

5. Item 5 has no workable untracked-file path yet.
   [migrate](/src/forge/migrate.py:174) refuses a checkout with untracked files, while `_plan` reads tracked Git trees and `_apply` runs in a new worktree. Pin where the leftovers are listed, confirmed, and removed, including the dry run and link checks.
   Disposition: cut: item 5 moves to forge doctor and doctor --fix, which already exist, instead of migrate.

6. Risks: none contradicts item 5.
   Deleting untracked files is a one-way step with no Git history to restore them. Name that data-loss risk and the confirmation boundary under Risks.
   Disposition: cut: Risks names the deletion and its confirmation boundary.

## Round 2

7. **Disputed cut 5 — item 5 is still blocked before cleanup.** `forge migrate`, including `--dry-run`, refuses visible untracked files before it creates `forge.toml`; `forge doctor` requires that file before it can list or remove leftovers. The move cannot reach the proposed cleanup path. Pin a pre-migration route and have DOCTOR’s `tests/test_upgrade_doctor.py` prove cleanup followed by a successful migrate dry run. [Plan](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/plans/FORGE-UPGRADE-1.md:63), [migrate.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/src/forge/migrate.py:174), [doctor.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/src/forge/doctor.py:74).
   Disposition: keep these files are ignored by git in repos older Forge set up, so migrate runs with them present and doctor finds them afterwards; details item 5 says so and its test migrates such a repo first.

8. **Disputed cut 2 — “unmerged” still lacks a reliable testable meaning.** Forge squash-merges fixes and can leave a merged fix’s dirty worktree and branch in place. Git ancestry would still call that branch unmerged, leaving the version exception open. Pin how PENDING establishes that the fix is still pending, including when that check fails, and test a retained worktree after merge in `tests/test_upgrade_pending.py`. [Plan](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/plans/FORGE-UPGRADE-1.md:53), [merge.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/src/forge/merge.py:60), [merge cleanup](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/src/forge/merge.py:104).
   Disposition: cut: details item 3 needs no 'unmerged': the exception applies only while the default branch pins an older version, so a worktree left after the merge changes nothing; tested.

9. **Trap — item 4’s named test does not reach its refusal.** With an unmerged upgrade fix worktree pinning the installed version, item 3 admits `forge close <fix>` from the default checkout; `close` then finds the fix worktree itself. The promised wrong-folder message never appears in that state. Specify a state where the version check must refuse, or change the expected result to successful routing, and test that public command in PENDING. [Plan](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/plans/FORGE-UPGRADE-1.md:53), [close.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/src/forge/close.py:45).
   Disposition: cut: details item 4's test runs forge close from another fix's folder that pins an older version, where the check does refuse.

10. **Trap — item 5’s deletion test misses files inside the named directories.** A user-created untracked file under `.factory/briefs/` would be removed by deleting that directory, despite the promise to remove no other untracked file. Listing only the directory name does not expose that loss. Pin how contents and links are inspected before confirmation; DOCTOR’s `tests/test_upgrade_doctor.py` should prove a nested user file survives or causes refusal on the Linux, macOS and Windows test matrix. [Plan](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/plans/FORGE-UPGRADE-1.md:63).
   Disposition: cut: details item 5 shows every file inside the paths and removes only what it showed; the test lists a nested file.

## Round 3

11. **Trap — item 1’s compatibility fields share the `tree` key.** The v1.1.0 check reads `review.tree` as a whole-tree fingerprint, while current close and PR check read that same key as the newer changed-file fingerprint. Keeping both requires a defined key and reader change in `close.py`, which SPEC cannot edit and SYNCED edits independently. Assign that seam and test that one recorded review passes both versions’ checks without close rerunning it. [Plan](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/plans/FORGE-UPGRADE-1.md:43), [close.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/src/forge/close.py:62), [review.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/src/forge/review.py:110).
   Disposition: cut: details item 1 keeps `tree` as the whole-tree fingerprint and puts the new one under its own key; SPEC owns close.py for that; SYNCED waits for SPEC; the test runs both checks on one review.

12. **Disputed keep 7 — ignored leftovers remain in the original checkout.** Ignoring them lets migration start, but migration creates a separate worktree and directs `forge doctor` to run there. That worktree has none of the original checkout’s ignored files. Pin cleanup after the original checkout receives the merged `forge.toml`, and make DOCTOR’s migration test use that folder. [Plan](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/plans/FORGE-UPGRADE-1.md:69), [migrate.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/src/forge/migrate.py:218), [migration instructions](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/docs/migrate-skill.md:43).
   Disposition: cut: details item 5 runs cleanup in the original checkout after the migration merges and is pulled; the test does exactly that.

13. **Disputed cut 8 — a human merge does not update the local default checkout.** The revised exception reads that checkout’s older pin. After a human merges remotely, a retained upgrade worktree can therefore keep the exception open until the local branch is updated; the stated “once the upgrade merges” condition does not hold. PENDING’s post-merge test must leave the local default branch stale and specify the intended result. [Plan](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/plans/FORGE-UPGRADE-1.md:57), [check_pin](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/src/forge/repo.py:290).
   Disposition: cut: details item 3 reads the default branch as last fetched from its remote; the test fetches the merge with the local branch stale.

14. **Trap — item 5 does not bind deletion to the confirmed list.** A file added under `.factory/briefs/` between `forge doctor` and `forge doctor --fix` was never shown to the human, but a fresh directory walk could delete it. Pin how the confirmed file list is carried to `--fix`, and test a newly added file survives or stops cleanup in DOCTOR. [Plan](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/plans/FORGE-UPGRADE-1.md:69).
   Disposition: cut: details item 5 records the listed files; --fix removes exactly those and refuses on any unlisted file; tested.

15. **Unproven — item 7 needs installed-artifact tests.** Hatchling currently takes a static version from `__init__.py`, and the test fixture runs Forge directly from source. That cannot prove a wheel installed from an unreleased commit reports its commit, or that a tag-built wheel reports the release. Pin the build provenance and test both installed artifacts in PENDING on the CI platforms. [Plan](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/plans/FORGE-UPGRADE-1.md:80), [pyproject.toml](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/pyproject.toml:18), [test fixture](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/tests/conftest.py:23).
   Disposition: cut: details item 7 reads direct_url.json from the package metadata; tests install fake distribution records for each case.

16. **Trap — item 7 omits clients before they have a pin.** `check_pin` currently permits a repo without `forge.toml`; `forge init` and `forge migrate` then write `v{__version__}`. A development build could create a client repo pinned to its commit-marked version and refuse its next command. PENDING needs public `init` and `migrate` refusal tests that prove no client files or branch are created. [Plan](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/plans/FORGE-UPGRADE-1.md:80), [repo.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/src/forge/repo.py:290), [init.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/src/forge/init.py:105), [migrate.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-UPGRADE-1/src/forge/migrate.py:192).
   Disposition: cut: details item 7 has init and migrate refuse a development build before creating anything; tested.

