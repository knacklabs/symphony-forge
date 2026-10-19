# Drop a fix nobody wants any more, and bring it back later

2 parts · Risks: none one-way · New moving parts: none

## What changes for you

- When you no longer want a fix, you tell the agent, and it drops the fix with one command and
  your reason. The fix leaves the board, `forge next` and the merge queue. Its pull request
  closes with your reason in it. Its worktree goes, unless it holds local files that are not in
  git. Its branch stays on GitHub.
- When you want a dropped fix back, the agent brings it back with the same command. The pull
  request opens again, the worktree comes back, and the fix continues from where it stopped.
- Teammates see the same result after their next fetch, because the fact lives in git and on
  GitHub, not on one laptop.

## Why

Issue 865: a fix that nobody wants stays on the board and in `forge next` for ever. The only way
out today is to merge it or to delete its branch by hand, and a hand deletion loses the work and
confuses the board. On 17 October 2026 the owner chose: drop hides the fix and keeps its branch, so
a drop can be undone.

## Done when

1. **A fix can be dropped with a reason, and it then leaves the board, the next steps and the merge queue, and its pull request closes with that reason.**
2. **A dropped fix can be brought back, and it continues from its last commit with its pull request open again.**
3. **A teammate's checkout shows the same dropped or restored state after it fetches.**

## New and existing repos

- **New repos** (init or adoption): the drop command and the coordinator guide text. Tested on a
  repo made by `forge init`.
- **Existing repos** (on upgrade to this release): the same command from their next fix. Fixes
  that were left on the board before this release stay as they are until someone drops them.
  Tested on the adopted earlier-release fixture moved to this release.

## Risks

Risks: none one-way. The branch and its commits stay on GitHub, so every drop can be undone.

## For the builders

### Done-when details

1. `forge fix drop <fix> --because "<reason>"`. It is a subcommand of `fix`, so the top-level
   command count does not change. Only the human decides a drop; the coordinator guide says the
   agent asks first and runs it on a clear yes. The command:
   - pushes the fix branch, so no local commit is lost, and commits a dropped record (reason, who,
     when) on the fix branch itself, not on the default branch;
   - closes the fix's pull request with a comment that holds the reason; a fix with no pull
     request yet gets none;
   - removes the worktree and the local branch and keeps the remote branch, but only when the
     worktree holds no ignored files other than rebuildable folders (`.venv`, `node_modules`,
     `.pytest_cache`, `__pycache__`, `dist`, `build`); otherwise it keeps the worktree, says which
     ignored paths kept it, and still drops the fix;
   - refuses with a plain reason and the next step when the fix has uncommitted changes, when a
     Forge run on this machine holds it, when it is already merged, or when another open fix is
     stacked on it (it names those fixes: drop or finish them first).
   The board, `forge next`, `forge land`'s queue and `forge board --json` skip a dropped fix. The
   fix's name stays reserved, as abandoned names are today.
   Tests: drop a fix with a pull request and one without; each leaves the board and `forge next`;
   the pull request is closed with the reason; the remote branch keeps every commit; a drop with
   uncommitted changes is refused and changes nothing; a fix with an ignored local data folder
   keeps its worktree; a fix that another open fix is stacked on is refused and names it.
2. `forge fix drop <fix> --undo`. It reuses the kept worktree when the drop kept one (after a
   fast-forward to the remote branch), or recreates it from the remote branch otherwise, commits a
   restored record, and reopens the pull request when one was closed by the drop. Its next step
   then follows the usual rules for its new commit: a fix that was ready before the drop needs
   `forge close` again, because readiness belongs to a commit. Tests: drop then undo; the fix is
   back on the board with its old commits and an open pull request; `forge work` continues it; a
   fix that was ready before the drop shows `forge close` as its next step after the undo; an undo
   of a drop that kept its worktree reuses it and its ignored data is still there.
3. The dropped state is read from the fix branch's record and the pull request's state on GitHub,
   never from a local-only file. Tests: a second clone fetches and shows the fix dropped, then
   restored.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| DROP | Drop and bring back | the `fix drop` subcommand with `--undo`, the dropped record on the fix branch, pull request close and reopen, worktree cleanup and restore, `forge next` and land skip a dropped fix, guide text | 1, 2, 3 | src/forge/task.py, src/forge/cli.py, src/forge/nextstep.py, src/forge/land.py, src/forge/templates/skill.md, src/forge/templates/brief.md, .claude/skills/forge/SKILL.md, .codex/skills/forge/SKILL.md, docs/commands.md | tests/test_fix_drop.py | | | |
| BOARD | The board skips dropped fixes | the board and `forge board --json` leave out a dropped fix and show it again after `--undo` | 1, 3 | src/forge/board.py, src/forge/board_facts.py | tests/test_board_skips_dropped_fixes.py | DROP | | |

New moving parts: none

## Notes

- BOARD waits for FORGE-BOARD-4/SERVER to merge, because both change src/forge/board.py.
