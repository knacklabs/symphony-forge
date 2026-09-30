# One command upgrades Forge in a repo

2 parts · Risks: none · New moving parts: none

## What changes for you

- One command upgrades Forge in a repo. It installs the new release, has that release refresh
  Forge's files, and opens the upgrade's pull request, which then merges like any other change.
- You can name the release or leave it out to get the newest. The command says what it did at
  each step.
- If you're not on the main branch, or you have changes you haven't committed, it stops before
  doing anything and tells you why in plain words. If it's interrupted, running it again picks
  up where it stopped.
- It works the same from Claude Code, from Codex or from your own terminal. It refreshes the
  files for both Claude Code and Codex, whichever one builds the code.
- It never touches your model choices or any other setting in Forge's settings file. Only the
  version changes.

## Why

Today an upgrade takes six manual steps, and two of them fail without saying so. A plain
reinstall can reuse an old cached build. An older Forge left earlier on the path can run the
old release's refresh in place of the new one's. Either way the upgrade lands with outdated
files. One command that runs every step, in order and with the right release, takes that work
off the owner and the agent.

## Done when

1. **One command upgrades Forge to the release you name, or to the newest when you name none, and opens its pull request.**
2. **The new release writes the upgrade's files for both Claude Code and Codex, whichever of them runs the command or builds the code.**
3. **Your model choices and every other setting in Forge's settings file stay exactly as they were.**
4. **Your agent upgrades Forge with that one command.**

## Risks

Risks: none

## For the builders

### Done-when details

1. `forge upgrade [release]` is a new command in `src/forge/upgrade.py`. Its declaration sets
   `changes_state: False`, so `cli._run` skips `repo.check_pin` for it. The command itself
   changes the pin. Under the pin check an older installed Forge would re-run the old pinned
   release, and that release has no upgrade command. The command runs from the main checkout
   and makes its own checks.
   - **Refusals.** It stops before creating anything (no fix, no install) and uses the usual
     problem line plus `Next:` line, in each of these cases:
     - Forge's own repo (`repo = "forge-source"`), which moves its version by releasing.
     - A checkout that isn't on the default branch.
     - Uncommitted changes to tracked files. Untracked files don't count.
     - A release that isn't `v` followed by three numbers.
     - A release that isn't newer than the pin on the freshly fetched default branch. This
       covers the same version and a downgrade.
     - No release named and the newest can't be found. The newest comes from
       `gh release view --repo knacklabs/symphony-forge --json tagName`. Its refusal gives
       gh's reason and says to name a release.
     - An upgrade fix for another release is already open: a worktree on a
       `fix/upgrade-forge-to-…` branch for a different release. This also covers a rerun with
       no release named after a newer release came out. The refusal names that fix, and its
       `Next:` line says to finish it with `forge upgrade <its release>` or remove it.
     - The version edit in item 3 can't be made. The command works it out on the freshly
       fetched default branch's `forge.toml` before creating anything.
   - **Steps.** Each step prints one line:
     1. It starts the fix `upgrade-forge-to-v<x>-<y>-<z>` from the default branch as last
        fetched, using the same checkout helper `forge fix start` and `forge merge enable` use.
        The fix records why "Upgrade Forge to <release>." and done-when "This repo pins and
        runs Forge <release>."
     2. It sets `version` in the fix's `forge.toml` (see item 3).
     3. It installs the release with exactly
        `uv tool install --force --reinstall --no-cache --python 3.11 git+https://github.com/knacklabs/symphony-forge@<release>`,
        unless `forge --version` on PATH already reports the release.
     4. It checks that `forge --version` on PATH now reports the release. Otherwise it refuses
        and names the stale `forge` it found and where it lives.
     5. It runs the release's `forge sync` in the fix's folder the way `check_pin` runs a
        pinned release through uv. That uv call becomes one helper in `repo.py` that
        `check_pin` and the upgrade share, and the existing pinned-run tests pass unchanged.
     6. It commits `forge.toml` and everything that sync changed, deletions included, as
        "Upgrade Forge to <release>". New git hook shims are left out using the filter close's
        synced check applies (`close._synced`), also when the hooks folder is inside the
        checkout. The fix's folder is the upgrade's own, so the commit takes everything in it,
        and close's review sees all of it.
     7. It runs the release's `forge close <fix>` the same way, with its output streamed.
     8. It exits with close's exit code, also when close refuses. Close's last line already says who merges: the human,
        or `forge merge <fix>` when the repo's merge setting allows it.
   - **Failure at a step.** A failed install refuses with uv's last line and a `Next:` line
     telling the user to run the install command in their own terminal, then
     `forge upgrade <release>` again. This also covers a Windows launcher that can't be
     replaced while it runs, and a sandbox with no network. A failed sync shows the release's
     own refusal and stops before the commit and close; a rerun syncs again. A refusing close
     shows its own output, and its exit code is the command's.
   - **Rerun.** Running the command again with the same release continues the fix when its
     folder exists and the state in that folder, committed or not, records the upgrade's why.
     A folder with no state and no commit of its own, left by an interruption right after
     `task._new_checkout` made it, is taken up: the command writes and commits the fix's state
     there, as fix start does, and goes on. Each step can safely run twice: the
     pin that's already set, the install skipped because PATH reports the release, the sync,
     the commit (skipped when there's nothing to commit), then close. A fix with that name and
     another why, or its branch without its folder, refuses and names the fix, and nothing
     changes.
   - **Tests** use the stub gh, the fake review, and a fake uv on PATH. The fake uv logs each
     call. On `tool install` it puts a launcher on PATH. On `tool run` it runs a copy of this
     checkout's code whose `__version__` reads as the release and whose skill template carries
     a marker. The tests cover:
     - a named release reaching Ready, with the uv calls and printed lines checked in order;
     - no release named, taking gh's newest;
     - each refusal, with nothing created afterwards;
     - newest changing between two runs: the second run refuses and names the open fix;
     - a failed install, then a rerun reaching Ready without a second fix;
     - an interruption right after the folder was made (folder and branch, no state), then a
       rerun reaching Ready without a second fix;
     - a failed release sync: nothing committed and close never runs; then a rerun after
       the sync is fixed reaching Ready;
     - a rerun after the commit;
     - close refusing: its output is shown and the command exits with its code;
     - a release whose sync deletes a file: the deletion is in the commit;
     - a checkout with `core.hooksPath = ".husky/_"`: sync's new shims are not in the commit;
     - a stale forge shadowing the install;
     - a taken fix name.
   - The help golden in `tests/test_split_commands.py` gains `upgrade`.
2. `forge sync` already writes both hosts' files (skill copies, hook files and
   `.codex/config.toml`) whatever the host or the `workers` setting. This item proves it
   through the upgrade and the marker described in item 1. A test runs the full upgrade in six
   cases: under `CLAUDECODE`, under `CODEX_THREAD_ID` and with neither set, each with
   `workers = "claude"` and with `workers = "codex"`. It asserts:
   - The committed `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` both
     carry the release's marker.
   - Both hosts' hook files and `.codex/config.toml` are what the release writes.
   - The sync that ran was the release's: the fake uv logged a `tool run --from …@<release>`
     call for `sync`.
   - The installed Forge's own sync never wrote the files.
   - A setting the test adds to `.codex/config.toml` survives. Sync turns on Codex's project
     hooks there and keeps every other setting (`sync._codex_config`). That refresh, like the
     skill and hook files and git's roadmap merge driver, is Forge's own files, not a setting
     in `forge.toml`.
3. The only change the command makes to `forge.toml` is the value of the top-level `version`
   line. It edits that line as text in bytes, the way `forge merge enable` edits `merge`,
   which keeps comments, line endings and every table. It parses the result and refuses,
   leaving the file alone, if that parse doesn't give the release. Nothing adds, removes or
   rewrites `[models]` or any other key. New model defaults are never pushed into an existing
   repo. If the release's own settings check rejects the repo's `forge.toml`, the release's
   sync refuses with its own message and the upgrade stops there. Tests:
   - The upgrade runs on a CRLF `forge.toml` that has comments, custom `[models.*]` tables and
     a `merge` setting. The committed `forge.toml` must be byte-for-byte the original with
     only the version string changed.
   - A `forge.toml` whose version is a multi-line string refuses before anything is created,
     and the file's bytes are unchanged.
   - When the marked release's settings check rejects a key the test adds, the command shows
     the release's refusal, commits nothing, never runs close, and `forge.toml` in the fix's
     folder differs from the original only in the version string.
4. The skill's "Upgrade Forge" section drops the six manual steps. In their place: ask which
   release, recommending the newest, then run `forge upgrade <release>`; when it refuses,
   follow its `Next:` line; close's last line says who merges. The skill's command table
   gains the command's row. The README's "Upgrade a project" and the guide's "Upgrading a
   repo" sections say the same in a few lines. Tests:
   - UPGRADE's test checks that the skill `forge sync` writes for both hosts names
     `forge upgrade` in its Upgrade section and no longer tells the agent to run
     `forge fix start "Upgrade Forge`.
   - GUIDE's test checks that the README and the guide name the command.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| UPGRADE | Upgrade command | The `forge upgrade` command, the shared release-run helper, the regenerated command page, and the skill's upgrade text and command row | 1, 2, 3, 4 | `src/forge/upgrade.py`, `src/forge/repo.py`, `docs/commands.md`, `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/` | `tests/test_upgrade_command.py`, `tests/test_split_commands.py` | none | yes |
| GUIDE | Upgrade guide | The README's and guide's upgrade text naming the one command | 4 | `README.md`, `docs/guide.md` | `tests/test_upgrade_guide.py` | none | yes |

New moving parts: none

## Notes

- The command reuses existing pieces:
  - the checkout helper behind `forge fix start` and `forge merge enable`;
  - `forge merge enable`'s way of editing one line in `forge.toml`;
  - `check_pin`'s way of running a release through uv;
  - the hook-shim filter in close's synced check;
  - `forge close` itself.
- The pin refusal's install line and the CI workflow's install line stay as they are. Changing
  them would rewrite every client's workflow, and that is out of scope.
- Refused on purpose: downgrades, and Forge's own repo. An upgrade fix already open for another
  release is left alone, and the command names it.
- A repo pinned to a release without this command upgrades once more by the old steps, or with
  `uvx --from git+https://github.com/knacklabs/symphony-forge@<release> forge upgrade <release>`.
  That works because the command skips the pin check, and it installs the release because the
  `forge` on PATH is still the old one.
- The skill changes in UPGRADE because this repo's review rules want a new command and the
  skill's text for it in the same change. GUIDE has no After: its README and guide text names
  the command but doesn't need its code.
- No client repo is named anywhere in this story's code, tests, texts or commits.
- Claude workers build every part. Opus writes GUIDE's text.
- Each new test file starts with `STORY = "FORGE-UPGRADECMD-1"`, and its `test_<n>_` names cite
  the Done-when items its task covers.
