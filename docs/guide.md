# Forge guide

Forge takes each change to a client's app from an approved story to a merged pull request, and
Claude Code and Codex drive it the same way. This guide covers installing it, its commands, the
two lanes, upgrading and releasing. The engineering rules live on the standards page, which ships
inside Forge and goes into every worker's brief. How Forge behaves is set by its spec,
`docs/specs/lean-forge-v1.md`.

## Install

You need git, the GitHub CLI (`gh`, signed in with `gh auth login`), `uv`, Claude Code and Codex.
Either agent can coordinate the work; the first cold read of a story or spec runs on the other one.
`forge.toml` chooses which one builds tasks and fixes.
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
  problem it finds. With Codex workers, it also checks the pinned Codex SDK, project trust and
  hook health; `forge doctor --fix` installs the SDK when needed.

## Where to start

Run `forge next` whenever you're unsure. It says where things stand in one sentence and prints the
exact next command. The same text appears when a Claude Code or Codex session starts.

## Commands

See the [command list](commands.md) for every Forge command.

You never run the hook commands yourself: git, the host hooks and CI call them.

## How a story runs

1. Add the story to the roadmap from its confirmed spec with `forge roadmap add <spec>`.
2. `forge story new <KEY> "<title>"` makes the story's branch, worktree and doc. The doc says what
   changes for the client, why, when it's done, the tasks, any new moving parts and the risks.
3. `forge read <KEY>` runs one independent cold read. Answer every finding (cut, defer or keep),
   amend the doc once, then run `forge read <KEY> --amended`.
4. The human approves once. In Claude Code, exit Plan Mode with the story doc as the plan; in Codex,
   ask the approval question `forge next` gives. Do this from one main chat for stories in
   every Forge repo this machine has used, including its worktrees. Forge remembers those repos
   automatically. `forge hook approval` records the approval in the story's repo.
5. For each task `forge next` lists as ready: `forge task start <KEY>/<TASK>`, then
   `forge work <KEY>/<TASK>`, then `forge close <KEY>/<TASK>`. Tasks with separate Scopes run at
   the same time.
6. Merge each ready pull request as described below. After the last one, record the outcome with
   `forge story done <KEY> "<outcome>"`.

Only the human approves a story and chooses between options. The agent does the rest, including
merging when the repo allows agent merges.

## Workers and conversations

Ask your agent to set `workers = "codex"` in `forge.toml` if you want Codex to build tasks and fixes.
The same file holds a `[models]` table: `[models.build]` for the first task build,
`[models.fix]` for later fix rounds, `[models.lite]` for quick fixes,
`[models.grill.codex]` and `[models.grill.claude]` for cold reads, and `[models.review]` for
Autoreview. Build, fix, lite and grill set a model and reasoning effort; review sets its model.
Building and fixing can also set the subagents' model and effort. Ask your agent to change these
settings in a fix.

Forge names task conversations `Build · <story>/<task> · <task name>` and later turns
`Fix · <story>/<task> · <task name>`. Quick fixes use `Lite · <fix name> · <why>` and cold reads
use `Grill · <story or spec> · <name>`. A later turn continues the item's conversation when it
can. For conversations you start yourself, names such as `Review`, `Explore` and `Debug` make
them easier to find in the Codex app.

### Notes, worker questions and quick answers

Use `forge work <item> --note "<text>"` when one sentence of guidance would help the worker in
this round. Forge puts it under "From the coordinator" in the brief and records it in the turn
log. An empty note is refused. Repeat the note if a later round needs it; the flag guides only
the current round and never extends the task or fix's Scope.

When a worker needs a decision it cannot make, its final message ends with a `Question:`
paragraph. Forge prints the question and waits for `forge work <item> --note "<answer>"`.
Without an answer, another `forge work <item>` and `forge close <item>` refuse. Forge sends the
question and answer in the answering brief and resumes the worker's conversation when possible.
If that round fails or is interrupted, answer again with `--note`; the question remains open.

Use `forge ask "<question>"` for a quick read-only look at this checkout without starting a
fix. It uses `[models.lite]` in `forge.toml` by default; pass `--model <model>` or
`--effort <effort>` to override either setting for the question. Forge prints the answer and
keeps its records under `.git/forge/`. The Codex conversation is temporary and does not appear
in the chat list. If a tracked or untracked file changes during the turn, Forge discards the
answer and tells you to check `git status` before asking again.

## The two lanes

- **Story:** any change that touches an interface or more than five code files.
- **Fix:** a small change, started with `forge fix start "<why>" --done "<done when>"`. Specs,
  decisions, the roadmap and discovery notes always ship as fixes, since planning documents don't
  count toward the limit. A fix that grows past five code files or touches an interface is
  refused at commit; either promote it with `forge story new <KEY> --from-fix <fix>`, which keeps
  its commits, or have the human allow it with `forge fix allow-large "<reason>"`.

Planning records follow the same lane: `forge spec save <slug>`, a cold read with
`forge read <slug>`, then `forge spec confirm <slug> --by "<name>"` once the human confirms in
chat. Every spec needs a `## Success measure` with `- Metric:`, `- Baseline:`, `- Target:` and
`- Check date: YYYY-MM-DD` filled in, or save and confirm refuse it. After the check date, record
what you measured with `forge spec measure <slug> --result "<text>"` in a fix. Decisions use `forge decision new <slug>` and `forge decision accept <slug> --by "<name>"`.

## Closing

`forge close <item>` follows the close rule: it merges the default branch in, pushes and opens or
updates the pull request, runs the review until no serious finding is left, waits for the checks
`forge.toml` names (`tests` and `forge-pr-check` by default), and marks the item ready. While the
review is blocked the pull request is a draft, and close marks it ready for review once the review
is clean and the checks are green. When it stops, it prints why and the next
command, usually `forge work <item>` for a fix round. Open the line a finding cites first: if the
code proves the finding wrong, dismiss it with
`forge close <item> --dismiss <n> --because "<file:line> <reason>"`.

## Merging a ready item

The human merges by default: omitting `merge` from `forge.toml` is the same as
`merge = "human"`. Ask your agent to set `merge = "agent"` in a fix if you want it to merge ready
pull requests. Only the setting on the default branch counts. A change to the setting on an item
branch cannot grant itself permission, and turning it off on the default branch takes effect at
once. `forge close` and `forge next` tell the agent when to run `forge merge <item>`.

With agent merging enabled, Forge checks that close recorded a clean, ready review, the pull
request is still open against the default branch at the recorded commit, and every check named by
the default branch's `forge.toml` is green. It then squash-merges with the pull request's title,
deletes the remote branch, fetches the default branch, and removes the item's local branch and
worktree. It leaves a worktree with uncommitted changes in place and says so. Forge archives the
item's recorded Codex conversations; Codex can restore archived chats. The agent merges only
through `forge merge <item>`; the hook still refuses a raw `gh pr merge` command. When agent
merging is off, a human merges the ready pull request.

## Upgrading a repo

You never edit `forge.toml` by hand. Ask your coding agent to upgrade Forge, or to change any
other setting such as the workers or the test command; it asks you first, with options, then
makes the change in a fix like any other:

1. `forge fix start "Upgrade Forge to vX.Y.Z" --done "forge doctor passes on vX.Y.Z"`.
2. It changes `version` in `forge.toml` to `vX.Y.Z`.
3. It installs that release with the `uv tool install` line above, using `@vX.Y.Z`.
4. `forge sync` rewrites the generated files for the new version.
5. `forge close <fix>`, then it is merged as described in Merging a ready item.

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

## Remove the Claude Codex plugin

The new Forge uses Codex directly. If you installed the old Claude Codex plugin, remove its
installation and marketplace from your own machine:

```
claude plugin uninstall codex@openai-codex
claude plugin marketplace remove openai-codex
```
