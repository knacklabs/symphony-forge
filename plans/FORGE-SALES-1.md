# A salesperson can build and demo a prototype without engineering help

4 parts · Risks: none · New moving parts: one install script for Macs

## What changes for you

- A salesperson sets up their Mac for prototyping with one script, and a one-page checklist walks
  them from an empty repo to a live demo.
- Before the customer signs off, prototype changes merge themselves once their tests pass and the
  review is clean; nobody has to judge a pull request. After sign-off the repo's own merge setting
  applies again.
- The agent groups everything from one conversation into one change per demo round, talks about
  the demo ("the next version is live", "the reviewer found a missing error message") rather than
  Forge's words, and says when to connect the repo to our deploy platform.

## Why

Salespeople are well suited to the FDE route: they know the customer and the pain. What trips them
up is the engineering around it: merging pull requests, installing Node, Docker and test browsers,
small tweaks each waiting on a full review, and Forge's own vocabulary.

## Done when

1. **Prototype changes merge themselves.** In a client repo without an accepted sign-off, a ready
   item is merged by the agent through `forge merge`, and `forge close` says so, whatever
   `forge.toml`'s `merge` says; with an accepted sign-off the setting applies as today; Forge's own
   repo is unaffected.
2. **One script sets up a Mac.** `scripts/install-mac.sh` checks for and installs what prototyping
   needs (Homebrew, git, GitHub CLI, Node, Docker, uv, Forge at the release the script names,
   Playwright's browsers, and the Codex SDK through `forge doctor --fix`), skips what is already
   there, prints each step in plain words, supports `--check` to list only what is missing, and
   ends by running `forge doctor`.
3. **The agent talks demo, not Forge.** The skill's prototype section tells the agent to batch one
   conversation's requests into one prototype fix per demo round, to describe progress in the
   demo's terms and never in Forge's (fix, worktree, branch, pull request), and to tell the
   salesperson when to connect the repo to our deploy platform.
4. **forge next says when to connect the platform.** In a client repo without an accepted
   sign-off, when the default branch has a `Dockerfile` and `docs/product/BRIEF.md` has no
   `- Demo address:` line, `forge next` says to connect the repo on our deploy platform, pick a
   subdomain, and record the address there.
5. **A checklist starts a prototype.** `docs/start-a-prototype.md` lists, in plain words, getting a
   GitHub seat and a repo, running the install script, opening Claude Code or Codex in the repo,
   `forge init`, discovery, connecting the platform and sign-off, and the README links it.

## Risks

Risks: none

## For the builders

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SPEC | The checklist | The start-a-prototype checklist and the README's link to it | 5 | `docs/start-a-prototype.md`, `README.md` | `tests/test_sales_checklist.py` | none | yes |
| MERGE | Merge until sign-off | The effective merge setting for close and merge before sign-off | 1 | `src/forge/close.py`, `src/forge/merge.py`, `src/forge/repo.py` | `tests/test_sales_merge.py` | none | yes |
| INSTALL | One install script | The Mac install script with its check mode | 2 | `scripts/install-mac.sh` | `tests/test_sales_install.py` | none | yes |
| TALK | Talk demo | The skill's prototype conversation rules and forge next's platform reminder | 3, 4 | `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/`, `src/forge/nextstep.py`, `tests/test_trim_skills.py`, `tests/test_split_ships.py` | `tests/test_sales_talk.py` | none | yes |

New moving parts: one install script for Macs (Done-when 2)

## Notes

- MERGE adds `repo.merge_setting(top)`: "agent" when the repo is a client repo and
  `approval.signed_off(top)` is false, else the default branch's `forge.toml` `merge`; `close.py`
  and `merge.py` both read it instead of the raw setting. The deny hook's block on a raw
  `gh pr merge` is unchanged.
- INSTALL's test runs the script with `--check` against a PATH of stub commands, so it installs
  nothing; it checks that a present tool is skipped and a missing one is listed. The script names
  the Forge release in one variable at its top.
- TALK's `- Demo address: <url>` line is the one place the demo address lives until sign-off; the
  sign-off decision copies it.
- Each test file starts with `STORY = "FORGE-SALES-1"`, and its `test_<n>_` names cite the
  Done-when items its task covers.
