# Doctor fixes what it finds

2 parts · Risks: removes folders of finished work · New moving parts: none

## What changes for you

- `forge doctor --fix` repairs everything it safely can, in one run: it installs the Forge version
  the repo pins, puts back the git hooks, installs the Codex SDK where Codex is used, removes the
  folders of finished work, and brings Forge's files for Claude Code and Codex up to date.
- Each repair prints one line.
- Forge's files are never changed on the default branch: doctor makes that change in a fix, which
  merges like any other.
- Doctor never overwrites a change someone made by hand. What needs a person (signing in to GitHub,
  a setting only you choose, a file changed by hand) stays one plain step.
- Every problem doctor can repair tells you to run `forge doctor --fix`.

## Why

Today doctor only reports. Each problem comes with a command that the developer must type in the
right folder and the right order. For example, sync must run after the pinned Forge is installed,
or it writes the wrong version's files. Folders of merged work also pile up. Forge leaves a folder
when it has any uncommitted change, and running the tests can change the lockfile. When a person
merges a pull request, its folder is always left behind. The owner wants setup that just works for
teams on Claude Code, Codex or both.

## Done when

1. **Doctor installs the Forge version the repo pins and finishes its repairs with that version.**
2. **Doctor puts back missing git hooks and, only where Codex is used, the Codex SDK.**
3. **Doctor removes the folders of finished work that hold nothing but a lockfile change.**
4. **Doctor brings Forge's files for Claude Code and Codex up to date through a fix, never on the default branch.**
5. **Doctor never overwrites a change made by hand, and leaves what needs a person as one plain step.**

## Risks

- Doctor deletes the folders and local branches of finished work. It deletes one only when all of
  its commits are already in a merged or closed pull request on GitHub and nothing is uncommitted
  except the lockfile and the cache folders the tools make again, such as `.venv` or
  `node_modules`. Any other file or folder, even one git ignores such as `.env`, keeps it.

## For the builders

### Done-when details

1. When the installed Forge is not the pinned version and the pin is the newer release (comparing
   the three numbers, the way `repo._older` does), `forge doctor --fix` runs
   `sync.install_line(cfg["version"])`, which is the pin refusal's own
   `uv tool install git+https://github.com/knacklabs/symphony-forge@v<pinned>`. After that it
   prints `- Fixed: installed Forge v<pinned>, the version this repo pins.` It then runs
   `forge doctor --fix` again through the `forge` now on PATH, with `FORGE_PINNED_RUN=v<pinned>`
   set. It passes that run's output through and exits with its exit code. Every other repair
   happens in that second run.
   - The second run never installs again, because `FORGE_PINNED_RUN` already names the pin. If its
     Forge is still not the pinned one (another `forge` comes earlier on PATH), it keeps the
     version row, with the install line as the Fix.
   - An older pin is left alone, and so is a development build with the same three numbers. The
     row stays, with the install line as the Fix. Other repos may need the newer Forge, and the
     version check already runs a repo's older pin through uv for each changing command. This also
     covers an upgrade fix waiting to merge, while the default branch still pins the older
     version.
   - When uv is missing or the install fails, the row stays and shows uv's last line, with the
     install line as the Fix. On Windows, for example, uv can't replace a `forge.exe` that is
     running. Doctor still makes the other repairs, except item 4, which needs the pinned Forge's
     templates.
   - Without `--fix`, the row's Fix is `forge doctor --fix` whenever the repair above would apply.

   Tests use a fake `uv` and a fake `forge` on PATH, with no network. They cover:
   - a newer pin: it is installed, and the second run sees `FORGE_PINNED_RUN`;
   - a second run that still has the wrong version: the row stays and `uv` is not called again;
   - an older pin: no `uv` call;
   - `uv` failing: the row stays with the install line, and the git hooks are still put back;
   - no `uv` on PATH;
   - a development build with the pin's three numbers: no `uv` call, and the row stays;
   - the second run's output printed as it came and its nonzero exit code returned.
2. **Git hooks.** The repair runs only when the git hooks row appears. The condition is today's
   (`doctor.py` lines 122-125), so Forge's own repo, when it has no `core.hooksPath`, is left
   alone. `--fix` calls `sync.install_shims`. The hooks are never committed, so this repair also
   runs on the default branch. It prints
   `- Fixed: installed the git hooks that check each commit and push.`
   - A hook that isn't Forge's is kept as `<hook>.pre-forge`, as `forge sync` does.
   - `install_shims` can refuse: a link that leads outside `.git`, or both the hook and its
     `.pre-forge` present. The refusal becomes the row's reason, its Next becomes the row's Fix,
     and no traceback is shown.

   **Codex SDK.** Doctor installs it only in these cases, which are today's rule (`doctor.py`
   lines 82-83):
   - `workers = "codex"`;
   - run under Claude Code (`CLAUDECODE` set) with Codex on PATH, where the cold read runs on
     Codex.

   It is never installed in any other case, whatever else `--fix` does. The install prints
   today's lines. When it fails, its refusal (`codex.REFUSALS["install"]`) becomes a row with the
   Fix `forge doctor --fix`, and doctor goes on with the hooks, folders and files. `codex.tidy`
   stops leftover Codex processes as it does today.

   Tests cover:
   - missing hooks put back on the default branch, matching `sync.shims`;
   - a hook that isn't Forge's, kept as `.pre-forge`;
   - the both-present refusal shown as a row;
   - `workers = "claude"` without `CLAUDECODE`: `uv` is never called for the SDK;
   - `workers = "claude"` under `CLAUDECODE` with `codex` on PATH: the SDK is installed;
   - `workers = "codex"`: the SDK is installed;
   - the SDK install failing: its row shows, and the hooks are still put back.

   Existing tests that change: `tests/test_fix_in_a_repo_whose_git_hooks_folder_is_set.py` now
   expects `Fix: forge doctor --fix`; `tests/test_contracts.py`'s SDK install failure now expects
   the row and the problems refusal; `tests/test_split_commands.py` holds the new `--fix` help.
3. Doctor looks at every worktree in `story.worktrees` whose branch starts with `story/`, `task/`,
   `fix/` or `forge/`. It skips the main checkout and the folder doctor runs in. For each branch
   doctor asks GitHub
   `gh pr list --head <branch> --state all --limit 100 --json headRefOid,state`. When `gh` is
   missing, or that call fails, doesn't return a list, or returns 100 entries, the folder is kept
   and not listed. (`nextstep._prs` isn't used here: it returns an empty list for a failure too.)
   A worktree counts as finished when all of these hold:
   - GitHub has a merged or closed pull request from that branch whose head commit equals the
     local branch's head;
   - no open pull request comes from that branch;
   - the folder has no `.gitmodules` file. A folder with submodules is always kept, since their
     changes can hide from `git status`;
   - `git status --porcelain --ignored --untracked-files=normal` there (the option overrides a
     repo's `status.showUntrackedFiles = no`) prints nothing but the root `uv.lock`, staged or
     not, and ignored cache folders whose own name is one of `.venv`, `node_modules`,
     `__pycache__`, `.pytest_cache`, `.ruff_cache` or `.mypy_cache`. Any other untracked, changed
     or ignored entry, file or folder (such as `.env` or `data/`), keeps the worktree.

   Without `--fix`, one row lists them: `<n> folders hold finished work: <paths>.`, with the Fix
   `forge doctor --fix`.

   With `--fix`, for each one doctor runs `git worktree remove --force <path>` from the main
   checkout, then `git branch -D <branch>`. It prints
   `- Fixed: removed <path>, whose pull request is merged.` (or `closed`).
   - When a removal fails (a locked worktree, or a file in use on Windows), a row names the folder,
     with the Fix `unlock it or close programs using it, then forge doctor --fix`.
   - When the folder is removed but `git branch -D` fails, a row says
     `Removed <path>, but its branch <branch> is still here: <git's last line>.`, with the Fix
     `git branch -D <branch>`.
   - Either failure leaves the other folders and the later repairs to go on.
   - Without `gh`, offline or signed out, nothing is listed. The `gh` rows already say why.

   Tests use a fake `gh`. They cover:
   - a merged pull request with only `uv.lock` changed: the folder and branch are removed;
   - the same case with a closed pull request;
   - a clean merged folder: removed;
   - another uncommitted file: kept;
   - an untracked file: kept;
   - an ignored `.env` file: kept;
   - an ignored `.venv/` folder: removed;
   - an ignored `data/` folder: kept;
   - the `gh` call failing, or printing something that isn't a list: nothing removed;
   - the `gh` call returning 100 entries: kept;
   - an untracked file with `status.showUntrackedFiles = no` set: kept;
   - a folder with a `.gitmodules` file: kept;
   - a local commit past the pull request's head: kept;
   - an open pull request from the same branch: kept;
   - doctor run inside that folder: kept;
   - the main checkout: never removed;
   - a failing removal: shown as a row, and the next folder still removed;
   - a failing branch deletion after the removal: its row, and the later repairs still run;
   - without `--fix`: only the row, and nothing removed.
4. The list of files comes from `sync.files`, which is exactly what `forge sync` writes. It holds
   both hosts' files whatever `workers` says: the `.claude` and `.codex` hook files, the skills,
   `.codex/config.toml`, and whatever sync later writes for either host. That includes the access
   settings, pre-allowed tools and subagent roles now in flight. Doctor never filters the list by
   the `workers` setting or by the host running it (`CLAUDECODE`, `CODEX_THREAD_ID` or neither).

   This repair runs only when the installed Forge is the pinned version, which item 1 ensures. It
   covers each differing file that item 5 doesn't hold back. A file sync wants empty (`""`) is
   removed, as `sync.write` does (`sync.py` lines 264-265).

   **On the default branch:**
   - Doctor first looks for its own fixes: local fix worktrees whose record's `why` is exactly
     `Bring the files Forge writes for Claude Code and Codex up to date` and whose item isn't
     merged. Doctor never writes in one of them again.
   - One is current when it holds the default branch's latest commit
     (`git merge-base --is-ancestor origin/<default> HEAD` there), its `forge.toml`, committed
     and in the folder, is the default branch's (`git diff --quiet origin/<default> -- forge.toml`
     there), and one of the fix's own commits (`git log origin/<default>..HEAD` there, so never an
     earlier repair already merged) has the fix's `why` as its subject.
     Then doctor starts nothing. One row says `Doctor's fix <name> holds Forge's files and
     isn't merged yet.`, with the Fix `forge close <name>`.
   - Any other is stale: its `forge.toml`, such as the pin or the test command, may be out of
     date, and sync's files follow it, or a failed run left it without its files commit. Doctor leaves it alone, and a row says
     `Doctor's fix <name> is behind <default branch>, so doctor started a new one.`, with the Fix
     `close its pull request if it has one, then git worktree remove --force <path> and git branch
     -D <branch>`.
   - When there is no current fix, doctor starts one through `forge fix start`'s own checkout step
     (`task._new_checkout`), from the default branch's latest commit, which gives the same record,
     branch and folder. It uses the slug `forge-files` and the fix start rule's suffix when that
     name is taken. The done-when is
     `The files match what forge sync writes for the pinned Forge`. The record also carries
     `allow_large`: `Doctor brings every file forge sync writes up to date in one change; <who>
     allowed it by running forge doctor --fix.`, as adoption's record does (`init.py` line 321).
     Sync's list already holds five code files and grows, so the fix limit and the interface
     paths (`githooks._promote`) would otherwise refuse it.
   - In the new fix's folder doctor works out again what sync writes there. It writes or removes
     the differing files that item 5 doesn't hold back, and commits exactly those paths with the
     fix's `why` as the subject. It prints `- Fixed: wrote <n> of Forge's files in fix <name>.`
     and the current fix's row.
   - Doctor makes its fix only when the checkout has no uncommitted changes and is at
     `origin/<default>`; otherwise a row says to commit or discard the changes first, and nothing
     is made. Doctor's fix is whatever is on its fixed branch name (`fix/forge-files`), whether or
     not its record was committed, so a later run always finds it and never makes a second one.
   - Doctor works out what differs before it makes the fix, so it never makes a fix with nothing
     in it. Doctor never removes its own fix's folder or branch, whatever happens (simpler, and no
     uncommitted work can be lost; owner rule for areas that keep breaking).
   - When writing or committing fails (sync refusing a link that leads outside the repo, a file
     the system won't write, or a commit a git hook refuses), doctor leaves the fix's folder as it
     is, and a row gives the reason with one step: finish it with `forge close <fix>` in that
     folder, or remove it with `git worktree remove --force "<path>"` and `git branch -D <branch>`,
     then run `forge doctor --fix` again.
   - Nothing is written or committed on the default branch. A file held back keeps its own row.

   **On any other branch:** doctor writes or removes the files in place and doesn't commit them,
   as `forge sync` does. It prints `- Fixed: wrote <path>.` or `- Fixed: removed <path>.` for each
   file. It checks the branch before writing anything: on a detached HEAD it writes nothing, a row
   gives sync's refusal with its own Next as the Fix, and the drift rows stay. When a write fails
   part way (a link that leads outside the repo, a file the system won't write), the files already
   written stay, as `forge sync` leaves them, the failure becomes a row with the Fix
   `forge doctor --fix`, and the files not yet written keep their rows.

   Once doctor has written the files in place, their rows are gone. So is the row saying the tests
   check doesn't run the test command (lines 172-175): the workflow is one of sync's files.

   Tests cover:
   - `workers = "claude"`, run with `CODEX_THREAD_ID` set, on the default branch with drifted
     `.codex/hooks.json` and `.claude/settings.json`: one fix holds both, the default branch has
     no new commit, and the row says `forge close`;
   - a second run: no new fix and no new commit, and the current fix's row;
   - `workers = "codex"`, run with `CLAUDECODE` set: both hosts' files are repaired;
   - on a fix branch: written in place and not committed;
   - a failed pin install: the drift rows stay and nothing is written;
   - another fix already using the slug with a different `why`: a new fix with a suffixed name;
   - the new fix's record carries `allow_large`;
   - a file sync wants empty: removed in place, and removed in the fix's commit;
   - doctor's fix behind a default branch that has since changed the test command: nothing
     changed there, its row, and a new fix with the new workflow;
   - doctor's fix with a local edit to its `forge.toml`: nothing changed there, and a new fix;
   - nothing differing: no fix left behind;
   - a fix holding one repaired file and one held back: the fix's row and the held-back row;
   - a commit a git hook refuses: its row, the new fix's folder and branch gone, and the next run
     makes the fix;
   - the same with the new fix's folder locked so it can't be removed: its row naming the folder,
     and the next run reports it stale and makes a new fix with the files, also when an earlier
     doctor repair is already on the default branch;
   - a file the system won't write after another was written: in a new fix, its row and the fix
     gone; in place, its row, the written file stays, and the next run finishes;
   - a link that leads outside the repo: its row;
   - a detached HEAD: its row, the drift rows, and no file or the index changed.

   `tests/test_upgrade_doctor.py`'s drift row now expects `Fix: forge doctor --fix`.
5. **Hand edits.** Doctor holds back a differing file in either of these cases:
   - it has uncommitted changes, staged, unstaged or untracked, in the checkout doctor runs in;
   - the last commit that changed it (`git log -1` on the branch doctor writes on) is not
     Forge's. A commit is Forge's only when it is already on the default branch
     (`git merge-base --is-ancestor <commit> origin/<default>`) and either changes the pinned
     version (the value `repo._pin` reads from `forge.toml` differs from the one in the commit's
     parent; an edit to that line that keeps the value doesn't count) or has a subject that starts
     with doctor's fix `why` above (a squashed merge keeps it, perhaps followed by ` (#<n>)`).
     Such a commit can't carry a hand edit to these
     files: adoption writes them itself (`init.py` line 317), close refuses a fix or task that
     changes the version while any of them isn't what `forge sync` writes (`close._synced`, lines
     206-235), and doctor's own fix holds only what sync writes. A commit not yet on the default
     branch, such as a local one that changes the pin and a skill together, has passed no such
     check, so it holds the file back.

   A file whose text already matches sync doesn't differ, so it is never held back. A file with no
   commit yet belongs to Forge. In Forge's own repo (`repo = "forge-source"`) the templates sit in
   the same repo, so no file there is held back because of its history. Uncommitted changes still
   hold a file back. Staged changes count even when the working copy matches sync.

   A file held back keeps its row, with the reason `was changed by hand (<that commit's subject>),
   so doctor won't overwrite it`, or `has changes not committed yet, so doctor won't overwrite
   it`, and the Fix `move your change out of this file, since forge sync rewrites it, then forge
   doctor --fix`.

   **Rows that stay a plain step.** These keep today's text and Fix:
   - missing tools;
   - GitHub sign-in;
   - `sh`;
   - the Autoreview helper;
   - a broken Forge block;
   - a failing host hook;
   - no checks;
   - checks that differ from branch protection;
   - no test command;
   - Codex trust;
   - the UI skills.

   The UI skills check now covers each host that `workers` names, plus any host whose program
   (`claude` or `codex`) is on PATH. Before, it covered the `workers` host only.

   **Rows `--fix` repairs.** These are the version row when item 1 applies, the SDK, the hooks,
   drifted files that aren't held back, and finished folders. Each says `Fix: forge doctor --fix`.

   **Without `--fix`,** doctor changes nothing it didn't already change before. It still stops
   leftover Codex processes.

   **Exit code.** Doctor exits nonzero while any row remains, and zero when `--fix` repaired
   everything in place.

   Tests cover:
   - a skill file changed in a commit without `forge.toml`: held back, with the row;
   - the same file changed together with `forge.toml`'s `version` line, on the default branch:
     repaired;
   - the same, in a local commit on a fix branch that isn't on the default branch: held back;
   - the same file changed on the default branch together with a `version` line edit that keeps
     the pinned value: held back;
   - the same file changed together with another `forge.toml` line: held back;
   - the same file last changed by a commit whose subject is doctor's fix `why` with ` (#12)`:
     repaired;
   - an uncommitted edit in the checkout doctor runs in: held back;
   - a staged hand edit whose working copy matches sync: held back, and the index unchanged;
   - Forge's own repo: history doesn't hold a file back;
   - `workers = "claude"` with `codex` on PATH and the skill missing from the Codex folders: a
     row;
   - the same without `codex` on PATH: no row;
   - GitHub signed out: still a row after `--fix`;
   - the exit codes.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| REPAIRS | Doctor repairs | `--fix` installing the pinned Forge and running again with it, putting back git hooks, the Codex SDK rule, removing finished folders, the `- Fixed:` line and `Fix: forge doctor --fix` for its rows, the option's help and command listing, and the skill's setup row | 1, 2, 3 | `src/forge/doctor.py`, `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/`, `docs/commands.md` | `tests/test_doctor_fix.py`, `tests/test_fix_in_a_repo_whose_git_hooks_folder_is_set.py`, `tests/test_contracts.py`, `tests/test_split_commands.py` | none | yes |
| FILES | Forge's files | Both hosts' synced files brought up to date in doctor's own fix or in place, files changed by hand held back, and the UI skills check for both hosts | 4, 5 | `src/forge/doctor.py` | `tests/test_doctor_fix_files.py`, `tests/test_upgrade_doctor.py` | REPAIRS | yes |

New moving parts: none

## Notes

- REPAIRS pins the shared pieces that FILES uses:
  - the repair line format `- Fixed: <what>.`;
  - the Fix text `forge doctor --fix`;
  - the order of repairs: the pin first (and running again), then the SDK, hooks and folders.

  FILES waits for REPAIRS because both change `doctor.py`, and FILES needs the pinned version in
  place before it writes files.
- What doctor checks today (`src/forge/doctor.py` at `e8792e10`), and what `--fix` does with each:

  | Lines | Check | `--fix` |
  |---|---|---|
  | 82-86, 98-99 | Codex SDK missing or wrong, where Codex is used | Installs it (already does) |
  | 89-91 | git, gh, uv or claude missing | Plain step: installing system tools is the person's call |
  | 92-93 | gh not signed in | Plain step |
  | 94-97 | Installed Forge isn't the pin | Installs the pin when it is newer (item 1) |
  | 100-103 | Autoreview helper not at its pin | Plain step: a copy into the user's own skills folder |
  | 105-116 | Doctor can't work out sync's files (a broken Forge block) | Plain step |
  | 117-119 | A synced file differs | In doctor's fix on the default branch, in place elsewhere; held back when changed by hand (items 4, 5) |
  | 120-125 | Git hooks missing | Puts them back (item 2) |
  | 127-129 | `sh` missing | Plain step |
  | 131-146 | A host hook fails | Plain step. It usually clears once the pin and files are repaired |
  | 148-150 | No checks in forge.toml | Plain step: the owner chooses |
  | 151-168 | Checks differ from branch protection | Plain step: the owner chooses |
  | 169-171 | No test command | Plain step |
  | 172-175 | The tests check doesn't run the test command | Cleared by the file repair: the workflow is a synced file |
  | 180-186, 216-218 | Codex doesn't trust the project | Plain step: trust lives in the user's own Codex settings and is their consent |
  | 190-206 | UI skills missing | Plain step, now for both hosts (item 5) |
  | 208-209 | Leftover Codex processes | Stops them (already does, on every run) |
  | new | Folders of finished work | Removes them (item 3) |
- Cut: clearing Forge's leftover Docker test containers and networks. The prototype deploy test now
  labels its own leftovers and sweeps any over an hour old, so doctor has nothing to add.
- Not added: a check for a renamed default branch. Doctor has none today, and this story adds only
  the repairs asked for.
- Decided: stale doctor fix: never refreshed; doctor starts a fresh fix (owner, 2026-10-01)
- Decided in drafting: "anything on the default branch that needs a commit" stays a plain step,
  except Forge's own files. Those go into doctor's own fix, which the owner merges like any other.
  Settings in forge.toml (checks, the test command) stay the owner's choice.
- Access settings, pre-allowed tools and subagent roles for both hosts are in flight in sync.
  Doctor picks them up through sync's file list and doesn't duplicate them.
- No client repo is named anywhere in this story's code, tests, texts or commits.
- Claude workers build both parts. Opus writes the skill row.
- Each new test file starts with `STORY = "FORGE-DOCTORFIX-1"`, and its `test_<n>_` names cite the
  Done-when items its task covers.
