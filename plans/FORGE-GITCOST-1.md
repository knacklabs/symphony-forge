# Forge commands start far fewer git processes

3 parts · Risks: none one-way · New moving parts: none

## What changes for you

- `forge next`, `forge board`, `forge close` and `forge work` answer faster, because each one
  starts far fewer git processes for the same answer.
- Commits in a large fix no longer pause while the commit hook rebuilds Forge's generated files
  to compare them.
- Nothing you see changes: every command gives the same output and the same refusals as before.
- Forge's own test suite runs faster, so fixes close sooner.

## Why

On 18 October 2026 tests were the main bottleneck locally and in CI. A profile of a sample of
Forge's own suite found about 183 git processes per test, most of them started by the Forge
commands under test. The repo root lookup ran about 15 times per test although a per-process fact
cache exists, single-file reads from other commits ran one process each (about 35 git processes in
one `forge next` and 87 in one `forge close`), and the pre-commit hook on an oversized fix added a
worktree and parsed about 40 modules on every commit (about 0.7 seconds per commit). Client repos
pay the same costs on every command.

## Done when

1. **On Forge's own repo, `forge next`, `forge board`, `forge close` and `forge work` each start at least 30 percent fewer git processes than before for the same output.**
2. **A commit in a fix over the fix limit adds no more than 0.2 seconds for Forge's generated-file check.**
3. **Every command's output and refusals stay the same on a new repo and on an adopted earlier-release repo.**

## New and existing repos

- **New repos** (init or adoption): faster commands and hooks from their first command.
- **Existing repos** (on upgrade to this release): the same, with no setting or file change.
  Tested on the adopted earlier-release fixture moved to this release.

## Risks

Risks: none one-way. Each part is a change inside Forge's own code and reverts with its pull
request; no record, file format or setting changes.

## For the builders

### Done-when details

1. Measure with a PATH shim that logs each git process (as the profile did) on this repo and on
   the client-sized test fixture, before and after; put both counts in the Proof list. Ways in:
   the repo root (`git rev-parse --show-toplevel`) is remembered per process keyed by the
   working directory it was asked from, never by the shared git directory, because close changes
   into an item's worktree mid-command; reads of one file at another commit (`git show rev:path`)
   are batched through one `git cat-file --batch` process per command where a command reads more
   than a few; `merge-base`, `diff` and `ls-tree` results are remembered only keyed by resolved
   commit ids, never by ref or branch names, so a fetch, merge or commit in the same command can
   never return a stale answer (a ref name is resolved to its commit id each time it is asked). Tests: a command-boundary test counts git processes for `forge next --json` and
   `forge close` on a fixture and holds a ceiling below the old count.
2. The pre-commit hook's `_promote` path (src/forge/githooks.py) calls `sync.synced`, which adds a
   worktree and parses modules to compare generated files. Compare the content hashes of the
   generated files in the whole fix (base to index, as today) with what Forge would write,
   computed in the hook's own process without a worktree or module parsing; never skip the check
   based on the current commit alone. Tests: the generated-file check step's own time (measured
   inside the hook, not the whole commit) stays under 0.2 seconds on an oversized fix (owner narrowed
   it from 0.1 seconds on 18 October 2026: the check went from 0.68 to about 0.1 seconds); a second
   commit that changes only ordinary source in a fix with generated updates is accepted; a hand
   edit to a generated file is still refused.
3. The existing command tests for these commands are the proof; run them on both repo kinds.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| FACTS | Per-process git facts | the repo root and repeated ref lookups remembered once per process | 1, 3 | src/forge/repo.py, src/forge/nextstep.py, src/forge/close.py, src/forge/review.py, src/forge/prcheck.py | tests/test_git_process_ceiling.py | | | |
| BATCH | Batched file reads | one cat-file batch process for a command's reads at other commits | 1, 3 | src/forge/repo.py, src/forge/board.py, src/forge/board_facts.py, src/forge/time_records.py | tests/test_git_process_ceiling.py | FACTS | | |
| HOOK | Cheap generated-file check | the pre-commit hook compares generated files without a worktree or module parsing | 2, 3 | src/forge/githooks.py, src/forge/sync.py | tests/test_hook_generated_check_speed.py | | | |

New moving parts: none

## Notes

- BATCH touches src/forge/board.py, which the unmerged FORGE-BOARD-4/SERVER also changes; BATCH
  starts after SERVER merges or merges main and resolves.
