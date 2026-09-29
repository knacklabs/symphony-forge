---
reader: codex (gpt-6-sol)
read_at: 2026-09-29T08:06:54+00:00
read_hash: 13d26c80804c7c78eb49be1c983ae127177fa08c
amended_hash:
round: 3
passed: no
doc_seen: 13d26c80804c7c78eb49be1c983ae127177fa08c
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 9992a93fa5885865a86cac1b823966831783cf9f
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

