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
- It never touches your model choices or any other setting. Only the version changes.

## Why

Today an upgrade takes six manual steps, and two of them fail without saying so. A plain
reinstall can reuse an old cached build. An older Forge left earlier on the path can run the
old release's refresh in place of the new one's. Either way the upgrade lands with outdated
files. One command that runs every step, in order and with the right release, takes that work
off the owner and the agent.

## Done when

1. **One command upgrades Forge to the release you name, or to the newest when you name none, and opens its pull request.**
2. **The new release writes the upgrade's files for both Claude Code and Codex, whichever of them runs the command or builds the code.**
3. **Your model choices and every other setting stay exactly as they were.**
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
     6. It commits `forge.toml` and everything that sync changed as "Upgrade Forge to
        <release>". Git hook shims are left out using the filter close's synced check applies.
     7. It runs the release's `forge close <fix>` the same way, with its output streamed.
     8. It exits with close's exit code. Close's last line already says who merges: the human,
        or `forge merge <fix>` when the repo's merge setting allows it.
   - **Failure at a step.** A failed install refuses with uv's last line and a `Next:` line
     telling the user to run the install command in their own terminal, then
     `forge upgrade <release>` again. This also covers a Windows launcher that can't be
     replaced while it runs, and a sandbox with no network. A failed sync or close shows the
     release's own refusal and stops.
   - **Rerun.** Running the command again with the same release continues the fix when its
     folder exists and its recorded why is the upgrade's. Each step can safely run twice: the
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
     - a failed install, then a rerun reaching Ready without a second fix;
     - a rerun after the commit;
     - a stale forge shadowing the install;
     - a taken fix name.
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
3. The only change the command makes to `forge.toml` is the value of the top-level `version`
   line. It edits that line as text in bytes, the way `forge merge enable` edits `merge`,
   which keeps comments, line endings and every table. It parses the result and refuses,
   leaving the file alone, if that parse doesn't give the release. Nothing adds, removes or
   rewrites `[models]` or any other key. New model defaults are never pushed into an existing
   repo. If the release's own settings check rejects the repo's `forge.toml`, the release's
   sync refuses with its own message and the upgrade stops there. A test runs the upgrade on a
   CRLF `forge.toml` that has comments, custom `[models.*]` tables and a `merge` setting. The
   committed `forge.toml` must be byte-for-byte the original with only the version string
   changed.
4. The skill's "Upgrade Forge" section drops the six manual steps. In their place: ask which
   release, recommending the newest, then run `forge upgrade <release>`; when it refuses,
   follow its `Next:` line; close's last line says who merges. The README's "Upgrade a
   project" and the guide's "Upgrading a repo" sections say the same in a few lines. A test
   checks two things. First, the skill `forge sync` writes for both hosts names
   `forge upgrade` in its Upgrade section and no longer tells the agent to run
   `forge fix start "Upgrade Forge`. Second, the README and the guide name the command.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| UPGRADE | Upgrade command | The `forge upgrade` command, the shared release-run helper, and the regenerated command page | 1, 2, 3 | `src/forge/upgrade.py`, `src/forge/repo.py`, `docs/commands.md` | `tests/test_upgrade_command.py` | none | yes |
| GUIDE | Upgrade guide | The skill's, README's and guide's upgrade text naming the one command | 4 | `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/`, `README.md`, `docs/guide.md` | `tests/test_upgrade_guide.py` | none | yes |

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
  release is left alone.
- A repo pinned to a release without this command upgrades once more by the old steps, or with
  `uvx --from git+https://github.com/knacklabs/symphony-forge@<release> forge upgrade <release>`.
  That works because the command skips the pin check, and it installs the release because the
  `forge` on PATH is still the old one.
- GUIDE has no After. Its text names the command but doesn't need its code. The command table
  in the skill is edited only by GUIDE, and `docs/commands.md` only by UPGRADE.
- No client repo is named anywhere in this story's code, tests, texts or commits.
- Claude workers build every part. Opus writes GUIDE's text.
- Each new test file starts with `STORY = "FORGE-UPGRADECMD-1"`, and its `test_<n>_` names cite
  the Done-when items its task covers.
