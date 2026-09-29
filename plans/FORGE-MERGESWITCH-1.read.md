---
reader: codex (gpt-6-sol)
read_at: 2026-09-29T07:57:01+00:00
read_hash: 75fc220163975ea335841650f80fb9d009684366
amended_hash:
round: 1
passed: no
doc_seen: 75fc220163975ea335841650f80fb9d009684366
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
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

