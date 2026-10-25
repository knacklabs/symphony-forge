# Forge guide

Forge takes each change to a client's app from an approved story to a merged pull request, and
Claude Code and Codex drive it the same way. This guide covers installing it, its commands, the
two lanes, upgrading and releasing. The engineering rules live on the standards page, which ships
inside Forge and goes into every worker's brief. How Forge behaves is set by its spec,
`docs/specs/lean-forge-v1.md`.

## Install

You need git, the GitHub CLI (`gh`, signed in with `gh auth login`), `uv`, and the agent your
repo uses: Claude Code, Codex, or both for split workers. Either agent can coordinate the work;
with one tool, that tool reads plans; with both, the first cold read uses the other installed tool,
or the coordinating session's `reader` subagent when the other tool is unavailable.
`forge.toml` chooses which one builds tasks and fixes.
Install the release a repo pins (uv brings Python 3.11 or later if you don't have it):

```
uv tool install git+https://github.com/knacklabs/symphony-forge@v1.2.21
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
  A custom runner label works too. Sync writes that label into every generated job in
  `.github/workflows/forge.yml`; new repos get it at init and earlier adopted repos get it after
  upgrading Forge and syncing. The jobs install uv and select Python themselves; Node tests
  install Node from the repo's version file or engines, defaulting to the client stack's Node 22.
  Close and land keep waiting for queued checks, showing minutes observed queued during the
  wait: shared runners may be busy or no runner may match the setting. Only `forge doctor`
  reports a likely missing runner when a current check has been queued at least five minutes
  and no matching job started in its sample of this repo's runs created in the last seven days.
  Doctor reads at most 100 newest runs, skips successful runs, and reads one page of latest
  jobs per remaining run. It does not inspect earlier attempts or older runs.
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

New clients get this flow at init; existing clients get the same guide after upgrade and sync.

Start with FDE discovery: ask about the customer's job, current workaround, its cost and the
evidence. Start with a canvas that shows the app's screens.
A salesperson can lead at first; a developer can take over from `docs/product/DISCOVERY.md` and
the answers in `docs/product/BRIEF.md`. Ask each build-changing question when it first matters,
one at a time, and record the answer and who gave it. If a requested feature does not help test
the problem, say why and offer to note it for after sign-off.

Make each app's design from the brief's `## Summary`, `## Users` and `## Things it keeps track of`,
including all fields and choice-list options. Run impeccable's init when PRODUCT.md is missing.
Use impeccable and emil-design-eng to write the app's theme tokens, type and colours in DESIGN.md.
Make a Claude Design artifact with a shadcn design system and named shadcn components.
On a Codex-only host without artifact tools, use HTML artboards in the repo.
Save artboards and images under `docs/design/prototype/` in a mechanical fix.
Copy `.forge/design/support.js` beside the HTML and run it for a 1440 by 900 PNG per screen.
Write SCREENS.md there, with one `## <screen>` per image, `Image: <file>`,
`Components: <shadcn names>` and `Fields:`. List fields as `- <field>: <type>, required|optional`,
with `, options: <a> | <b>` for choice lists, or use `Fields: none`.
Before sign-off, run impeccable's critique and polish and the emil-design-eng checklist.
Record notes and `Result: passed` in CHECKS.md under `## Critique`, `## Polish` and `## Emil checklist`.
Commit the folder. Record approval with `forge decision new prototype-design` and
`forge decision accept prototype-design --by "<name>"`.

The customer can sign off on the canvas alone. A working prototype needs an FDE request to prove
something the canvas cannot, such as real data or speed. Record it with `forge decision new prototype-build`.
The owner accepts it with `forge decision accept prototype-build --by "<name>"`.
Build and demo the prototype only after that acceptance, through `forge fix start`, `forge work` and `forge close`. A prototype
fix started before sign-off can exceed the usual fix size and change an interface; it still gets
tests, review and a pull request. Save and confirm specs as the work reveals them. Before sign-off,
`forge next` shows which required answers are still open. Its light rounds prove the demo steps,
security and data boundaries, with `[models.light_review]`. Full proof is due at sign-off.
Resolve the answers, then have the whole working
prototype and answers strictly reviewed before the customer is asked: write the record with
`forge decision new client-signoff`, leave `approved_via` and `approved_on` empty, and run
`forge decision accept`, which runs the review and either names the gaps or says you can now ask
the customer's named person for sign-off.
The customer's named person approves the canvas or requested demo and the quoted answers. Set `approved_via` to
`email`, `call` or `chat` and `approved_on` to the reply date. Run `forge decision accept` again
to record it. Put the folder and tree id under `## Signed design`, demo outcomes and their tests
under `## Proof` for a working build, and settled choices under `## Decisions`.

Each sign-off checks the design records and the brief's nonempty `## Things it keeps track of`.
Its completeness check compares SCREENS.md and the images against the brief's Summary, Users,
Things it keeps track of and Key flows. Missing screens, fields, choice-list options or flows hold sign-off.
The check uses `claude-opus-5-5` at high, independent of `[models.design]`.
Without Claude it uses `gpt-6.1-sol` at high and reports the fallback.
Fix gaps and approve the changed canvas again before another sign-off attempt.
A canvas-only sign-off needs no build or code review. A working prototype gets one whole-product review.
Forge reuses each passed result while what it checked stays unchanged.

Only after accepted client sign-off, create stories with `forge story new`. Specs are optional;
use `forge roadmap add` when planning from a confirmed spec. Promotion from a fix keeps its
existing route: its roadmap entry must already be committed in the fix's branch. In a client
repo, trying either command early tells you to build and demo the prototype and run `forge next`.
Every new story copies the sign-off's Signed design, Proof and Decisions into
`## Proven by the prototype`. The plan and cold read treat this as settled evidence and cover
only new work or production risks. Start from the signed canvas or a newer design approved with the plan.
Forge's own repo keeps its existing story flow. For the full sign-off contract, see the
[prototype sign-off spec](specs/prototype-signoff.md) and
[decision 0095](decisions/0095-prototype-before-stories.md).

## Commands

See the [command list](commands.md) for every Forge command.

You never run the hook commands yourself: git, the host hooks and CI call them.

`forge board` opens the board as a live page on this computer. It serves the page on 127.0.0.1
with a per-run token in the address, so only this computer can open it, and the page refreshes by
itself when the work changes. Press Ctrl-C to stop it. `forge board --json` prints the current
work as JSON, and `--out <path>` writes every item's facts, finished ones included, as JSON.

## How a story runs

In a client repo, finish the canvas checks and customer sign-off above before starting here.
A working prototype also needs its strict whole-product review.

1. Start from the problem you want to solve. A spec is optional; if using a confirmed spec,
   add its stories with `forge roadmap add <spec>` as before.
2. `forge story new <KEY> "<title>"` makes the story's branch, worktree and doc. The doc says what
   changes for the client, why, when it's done, the tasks, any new moving parts and the risks.
   Its own branch adds a missing roadmap entry. The title seeds Why; write the problem,
   today's workaround and its cost there, without a separate spec read or confirmation.
   Before the cold read, design each added screen or changed flow with the process above.
   Save the artboards, images, SCREENS.md and CHECKS.md in `docs/design/<KEY>/`.
   End `## What changes for you` with `Design: docs/design/<KEY>/ (<tree id>)`.
   Get the tree id with `git rev-parse HEAD:docs/design/<KEY>` after committing the folder.
   One plan approval covers that exact design. A folder change needs a new tree id and approval.
   Small changes to existing screens that add no screen and change no flow use `Design: none (<why>)`.
   Backend-only stories need no canvas. Earlier approved stories keep working.
   The build applies DESIGN.md to the starter and includes every listed component and field from SCREENS.md.
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
   `forge work <KEY>/<TASK>`. Tasks with separate Scopes run at
   the same time, but one machine runs agents on half its available cores (at least one; work rounds, plan reads and
   close reviews, across all its repos): the rest wait in line, first come, first served, and print
   their place when they start waiting and each time it changes; a run that dies frees its place
   once its agent ends.
6. Run `forge land --all` in the background in place of closing and merging by hand. It takes
   every task and fix in close, starts them oldest first, several at a time up to the machine's
   agent places, and merges each one when it passes, where the repo allows agent merges. A change
   not yet ready that changes a file an older change in the run also changes waits for it. Only
   one run works in a repo at a time. A change that needs a worker or you stops alone; the run
   ends with `Merged (n): ... · Ready to merge (n): ... · Needs you (n): ...` and each stopped
   change's reason and next step. A failed check whose log names none of the change's files
   runs again once. Where a human merges, the run merges nothing and lists the ready changes
   oldest first with their links, in the order to merge them. The last task's merge records the
   story done, using its title.

Only the human approves a story and chooses between options. The agent does the rest, including
merging when the repo allows agent merges.

## Workers and conversations

Ask your agent to run everything in Claude, run everything in Codex, or use both. In a settings
fix it sets `tools = "claude"` with `workers = "claude"`, `tools = "codex"` with
`workers = "codex"`, or `tools = "both"`. Both is the default when the setting is absent;
with one tool `workers` is ignored, including for design work. Upgrade Forge before adding
`tools` to an older repo. The planning, approval, build, review, CI and merge process is the same
with any choice. A round on the coordinating session's tool runs as its background subagent;
the other tool uses its kit. Reviews use the repo's tool through Autoreview's own default model
and effort; with both they use Codex when installed, otherwise Claude. Existing review model
entries are ignored and doctor shows a note; upgrading preserves the repo's settings.

For a native plan read, `forge read <target>` hands out the `reader` role, the plan's checkout
and its prompt. Run that background subagent in your session, then record its final message
with `forge handback <target> --subagent <id> --text "<message>"`. Its lock and machine place
stay held until handback. Forge checks for changed files and records the usual cold-read notes.

The same file holds a `[models]` table: `[models.build]` for the first task build,
`[models.fix]` for later fix rounds, `[models.lite]` for a fix's first build round,
`[models.explore]` for the explorer role on both hosts and quick read-only questions,
`[models.grill.codex]` and `[models.grill.claude]` for cold reads.
Build, fix, lite, explore and grill set a model and reasoning effort.
Build, fix, lite and explore can also set the subagents' model and effort. Build, fix, lite and explore may
instead hold one entry per family, such as `[models.build.codex]` and `[models.build.claude]`. A
single entry counts for its model's family: a gpt model is Codex's, any other is Claude's. When a
kind has no Claude implementation entry, Forge uses `claude-sonnet-5-5` at xhigh effort.
Claude plan reads default to `claude-opus-5-5` at high effort, including when Claude is the only
installed tool. Claude planner and architect roles use that plan-read entry; debugger,
security and performance use Opus 5.5 at high effort. Codex build, fix and lite workers with
no entry use Forge's `gpt-6.1-sol` at medium effort; Codex design uses its design default.
Ask your agent to change these settings in a fix.

`forge init` writes Sonnet at xhigh for Claude build, fix, lite and design (frontend included),
and Opus at high for Claude grill. Existing model entries stay unchanged on
upgrade. To opt in, set `model` to `"claude-sonnet-5-5"` and `effort` to `"xhigh"` in those
four implementation entries, and `"claude-opus-5-5"` at `"high"` in grill. A missing implementation entry
can be added before the first table with one line per kind, replacing `build` below:
`models.build.claude = { model = "claude-sonnet-5-5", effort = "xhigh" }`.
For plan reads, use this line:
`models.grill.claude = { model = "claude-opus-5-5", effort = "high" }`.
Move a single build, fix or lite entry to its family's table first. Run `forge sync` after
changing settings to refresh subagent roles.

Every normal, light and prototype sign-off review runs through the external Autoreview
program on the repo's tool: Claude with `tools = "claude"`, Codex with `tools = "codex"`.
With `tools = "both"`, reviews use Codex when installed and Claude otherwise. Autoreview chooses its own
default model and effort; Forge passes neither. Legacy `[models.review]` entries stay in
existing settings but no longer override Autoreview's defaults.

A story task marked User-facing or a client fix allowed as "Prototype before sign-off"
uses its selected tool's design entry: `[models.design.codex]` on Codex and
`[models.design.claude]` on Claude. Claude's default is
`claude-sonnet-5-5` at xhigh effort. With `tools = "both"` and `workers = "split"`, the
fallback applies only to Claude design rounds run through its kit. If the `claude` command
is missing, or Claude fails before changing the checkout,
Forge uses `[models.design.codex]` instead: `gpt-6.1-sol` at high effort by default. Forge prints
and logs the fallback reason. If Claude changed the checkout before failing, Forge reports the
failure without a Codex retry. When Claude Code coordinates the round, design work runs as
its native `frontend` subagent; a failed native round gets no automatic Codex retry.
With one tool selected, Forge reports the failure without a Codex retry.
Split routing also applies to User-facing story tasks in
Forge's own repo. Other work keeps its usual worker and model settings. Set either design table's `model` and `effort` in `forge.toml`
to change that choice.

Forge names task conversations `Build · <story>/<task> · <task name>` and later turns
`Fix · <story>/<task> · <task name>`. Quick fixes use `Lite · <fix name> · <why>` and cold reads
use `Grill · <story or spec> · <name>`. A later turn continues the item's conversation when it
can. For conversations you start yourself, names such as `Review`, `Explore` and `Debug` make
them easier to find in the Codex app.

If another program holds the earlier Codex conversation, Forge retries once. If it is still
held, work starts a new conversation with the whole brief and says why in one line.
New repos get this behavior at init. Existing repos get it on upgrade.

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

For a quick read-only question about this checkout, hand it to the session's `explorer`
subagent role. It uses the explore entry in `forge.toml`; no separate Forge command is needed.

New repos get explore on Claude with `claude-haiku-5-5` at high effort and on Codex with the
initial lite settings. Upgrading and syncing an existing repo preserves its settings: without
explore, its read-only work keeps using lite. Add explore entries in a fix and sync to separate
read-only work from implementation.

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

`forge close <item>` fetches the default branch. It merges that branch in only when a trial merge
finds a clash, or GitHub reports the pull request conflicting or behind under its up-to-date rule.
An unrelated change on the default branch adds no merge to the pull request. Close pushes and opens or
updates the pull request, runs the review until no serious finding is left, waits for the checks
`forge.toml` names (`tests` and `forge-pr-check` by default), and marks the item ready. While the
review is blocked the pull request is a draft, and close marks it ready for review once the review
is clean and the checks are green. When it stops, it prints why and the next
command, usually `forge work <item>` for a fix round. Open the line a finding cites first: if the
code proves the finding wrong, dismiss it with
`forge close <item> --dismiss <n> --because "<file:line> <reason>"`.

Close checks GitHub's clash state at every look, even when all checks are green. If this head
clashes, close stops and says to run close again to bring the default branch in. It waits when
GitHub has not yet determined whether this head can merge.

If GitHub refuses a pull request body update, close stops after one attempt, including during a
history retry. Wait for a rate limit to reset, or fix the reported problem, then retry the command.

Each change's related tests, lint and type checks run once, in the repo's chosen test place.
In a local-test repo, set `fast_test` in `forge.toml` when close needs a narrower command; it
runs instead of `test`, with `{base}` replaced by the merge base with the default branch (for
example `npx vitest run --changed {base} && npm run lint`). In a CI-test repo, the pull request's
`tests` check runs the related tests and close waits for it. The nightly full run covers the rest.
New repos leave `fast_test` unset. `forge doctor` says when it is set.
The generated `forge.yml` runs one `tests` job with `forge test --change`. Repos with a direct
pytest command and pytest-split keep their existing six-group job, which runs `test`.
The required `tests` check passes only when every job passes.
New repos get this at init and earlier adopted repos after upgrading Forge and syncing; the
required check keeps its `tests` name, so branch protection doesn't change.
In CI mode, `forge.yml` also runs `forge test --full` once a day on the default branch and supports
`workflow_dispatch`. Start a full run with `gh workflow run forge.yml --ref <default>`. In local
mode, `forge next` says when the daily run is due; run `forge test --full` in the main checkout
when the machine is quiet. A green full run on the latest default-branch commit gates release tags
and client sign-off. Everyday merges do not wait for it.
On a `windows-*` runner, the generated related-test job wraps `forge test --change` in PowerShell
and retries it once after a failure. The command runs the configured test command with the same
shell as a local close on Windows. Use `pwsh -File "<path>"` to run a PowerShell script. A second
failure fails the check; Linux and Mac run it once, and the trusted `forge-pr-check` gate keeps
its command. New clients get this at init; existing clients get it after upgrading Forge and
running `forge sync`. Forge's own Windows full-suite job instead reruns each failed pytest test
once and gives the known slow tests longer timeouts on Windows.
Close runs the full related-test selection, even when it covers more than a third of the Python
test files. Shared test inputs select every test. Bare
`forge test` keeps worker runs bounded: when the pytest selection would cover more than a third
of the repo's Python test files, it runs only the part's Tests column or the fix's touched test
files, plus `always_test`, and says "The nightly full run covers the rest." With no named tests
it runs only `always_test`. An explicit `forge test --pytest <base>` keeps the full selection.
New repos get this bound from init; existing repos get it on upgrade.

Other workflows can use the same rule. Init and `forge sync` ship `.forge/records-only`.
After checkout, add this one step: `- {id: forge-records, uses: ./.forge/records-only}`.
Give the job `contents: read` and `actions: read` permissions, and fetch the full history.
The runner needs Python, Bash and the GitHub CLI, as GitHub-hosted runners provide.
Add the condition below to each later step that can skip the records commit:

```yaml
permissions:
  contents: read
  actions: read
steps:
  - uses: actions/checkout@v7
    with:
      fetch-depth: 0
  - {id: forge-records, uses: ./.forge/records-only}
  - if: steps.forge-records.outputs.records_only != 'true'
    run: your-build-command
```

The output is `records_only=true` only for a push or pull request whose parent passed this
same workflow. The step uses Forge's existing close-record rule. Code changes, documentation
changes, a failed parent run or missing proof produce `false`, so the workflow runs normally.
For pull requests, the parent must also include the current base and its run must cover that base.
Each job that uses the step skips only its guarded steps.

## Parts that build on reviewed work

New and upgraded repos use `stack = "on"` by default, with no settings change. A part can start
on one reviewed, unmerged part when its After list or Scope makes it wait for that part.
The base must use the same Forge release and must start from the default branch.
A part that builds on another can become a base after Forge merges the lower part and close
moves it onto that merged code and reviews it again. Set `stack = "off"` to make new parts
wait for merges. Parts that already started on another part keep their base.

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

If GitHub reports a clash during the check wait, or refuses the merge as behind or conflicting,
Forge runs close and retries the merge once. A pull request that can merge keeps its current head.

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

Before an upgrade, wait until no Forge runs are in progress anywhere on the machine.
Let workers, plan reads, tests and close finish first. An install during a close can mix two releases.

To upgrade, the agent asks which release you want, recommending the newest, then runs
`forge upgrade <release>` (or `forge upgrade` for the newest) from the default branch with
nothing uncommitted. The command starts a fix, changes only `version` in `forge.toml`, installs
that release, has it rewrite Forge's generated files for Claude Code and Codex, and closes the
fix. Close's last line says who merges, as described in Merging a ready item. When the command
refuses, follow its `Next:` line; running it again picks up where it stopped.
If the machine's lanes still have runs, the command names them and asks you to wait.

A repo pinned to a release older than the command upgrades once with
`uvx --from git+https://github.com/knacklabs/symphony-forge@vX.Y.Z forge upgrade vX.Y.Z`.

## Releasing Forge

For Forge's maintainers:

1. In a fix, set `__version__` in `src/forge/__init__.py` to the new version (without the `v`),
   close it and merge it.
2. Start the full test run with `gh workflow run forge.yml --ref main` and confirm it is green.
   Start the platform run with `gh workflow run forge-next.yml --ref main` and confirm it is green
   on Linux, Mac and Windows before tagging. Pull requests and merges to main run only the Linux
   test groups; they do not prove the other platforms ready for release.
3. Tag the merge commit `vX.Y.Z` and push the tag: `git tag vX.Y.Z <merge commit>`, then
   `git push origin vX.Y.Z`. Check the tag's tree matches the default branch with
   `git diff --quiet vX.Y.Z origin/main`.
   The tag push runs the full matrix again; confirm that run is green too.
4. Install from the tag and check that `forge --version` prints `vX.Y.Z`.

What the switch to this Forge removed from the repo, and where to find it, is in
`docs/archive.md`.

## Remove the Claude Codex plugin

The new Forge uses Codex directly. If you installed the old Claude Codex plugin, remove its
installation and marketplace from your own machine:

```
claude plugin uninstall codex@openai-codex
claude plugin marketplace remove openai-codex
```
