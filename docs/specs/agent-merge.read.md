---
reader: codex (gpt-6-sol)
read_at: 2026-09-27T14:54:58+00:00
read_hash: 3bb8643454adc2cc03f4b8f04cd986ad5cec3fc7
amended_hash:
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. `forge merge` has no durable proof that the last close ended Ready.
   [close.py](/src/forge/close.py:81) prints Ready without saving that status or the pushed commit. [nextstep.py](/src/forge/nextstep.py:23) has a `ready` state, but close never writes it. Pin where the Ready result and commit live before specifying either command’s gate. Also resolve close’s migration exception, which can print Ready without waiting for the configured `forge-pr-check`.
   Disposition: keep close now records ready and its pushed commit; merge waits on every configured check, no migration exception

2. The setting’s authority is unspecified.
   Close reads `forge.toml` from the item’s worktree. If merge does likewise, an item can carry `merge = "agent"` on its own unmerged branch while the repo’s landed setting remains `"human"`. Specify which trusted revision authorizes merging and how this repo’s first setting change becomes effective.
   Disposition: keep only the default branch's forge.toml as fetched from origin grants the setting

3. The merge target and commit need protection at the merge operation.
   Checking the PR head and then invoking merge leaves a window for the head to change. Require the merge operation to match the checked commit, and verify that the open PR targets the intended default branch. The installed `gh pr merge` supports `--match-head-commit`.
   Disposition: keep the merge is tied to the checked head commit and checks the pull request targets the default branch

4. Cut or defer: automatic branch and worktree deletion.
   The Why and success measure need the PR merged promptly; they do not need immediate cleanup. If cleanup stays, list it under Risks and require preservation of local changes. After merging, `forge next` also needs a refreshed default-branch view: it currently determines that a task merged from the locally known landed state.
   Disposition: keep the owner chose tidy-up; a worktree with uncommitted changes stays, and merge fetches the default branch

5. The hook does not make `forge merge` the agent’s only possible merge path.
   [deny.py](/src/forge/deny.py:103) refuses a shell command containing `gh pr merge`; it does not enforce the broader claim that the agent “never merges any other way.” State that as an agent instruction, or specify an enforceable boundary before relying on it to guarantee the close rule.
   Disposition: keep reworded: AGENTS.md and the skill say the agent merges only through forge merge; the hook still refuses a raw merge
