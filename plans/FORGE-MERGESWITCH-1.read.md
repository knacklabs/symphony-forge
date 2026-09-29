---
reader: codex (gpt-6-sol)
read_at: 2026-09-29T09:20:40+00:00
read_hash: 9f735ceaa052a09e99deb9165314775b45e2fceb
amended_hash:
round: 9
passed: yes
doc_seen: 9f735ceaa052a09e99deb9165314775b45e2fceb
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 0bffa5ae9e0a332504217851e24c16d69a92854b
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

## Round 1

1. `forge merge enable` cannot be registered within the stated Scope.
   The CLI currently treats `merge` as a standalone command. Adding `merge enable` creates a second `merge` parser and fails during parser construction. Scope must include `src/forge/cli.py`, with a test that both commands still work.
   Disposition: cut: SPEC's Scope adds src/forge/cli.py and item 2's tests check both merge forms.

2. Unproven: item 1: how the one command opens a mergeable pull request.
   `forge fix start` only creates a fix worktree; `forge close` opens the pull request after review and requires configured checks. Pin whether `enable` runs that close flow or opens a pull request directly, and test the resulting review and ready state.
   Disposition: cut: item 1 runs forge close on the fix, so the change is reviewed and its pull request opened; tested to Ready.

3. Unproven: item 1: interrupted runs and retries.
   A failed commit, push, or `gh pr create` can leave a fix branch or worktree behind. The story specifies neither the next command the owner sees nor a test that a second run can finish safely.
   Disposition: cut: item 1 continues its own fix when run again; tested after a failed push.

4. Unproven: item 1: what “already on” means for a client prototype.
   `repo.merge_setting()` can return `agent` while the default branch still says `merge = "human"`. Pin whether `enable` refuses in that state and test it.
   Disposition: cut: item 1 defines on as the default branch's forge.toml saying agent; a prototype doesn't count; tested.

5. Trap: Windows line endings and shells: item 1.
   The test plan does not prove that editing `forge.toml` preserves a CRLF file or places the root `merge` key correctly when the file ends in a `[models]` table. Add those cases to `tests/test_merge_enable.py`.
   Disposition: cut: item 1 keeps line endings and places the key before the first table; tested with CRLF ending in a table.

## Round 2

6. Unproven: item 1: retries at every stated interruption point.
   The amended test covers a failed push, but the command also promises to continue after an interrupted commit or pull request creation. Pin how it identifies its own fix without taking over an unrelated fix, and test those states.
   Disposition: cut: item 1 gives the fix a fixed name and tests a rerun after each interruption point.

7. Contradiction: item 2: a prototype can agent-merge the switch pull request.
   Before sign-off, `repo.merge_setting()` permits `forge merge` even when the default branch says `merge = "human"`. `forge close` will therefore point to agent merge for this fix. Pin a rule that keeps this pull request for the owner to merge, and test it in the prototype case.
   Disposition: cut: item 1 has forge merge never merge a change to the merge setting, tested in a prototype.

## Round 3

8. Unproven: item 1: the fixed name is already used by another fix.
   “Never touches any other fix” needs a collision test: the command must recognize that the existing branch or worktree is unrelated and leave it unchanged.
   Disposition: cut: item 1 refuses and names an unrelated fix that holds the name, tested.

9. Contradiction: item 1: a prototype still tells the owner to run `forge merge`.
   `forge close` currently prints `Next: forge merge <item>` before `enable` can print its owner-merge instruction. The new merge refusal would make that next step fail. Pin and test the complete output so it gives the owner one valid next step.
   Disposition: cut: item 1 has close name the owner's merge for this fix, never forge merge, tested on the whole prototype output.

## Round 4

10. Contradiction: item 1: the retry before the config change conflicts with the collision rule.
    At that point the command’s own fix has no `forge.toml` merge-switch change, so the stated rule would classify it as unrelated and refuse. Pin an identity that works before the edit, and test that state.
   Disposition: cut: item 1 identifies its fix by the recorded kind merge-switch, which exists before the edit; tested.

11. Unproven: item 1: `forge merge` rejects every merge-setting change.
    The promised guard applies to any fix that changes the setting, but the test covers only the switch’s pull request. Test a differently named fix that changes `merge` while agent merges are otherwise allowed.
   Disposition: cut: item 1 tests a differently named fix changing merge refused by forge merge in a prototype.

## Round 5

12. Unproven: item 1: `forge next` gives the owner the wrong command in a prototype.
    For a ready fix, `nextstep.py` still uses the prototype’s effective agent setting and says `Next: forge merge <item>`, which the new guard refuses. Include that output in Scope and test the next step after the switch pull request is ready.
   Disposition: cut: item 1 has forge next name the owner's merge for this fix too; nextstep.py joins Scope; tested.

13. Simpler: new `merge-switch` kind → the fix’s existing `why` and `done_when` fields.
    Those fields are recorded when the fix starts and can identify it before the config edit. A new kind also changes the prototype review level because `review.blocking_level()` treats only `kind = "fix"` as a prototype fix.
   Disposition: cut: item 1 identifies the fix by its recorded why and done_when instead of a new kind.

## Round 6

14. Unproven: item 1: a same-name fix with matching `why` and `done_when` but other changes.
    Those fields can match while the worktree contains unrelated edits. The command would treat it as its own and continue closing it. Test that a retry accepts only an empty change or the intended merge-setting change, and leaves other edits alone.
   Disposition: cut: item 1 continues only when the fix's changes are none or exactly the merge line; other edits leave it alone; tested.

## Round 7

15. Unproven: item 1: cleanup after the owner merges the switch pull request.
    Once that merge makes the default branch’s setting `agent`, `forge next` can tell the owner to run `forge merge <item>` to tidy the remaining worktree. The new guard refuses that command. Pin and test the post-merge next step and cleanup path.
   Disposition: cut: item 1's guard only stops merging; after the owner's merge, forge merge cleans up as usual; tested with forge next.

## Round 8

16. Unproven: item 1: `forge next` after the pull request opens but before `forge close` records Ready.
    In a prototype, the existing waiting-for-checks path says it is preparing an “automatic merge.” The test covers `forge next` only after Ready. Test this interrupted state and make its message point to the owner’s merge path.
   Disposition: cut: item 1 now has one rule for every Forge message about the fix at every stage, and the test runs forge next at each stage.

## Round 9

No findings.
