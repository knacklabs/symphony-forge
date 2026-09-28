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

1. **Prototype changes merge themselves.** A decision records the owner's choice that the agent
   merges prototype changes until sign-off. In a client repo whose default branch has no accepted
   sign-off, a ready item is merged by the agent through `forge merge`, and `forge close` and
   `forge next` say so, whatever `forge.toml`'s `merge` says; once the default branch has an
   accepted sign-off, the setting applies as today; Forge's own repo is unaffected.
2. **One script sets up a Mac.** `scripts/install-mac.sh` in Forge's repo, run with one
   `curl … | bash` line from the checklist, checks for and installs what prototyping needs
   (Homebrew, git, GitHub CLI, Node, Docker, uv, Forge at the release the script names, Claude Code,
   Codex and Playwright's browsers), skips what is already there, prints each step in plain words,
   supports `--check` to list only what is missing, and ends by printing `forge --version` and the
   checklist's next step.
3. **The agent talks demo, not Forge.** The skill's prototype section tells the agent to batch one
   conversation's requests into one prototype fix per demo round, to describe progress in the
   demo's terms and never in Forge's (fix, worktree, branch, pull request), and to tell the
   salesperson when to connect the repo to our deploy platform.
4. **forge next says when to connect the platform.** In a client repo without an accepted
   sign-off, when the default branch has a `Dockerfile` and its `docs/product/BRIEF.md` has no
   `## Demo` section with a `- Address: <url>` line, `forge next` says to connect the repo on our
   deploy platform, pick a subdomain, and record the address there; the skill tells the agent to
   copy that address into the sign-off decision.
5. **A checklist starts a prototype.** `docs/start-a-prototype.md` lists, in plain words and in
   this order: getting a GitHub seat and a new repo; running the install script; signing in to
   Claude Code or Codex; opening it in the repo and asking for `forge init`, which also installs
   the Codex SDK through `forge doctor --fix`; discovery with the customer; asking the agent to
   build the demo, which it builds, tests and merges; connecting the repo to our deploy platform
   (the address and who grants access are a placeholder to fill in: "ask your lead"); and
   sign-off. The README links it.

## Risks

Risks: none

## For the builders

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SPEC | The checklist and the decision | The start-a-prototype checklist, the README's link to it, and the decision that the agent merges until sign-off | 1, 5 | `docs/start-a-prototype.md`, `README.md`, `docs/decisions/` | `tests/test_sales_checklist.py` | none | yes |
| MERGE | Merge until sign-off | The effective merge setting for close and merge before sign-off | 1 | `src/forge/close.py`, `src/forge/merge.py`, `src/forge/repo.py` | `tests/test_sales_merge.py` | none | yes |
| INSTALL | One install script | The Mac install script with its check mode | 2 | `scripts/install-mac.sh` | `tests/test_sales_install.py` | none | yes |
| TALK | Talk demo | The skill's prototype conversation rules and forge next's platform reminder | 1, 3, 4 | `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/`, `src/forge/nextstep.py`, `tests/test_trim_skills.py`, `tests/test_split_ships.py` | `tests/test_sales_talk.py` | MERGE | yes |

New moving parts: one install script for Macs (Done-when 2)

## Notes

- MERGE adds `repo.merge_setting(top)`: "agent" when the repo is a client repo and the default
  branch as last fetched has no accepted sign-off (the sign-off check read from that branch only,
  never from the current checkout), else the default branch's `forge.toml` `merge`; `close.py` and
  `merge.py` read it instead of the raw setting, and TALK makes `nextstep.py`'s ready and cleanup
  paths read it too. The deny hook's block on a raw
  `gh pr merge` is unchanged.
- INSTALL's test runs the script against a PATH of stub commands, so it installs nothing: `--check`
  lists only the missing tools, and a full run calls each missing tool's installer once, skips the
  present ones, installs the Forge release named in the script's one variable, and prints the next
  step. Installing Homebrew, Docker and browsers for real is proven once on a clean Mac and
  recorded in the functional check, not in CI.
- TALK reads `## Demo` / `- Address: <url>` in `docs/product/BRIEF.md` from the default branch as
  last fetched; it is outside `## Answers`, so the answers parser ignores it. Copying the address
  into the sign-off decision is an instruction in the skill, not code.
- Each test file starts with `STORY = "FORGE-SALES-1"`, and its `test_<n>_` names cite the
  Done-when items its task covers.
