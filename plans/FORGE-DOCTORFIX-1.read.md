---
reader: codex (gpt-6.1-sol)
read_at: 2026-09-30T20:40:51+00:00
read_hash: f3662a1403f50cfb4ba193c5c34e1eeddbc33d65
round: 2
passed: no
doc_seen: f3662a1403f50cfb4ba193c5c34e1eeddbc33d65
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 096dd157aa3dde18a53b00ca66bed63ede27c77c
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc, then run
`forge read <doc>` again for the next round, until a round finds nothing:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. Item 3 can delete ignored user files, contradicting its deletion safeguard.
   `git status --porcelain` omits ignored files; this repo ignores `.env` and `.env.*`. A qualifying worktree containing those files would still be forcibly removed. Pin what ignored content is disposable, protect everything else, and prove that protection in REPAIRS.
   Disposition: cut

2. Unproven: item 3: a failed open-PR lookup must prevent deletion.
   [`nextstep._prs`](/src/forge/nextstep.py:459) returns `[]` for both failure and a successful empty result. If the merged lookup succeeds but the open lookup fails, doctor can mistake “unknown” for “no open PR.” Require successful queries before deleting; test failed and malformed responses in REPAIRS.
   Disposition: cut

3. Item 5’s history rule cannot guarantee that hand edits survive.
   Changing a generated file by hand alongside `forge.toml` makes it eligible for overwrite. Conversely, item 4’s own repair commit does not change `forge.toml`, so subsequent drift in that file becomes “changed by hand.” Pin an ownership rule that handles both cases and test it in FILES.
   Disposition: cut

4. Unproven: item 5: hand edits inside a reused doctor fix are protected.
   The rule checks uncommitted changes “in the checkout doctor runs in,” but default-branch repairs write into another worktree. Require the guard to inspect the destination too; test staged, unstaged and untracked destination edits in FILES.
   Disposition: cut

5. Item 4 does not pin reuse of a fix carrying an older Forge pin.
   A pending doctor fix can survive an upgrade on the default branch. Reusing it by `why` alone can write newer templates into a checkout that still pins the older release. Specify whether doctor refreshes that fix or leaves a plain step, and test this state.
   Disposition: cut

6. Item 4’s pending-fix row can claim success while files remain unrepaired.
   The row unconditionally says the files are “up to date,” although item 5 can hold files back. Make that message conditional on the destination actually matching `sync.files`; test a fix containing both repairable and held-back drift.
   Disposition: cut

7. Item 4 does not account for the normal fix limits.
   [`githooks._promote`](/src/forge/githooks.py:127) refuses more than five code files or any configured interface path. The promised expanding sync list can cross either boundary. Pin the permitted behavior and plain next step without bypassing these gates; add FILES coverage.
   Disposition: cut

8. Unproven: item 2: SDK installation failure still allows independent repairs.
   [`codex.install`](/src/forge/codex.py:115) currently raises a refusal immediately, stopping hooks, folder cleanup and file repairs. Specify failure isolation and output. If SDK failure becomes a row, REPAIRS also needs ownership of the existing refusal assertion in `tests/test_contracts.py`.
   Disposition: cut

9. REPAIRS omits an existing test that must change with the option’s help.
   [`tests/test_split_commands.py`](/tests/test_split_commands.py:167) fixes the old SDK-only help text, exercised by `tests/test_split_commands_rest.py`. Add the expectation owner to REPAIRS’ Tests cell.
   Disposition: cut

10. Unproven: item 4: sync’s empty-string deletion contract is preserved.
    `sync.files` can return `CLAUDE.md: ""`, meaning delete the file; [`sync.write`](/src/forge/sync.py:264) explicitly unlinks it. The story only specifies writing differing files. Pin deletion semantics and test both in-place deletion and committed deletion in the doctor fix.
   Disposition: cut

11. Unproven: item 4: write and commit failures leave an accurate, recoverable result.
    No FILES test covers an outside-repo symlink, detached HEAD, filesystem refusal or rejected commit after files were written. Specify the remaining rows and retry behavior, especially because uncommitted doctor output would otherwise meet item 5’s hold-back rule.
   Disposition: cut

12. Unproven: item 3: branch deletion fails after worktree removal succeeds.
    The documented failure step addresses a folder that could no longer exist. Pin the diagnostic and recovery step for this half-finished cleanup, and prove that later repairs continue in REPAIRS.
   Disposition: cut

13. Unproven: item 1: development-build exemption and child-run result propagation.
    The listed tests omit the explicitly promised same-three-number development build and preservation of the child’s output and nonzero exit code. Add both cases to `tests/test_doctor_fix.py`.
   Disposition: cut

## Round 2

14. Finding 3 remains open: item 5 still permits overwriting hand edits.
    The approval-facing promise says “never,” but lines 234–236 explicitly allow replacing a hand edit committed with a pin change. Keeping its old text in git history does not prevent overwriting it. Align the promise and implementation rule; no `Decided:` line settles this exception.
    Disposition: cut

15. Item 3 treats every ignored folder as disposable without establishing that its contents are regenerable.
    An ignored `data/` or `secrets/` directory qualifies just like `.venv/`; porcelain can collapse its contents into one directory entry. Limit deletion to known regenerable folders and prove that other ignored directories survive in REPAIRS.
    Disposition: cut

16. Unproven: item 3: a capped PR list cannot establish that no open PR exists.
    `--state all --limit 1000` can include the matching closed PR while omitting an older open PR from that branch. Require complete evidence or skip cleanup when the result reaches the cap; add the boundary case to `tests/test_doctor_fix.py`.
    Disposition: cut

17. Item 5’s “already matches sync” exception can discard a staged hand edit.
    The working file can match sync while the index holds different hand-edited text. Committing that path through [`repo.commit_state`](/src/forge/repo.py:429) stages the working copy over that edit. Require both working-tree and index checks, and test this state in FILES.
    Disposition: cut

18. Unproven: item 4: retrying a rejected commit also commits pending deletions.
    After doctor removes `CLAUDE.md`, [`githooks.ships`](/src/forge/githooks.py:66) omits it from subsequent `sync.files` results. Pin how the retry finds that deletion and test removal followed by commit refusal and a successful retry.
    Disposition: cut

19. Unproven: item 4: filesystem write failure remains uncovered from finding 11.
    The amended tests cover a symlink refusal and a rejected commit, but not the system refusing a write after another file was repaired. Add FILES coverage proving the failure row, preserved partial result and successful retry.
    Disposition: cut

20. Unproven: item 4: detached HEAD remains uncovered from finding 11.
    The refusal is now specified, but no listed FILES case proves that doctor leaves files and the index untouched and retains the drift rows on detached HEAD.
    Disposition: cut
