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
- **CI runners:** `runner = "ubuntu-latest"` is the default in `forge.toml`. For an organisation
  using self-hosted Linux runners, use `forge init --runner self-hosted`, or set
  `runner = "self-hosted"` in an existing repo's settings in a fix and run `forge sync`.
  A custom runner label works too. Sync writes that label into both generated jobs in
  `.github/workflows/forge.yml`; new repos get it at init and earlier adopted repos get it after
  upgrading Forge and syncing. The jobs install uv and select Python themselves; Node tests
  install Node from the repo's version file or engines, defaulting to the client stack's Node 22.
  Close and land keep waiting for queued checks, showing minutes observed queued during the
  wait: shared runners may be busy or no runner may match the setting. Only `forge doctor`
  reports a likely missing runner: this repo must show unmet demand dating back at least seven
  days, unassigned queued or failed jobs on the current pull request, and no matching job that
  ran in the last seven days. Expired or cancelled attempts count, even after a fresh retry.
  Make a matching runner available or correct the setting; run `forge sync` only after changing
  the runner setting. Keep the required checks enabled.
- **A repo that copied in the old Forge:** `forge migrate` moves it over in one pull request.
- **Rules for agents:** a repo keeps them in AGENTS.md only, outside Forge's block. Claude Code
  reads AGENTS.md itself, so `forge sync` moves any lines a CLAUDE.md has that AGENTS.md lacks into
  AGENTS.md, in their order, and deletes CLAUDE.md.
- **Every clone:** run `forge sync` once, because the git hooks are installed, not committed.
  Then `forge doctor` checks the tools, the pin, the hooks and CI, and prints a fix for each
  problem it finds. With Codex workers, it also checks the pinned Codex SDK, project trust and
  hook health; `forge doctor --fix` installs the SDK when needed.

## Sharing this machine

Forge gives half this machine's available cores to agents and half to tests, with at least one
core in each budget. Work rounds, plan reads and close reviews across every repo share the agent
line, first come first served; waiting agents say their place. The test lane holds one run at a
time. `forge doctor` shows the split.

`forge board --json` shows both machine-wide lanes and OS load and memory. Only a person can run
`forge stop <item>` to stop all that item's runs in this repo, add `--repo <root>` for another repo,
or use `forge stop --id <id>` for one board entry. The host's stop key asks first. Running process
trees end before a place is freed; waiting runs leave the line and never start. If Forge cannot
verify the recorded process, it refuses and terminates nothing. Workers never run this command.

## Where to start

Run `forge next` whenever you're unsure. It says where things stand in one sentence and prints the
exact next command. The same text appears when a Claude Code or Codex session starts.

### A new client project

Start with FDE discovery: ask about the customer's job, current workaround, its cost and the
evidence. Choose the smallest working prototype that tests the riskiest part of that problem.
A salesperson can lead at first; a developer can take over from `docs/product/DISCOVERY.md` and
the answers in `docs/product/BRIEF.md`. Ask each build-changing question when it first matters,
one at a time, and record the answer and who gave it. If a requested feature does not help test
the problem, say why and offer to note it for after sign-off.

Build and demo the prototype through `forge fix start`, `forge work` and `forge close`. A prototype
fix started before sign-off can exceed the usual fix size and change an interface; it still gets
tests, review and a pull request. Save and confirm specs as the work reveals them. Before sign-off,
`forge next` shows which required answers are still open. Resolve those, then have the whole
prototype and answers strictly reviewed before the customer is asked: write the record with
`forge decision new client-signoff`, leave `approved_via` and `approved_on` empty, and run
`forge decision accept`, which runs the review and either names the gaps or says you can now ask
the customer's named person for sign-off.
The customer's named person approves the demo and the quoted answers; fill in their reply and run
`forge decision accept` again to record it.

Only after accepted client sign-off, add confirmed specs to the roadmap with `forge roadmap add`
and create stories with `forge story new`. This includes stories promoted from fixes. In a client
repo, trying either command early tells you to build and demo the prototype and run `forge next`.
Forge's own repo keeps its existing story flow. For the full sign-off contract, see the
[prototype sign-off spec](specs/prototype-signoff.md) and
[decision 0095](decisions/0095-prototype-before-stories.md).

## Commands

See the [command list](commands.md) for every Forge command.

You never run the hook commands yourself: git, the host hooks and CI call them.

## How a story runs

In a client repo, finish the prototype review and customer sign-off above before starting here.

1. Add the story to the roadmap from its confirmed spec with `forge roadmap add <spec>`.
2. `forge story new <KEY> "<title>"` makes the story's branch, worktree and doc. The doc says what
   changes for the client, why, when it's done, the tasks, any new moving parts and the risks.
3. `forge read <KEY>` runs an independent cold read. Answer every finding (cut, defer or keep),
   amend the doc, then run `forge read <KEY>` again; the same reader reads the whole doc again,
   and this repeats until a round finds nothing.
4. The human approves once, and sees only the top of the story doc: from its title down to
   `## For the builders`, or the whole doc when it has no such heading. In Claude Code, exit
   Plan Mode with that part as the plan; in Codex, show it, then ask the approval question
   `forge next` gives. The approval binds "What changes for you" and "Done when", so tightening
   the details, tasks or notes below needs no new approval. Do this from one main chat for
   stories in every Forge repo this machine has used, including its worktrees. Forge remembers
   those repos automatically. `forge hook approval` records the approval in the story's repo.
5. For each task `forge next` lists as ready: `forge task start <KEY>/<TASK>`, then
   `forge work <KEY>/<TASK>`, then `forge close <KEY>/<TASK>`. Tasks with separate Scopes run at
   the same time, but one machine runs agents on half its available cores (at least one; work rounds, plan reads and
   close reviews, across all its repos): the rest wait in line, first come, first served, and print
   their place when they start waiting and each time it changes; a run that dies frees its place
   once its agent ends.
6. Merge each ready pull request as described below. `forge merge` records the story done in its
   last task's merge, using `--outcome "<outcome>"` or the story's title.

Only the human approves a story and chooses between options. The agent does the rest, including
merging when the repo allows agent merges.

## Workers and conversations

Ask your agent to set `workers = "codex"` in `forge.toml` if you want Codex to build tasks and fixes.
The same file holds a `[models]` table: `[models.build]` for the first task build,
`[models.fix]` for later fix rounds, `[models.lite]` for quick fixes,
`[models.grill.codex]` and `[models.grill.claude]` for cold reads, and `[models.review]` for
Autoreview. Build, fix, lite and grill set a model and reasoning effort; review sets its model.
Building and fixing can also set the subagents' model and effort. Build, fix, lite and review may
instead hold one entry per family, such as `[models.build.codex]` and `[models.build.claude]`. A
single entry counts for its model's family: a gpt model is Codex's, any other is Claude's. When a
kind has no entry for a family, that tool runs on its own settings, except that a review on Claude
uses `[models.grill.claude]`. Ask your agent to change these settings in a fix.

In a client repo, a story task marked User-facing or a fix allowed as "Prototype before sign-off"
uses `[models.design.claude]` even when `workers = "codex"`. Its default is `claude-opus-5-5` at
high effort. If the `claude` command is missing, or Claude fails before changing the checkout,
Forge uses `[models.design.codex]` instead: `gpt-6.1-sol` at high effort by default. Forge prints
and logs the fallback reason. If Claude changed the checkout before failing, Forge reports the
failure without a Codex retry. Other work, including all work in Forge's own repo, keeps its
usual worker and model settings. Set either design table's `model` and `effort` in `forge.toml`
to change that choice.

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
  count toward the limit, and neither do test files or a file whose content is exactly what
  `forge sync` writes. A fix that grows past five code files or touches an interface is
  refused at commit; either promote it with `forge story new <KEY> --from-fix <fix>`, which keeps
  its commits, or have the human allow it with `forge fix allow-large "<reason>"`. In a client repo,
  fixes started before sign-off have the prototype allowance; a fix keeps that allowance after
  sign-off, and a later fix starts without it.

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

Close runs `forge.toml`'s `test` command before the review, and the pull request's `tests` check
runs it again. When that check runs the full suite, ask your agent to set `fast_test` too: a
command close runs instead of `test`, with `{base}` replaced by the merge base with the default
branch, so it runs only the tests related to the changed files plus fast checks (for example
`npx vitest run --changed {base} && npm run lint`). The `tests` check keeps running the full
`test`, and new repos leave `fast_test` unset. `forge doctor` says when it is set.

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

The story's last task records its completion in the same squash merge. Pass
`forge merge <KEY>/<TASK> --outcome "<outcome>"` to say what it achieved, or omit the option to
use its title. This keeps the reviewed commit unchanged and needs no extra pull request or CI
run. The board and `forge next` read the outcome from git. Existing done records stay unchanged.
To correct an outcome later, run `forge story done <KEY> "<outcome>"` on an existing work branch;
the correction ships with that branch's pull request, and the command opens no separate one.

## Upgrading a repo

You never edit `forge.toml` by hand. Ask your coding agent to upgrade Forge, or to change any
other setting such as the workers or the test command; it asks you first, with options, then
makes the change in a fix like any other.

To upgrade, the agent asks which release you want, recommending the newest, then runs
`forge upgrade <release>` (or `forge upgrade` for the newest) from the default branch with
nothing uncommitted. The command starts a fix, changes only `version` in `forge.toml`, installs
that release, has it rewrite Forge's generated files for Claude Code and Codex, and closes the
fix. Close's last line says who merges, as described in Merging a ready item. When the command
refuses, follow its `Next:` line; running it again picks up where it stopped.

A repo pinned to a release older than the command upgrades once with
`uvx --from git+https://github.com/knacklabs/symphony-forge@vX.Y.Z forge upgrade vX.Y.Z`.

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
