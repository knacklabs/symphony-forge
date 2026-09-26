# Forge guide

Forge takes each change to a client's app from an approved story to a merged pull request, and
Claude Code and Codex drive it the same way. This guide covers installing it, its commands, the
two lanes, upgrading and releasing. The engineering rules live on the standards page, which ships
inside Forge and goes into every worker's brief. How Forge behaves is set by its spec,
`docs/specs/lean-forge-v1.md`.

## Install

You need git, the GitHub CLI (`gh`, signed in with `gh auth login`), `uv` and Claude Code, which
runs Forge's workers. Codex can coordinate the work too; Codex workers come in a later release.
Install the release a repo pins (uv brings Python 3.11 or later if you don't have it):

```
uv tool install git+https://github.com/knacklabs/symphony-forge@v1.0.0
```

`forge --version` prints the installed version. Each repo pins its release in `forge.toml`, and
every command that changes something refuses to run when the installed version differs, printing
the install line to fix it.

- **A new repo:** create it on GitHub with an `origin` remote and no commits, then run `forge init`.
  It writes `forge.toml`, the docs skeleton and the files for both hosts in one first commit,
  pushes it, installs the git hooks and switches on branch protection for the default branch.
- **A repo that copied in the old Forge:** `forge migrate` moves it over in one pull request.
- **Every clone:** run `forge sync` once, because the git hooks are installed, not committed.
  Then `forge doctor` checks the tools, the pin, the hooks and CI, and prints a fix for each
  problem it finds.

## Where to start

Run `forge next` whenever you're unsure. It says where things stand in one sentence and prints the
exact next command. The same text appears when a Claude Code or Codex session starts.

## Commands

| Command | What it does |
|---|---|
| `forge init` | Sets up a new repo: `forge.toml`, the docs skeleton, the first commit, then `forge sync` |
| `forge sync` | Writes the generated files for both hosts, the CI workflow and the git hooks |
| `forge doctor` | Checks tools, versions, hooks, generated-file drift and CI; one row per problem, each with a fix |
| `forge migrate` | Moves a client from the copied-in Forge in one pull request |
| `forge next` | Says where things stand and gives the exact next command |
| `forge board` | Writes the plain-English board page and opens it (`--out <path>` to write it elsewhere) |
| `forge story new <KEY> "<title>"` | Starts a story's branch, worktree and doc (`--from-fix <fix>` promotes a fix) |
| `forge read <KEY or spec>` | Runs the one cold read of a story doc or spec (`--amended` records the one amendment) |
| `forge story done <KEY> "<outcome>"` | Records a finished story's outcome sentence and dates |
| `forge task start <KEY>/<TASK>` | Starts a task in its own branch and worktree |
| `forge fix start "<why>" --done "<done when>"` | Starts a small fix in its own branch and worktree |
| `forge fix allow-large "<reason>"` | Records the human's permission for a fix to go over the fix limit |
| `forge work <item>` | Runs the worker on a task or fix: the first build, or a fix round |
| `forge close <item>` | Closes a task or fix by the close rule |
| `forge spec save <slug>` | Saves a spec as a draft |
| `forge spec confirm <slug> --by "<name>"` | Marks a spec confirmed after the human confirms it in chat |
| `forge spec payback --build-days <n> --day-rate <n> <value>` | Says whether a build pays back: build (three months or less), smallest slice first (up to twelve), don't build, or find out first when no value can be estimated. The value is any of `--hours-per-month`, `--people` and `--hourly-rate`; `--revenue-per-month`; `--incident-cost` and `--incident-chance`, weighed by `--confidence measured`, `estimated` or `guessed` (the default). Use rounded rates, never real salaries. It changes nothing |
| `forge decision new <slug>` | Writes a decision record |
| `forge decision accept <slug> --by "<name>"` | Accepts a decision after the human confirms it in chat |
| `forge roadmap add <spec>` | Adds roadmap items from a confirmed spec |
| `forge hook context` | Session start: prints `forge next` and the story's state |
| `forge hook deny` | Before each shell command: blocks destructive commands, `--no-verify` and `gh pr merge` |
| `forge hook approval` | After the plan and question tools: records approvals and counts human touches |
| `forge hook pre-commit` | The git pre-commit rules |
| `forge hook pre-push` | The git pre-push rules |
| `forge hook pr-check` | The required `forge-pr-check`, run in CI from the base branch |

You never run the hook commands yourself: git, the host hooks and CI call them.

## How a story runs

1. Add the story to the roadmap from its confirmed spec with `forge roadmap add <spec>`.
2. `forge story new <KEY> "<title>"` makes the story's branch, worktree and doc. The doc says what
   changes for the client, why, when it's done, the tasks, any new moving parts and the risks.
3. `forge read <KEY>` runs one independent cold read. Answer every finding (cut, defer or keep),
   amend the doc once, then run `forge read <KEY> --amended`.
4. The human approves once. In Claude Code, exit Plan Mode with the story doc as the plan; in Codex,
   ask the approval question `forge next` gives. `forge hook approval` records it.
5. For each task `forge next` lists as ready: `forge task start <KEY>/<TASK>`, then
   `forge work <KEY>/<TASK>`, then `forge close <KEY>/<TASK>`. Tasks with separate Scopes run at
   the same time.
6. The human merges each pull request. After the last one, record the outcome with
   `forge story done <KEY> "<outcome>"`.

Only the human approves a story, chooses between options and merges. The agent does the rest.

## The two lanes

- **Story:** any change that touches an interface or more than five code files.
- **Fix:** a small change, started with `forge fix start "<why>" --done "<done when>"`. Specs,
  decisions, the roadmap and discovery notes always ship as fixes, since planning documents don't
  count toward the limit. A fix that grows past five code files or touches an interface is
  refused at commit; either promote it with `forge story new <KEY> --from-fix <fix>`, which keeps
  its commits, or have the human allow it with `forge fix allow-large "<reason>"`.

Planning records follow the same lane: `forge spec save <slug>`, a cold read with
`forge read <slug>`, then `forge spec confirm <slug> --by "<name>"` once the human confirms in
chat. Decisions use `forge decision new <slug>` and `forge decision accept <slug> --by "<name>"`.

## Closing

`forge close <item>` follows the close rule: it merges the default branch in, pushes and opens or
updates the pull request, runs the review until no serious finding is left, waits for the checks
`forge.toml` names (`tests` and `forge-pr-check` by default), and marks the item ready. While the
review is blocked the pull request is a draft, and close marks it ready for review once the review
is clean and the checks are green. When it stops, it prints why and the next
command, usually `forge work <item>` for a fix round. Open the line a finding cites first: if the
code proves the finding wrong, dismiss it with
`forge close <item> --dismiss <n> --because "<file:line> <reason>"`.

## Upgrading a repo

You never edit `forge.toml` by hand. Ask your coding agent to upgrade Forge, or to change any
other setting such as the workers or the test command; it asks you first, with options, then
makes the change in a fix like any other:

1. `forge fix start "Upgrade Forge to vX.Y.Z" --done "forge doctor passes on vX.Y.Z"`.
2. It changes `version` in `forge.toml` to `vX.Y.Z`.
3. It installs that release with the `uv tool install` line above, using `@vX.Y.Z`.
4. `forge sync` rewrites the generated files for the new version.
5. `forge close <fix>`, and you merge.

## Releasing Forge

For Forge's maintainers:

1. In a fix, set `__version__` in `src/forge/__init__.py` to the new version (without the `v`),
   close it and merge it.
2. Tag the merge commit `vX.Y.Z` and push the tag: `git tag vX.Y.Z <merge commit>`, then
   `git push origin vX.Y.Z`. Check the tag's tree matches the default branch with
   `git diff --quiet vX.Y.Z origin/main`.
3. Install from the tag and check that `forge --version` prints `vX.Y.Z`.

What the switch to this Forge removed from the repo, and where to find it, is in
`docs/archive.md`.
