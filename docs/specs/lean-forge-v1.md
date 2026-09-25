---
slug: lean-forge-v1
title: Forge v1: one small tool takes a story from approval to a merged pull request
status: draft
saved: 2026-09-25T14:12:12+00:00
---

# Forge v1: one small tool takes a story from approval to a merged pull request

## Why

Forge has grown to about 47,000 lines of scripts and as many again in tests. Most of it is
bookkeeping that checks other bookkeeping. On 2026-09-25 four finished tasks could not close
because of Forge's own machinery. 11 of the last 25 merged pull requests fixed Forge instead of the
product. Every client also carries its own copy of all of it. The owner decided to rebuild Forge
from scratch in this repo, switch over and delete the old tree (the decision "Forge is rebuilt lean
in the same repo, then switched over"). The rule for closing a task stays as confirmed in
[close-on-green-ci-and-clean-review](close-on-green-ci-and-clean-review.md).

## Principles

Each principle has a check; the check is an acceptance criterion, a CI check or a review instruction.

1. Every artifact serves a client-visible change or is cut. Check: every story doc starts with "What changes for you".
2. One home per fact: history in git, review and tests in the PR, current state in `.factory`. Check: no command writes a fact git or GitHub already holds.
3. Gates check outcomes, never rituals: refuse only on a red test, a P0/P1 finding or a missing approval. Check: every refusal names the real problem and the next action.
4. Fail loud, early, once: enforce at the command or commit, never silently. Check: a behaviour test for every refusal message.
5. No rule without a test; no test without a rule. Check: the suite maps one test to one rule and tests no internal record format.
6. Forge shrinks over time: every story removes at least as much process as it adds. Check: no module over 1,200 lines, a fixed ceiling on `forge` commands, refactor ratchet in CI.
7. Adapt to third parties, never mirror them (Autoreview, Codex, Claude, GitHub): read only used fields, tolerate new ones, pin versions. Check: one boundary contract test per external tool.
8. The agent does the work; the human decides (approve a story, choose between options, merge). Check: human touches per story are counted; target three or fewer.
9. Same result from any agent: logic in `forge` commands and git, thin host adapters. Check: the same behaviour tests run through both adapters.
10. Slow is a bug: close in minutes, CI under 5 minutes. Check: time per step is recorded and shown on the board; over-budget steps get fixes.
11. Plain English wherever a human looks: no IDs, hashes or jargon on the board, in PR summaries or in questions. Check: reviewed on board and PR text.
12. Reversible by default: every change and every migration is one PR; rollback is a revert. Check: no command changes a client repo outside a branch and PR.
13. Measure the factory: task cycle time, human touches per story, share of PRs fixing Forge instead of the product. Check: these three are the rebuild's success measure.

## Behaviour

### Where it lives and how it is installed

- The new code lives in `src/forge/`, one Python package with no third-party runtime dependencies
  (Python 3.11 or later, standard library only). The repo root gets a `pyproject.toml` that
  declares the `forge` console command. Behaviour tests live in `tests/`. The old `factory/` tree
  and the old `./forge` launcher stay untouched until the switch.
- A release is a git tag `vX.Y.Z` on the public repo. Install or upgrade with
  `uv tool install git+https://github.com/knacklabs/symphony-forge@vX.Y.Z`. `forge version` prints
  the installed version.
- The standards page (`docs/standards.md`) is shipped inside the package, so every worker brief
  can include it in any repo.

### Configuration: `forge.toml`

Each repo that uses Forge has one committed `forge.toml` at its root:

```toml
version = "v1.0.0"      # the Forge release this repo runs; upgrading = bump this, install, forge sync
workers = "claude"      # claude | codex (codex arrives with the warm-threads story)
model = "opus"          # the worker model
checks = ["tests"]      # the CI checks close waits for, by name
interfaces = []         # extra path globs that count as interfaces for the fix lane
```

Every command that changes state refuses when the installed Forge differs from `version`, and
prints the exact `uv tool install` line. `forge version`, `forge doctor` and `forge next` still run.

### Commands

v1 has exactly these commands, at most 20:

| Command | What it does |
|---|---|
| `forge init` | Sets up a new repo: `forge.toml`, the docs skeleton (brief, discovery, specs, decisions, roadmap), then `forge sync`. |
| `forge sync` | Writes the generated adapter files and git hooks for the pinned version. |
| `forge doctor` | Checks tools, versions, hooks, adapter drift and the named CI checks. Prints one row per problem, each with a fix. |
| `forge migrate` | Moves a client repo from the copied-in Forge to v1 in one pull request. |
| `forge next` | Says where things stand and gives the exact next command(s). |
| `forge board` | Writes and opens the plain-English board page. |
| `forge story new <KEY> "<title>" [--from-fix <fix>]` | Starts a story branch, worktree and story doc (or promotes a fix). |
| `forge story read <KEY>` | Runs the one cold read of the story doc. |
| `forge task start <KEY>/<TASK>` | Starts a task in its own branch and worktree. |
| `forge fix start "<why>"` | Starts a fix in its own branch and worktree, with a one-line reason. |
| `forge work <item>` | Runs the configured worker on a task or fix: first build, or a fix round. |
| `forge close <item> [--dismiss <n> --because "<file:line> <reason>"]` | Closes a task or fix by the close rule. |
| `forge spec save <slug>` / `forge spec confirm <slug> --by "<name>"` | Saves a spec as a draft, then marks it confirmed after the human confirms in chat. |
| `forge decision new <slug>` / `forge decision accept <slug> --by "<name>"` | Writes a decision record, then accepts it after the human confirms in chat. |
| `forge hook <name>` | Internal: the one entry point that git hooks, host hooks and CI call. |
| `forge version` | Prints the installed version. |

### The story doc

- One file per story: `plans/<KEY>.md`. Its sections, in this order:

  ```markdown
  # <plain-English title>

  ## What changes for you
  ## Why
  ## Done when
  ## Tasks
  | ID | Name | What it delivers | After | User-facing |

  New moving parts: none
  ## Notes
  ```

- "What changes for you" must come first.
- "Done when" is a list; each item becomes an instruction to the reviewer.
- "Tasks" is one table:
  - IDs are unique and made of capital letters, digits and hyphens.
  - "Name" is a short plain-English name, which the board shows.
  - "After" lists IDs from the same table, with no cycles.
  - "User-facing" is yes or no.
- A `New moving parts:` line right after the table is required. It is either `none`, or lists each
  new dependency, service, datastore, queue, background job or abstraction layer with the Done-when
  item that needs it. It goes into every worker brief and every set of review instructions.
- "Notes" is optional: technical notes for workers and reviewers.
- There are no task plans and no task grills.
- `forge story new` checks that the key is on the roadmap (`plans/roadmap.json`). It creates the
  `story/<KEY>` branch in its own worktree and writes the template.
- The story branch is never opened as a pull request. The doc, its read notes and its state reach
  the default branch with the story's first task pull request, so a story adds no extra merge.

### Cold read and approval

- `forge story read <KEY>` runs the worker backend once, read-only, with a fixed cold-read
  prompt. It writes the findings to `plans/<KEY>.read.md` and records who read the doc, when, and
  the doc's git hash as it was read.
- The cold read also asks "is this simple enough?":
  - Each task maps to the Done-when items it delivers. Each Done-when item maps to the spec's
    behaviour or success measure. Anything that maps to nothing gets `Cut or defer: <item>`.
  - Each entry in `New moving parts` needs its Done-when item and a reason the lower rungs won't do
    (reuse, the standard library, the platform, an installed dependency). If not:
    `Simpler: <part> → <lower rung>`.
  - The reader names a smaller shape when one exists, and flags a one-way step (deleting data, a
    destructive migration, a new vendor) that isn't listed under risks.
  - It never proposes dropping validation, security, data-loss protection or accessibility.
- The coordinator then writes a disposition under each finding and amends the doc once:
  - "cut" edits the doc;
  - "defer" moves the item to the spec's Out of scope;
  - "keep" gives a one-line reason.

  Only a genuine trade-off goes to the human, as a question with options. There is no second read.
- The approval covers the text of "What changes for you" and "Done when". Changing either one
  after approval needs a new approval. Changing "Why", "Tasks" or "Notes" does not.
- On Claude Code, the coordinator shows the doc through Plan Mode (`ExitPlanMode` with the doc's
  exact text). The approval hook records an approval when the approved text equals a story doc in
  one of the repo's worktrees.
- On Codex, the coordinator shows the doc in chat, then asks "Approve this plan?" through
  `request_user_input`. The question id is `approve_<KEY>_<short hash>` (`forge next` prints it),
  and the choices are "Approve" and "Request changes". The hook records the approval when the
  answer is "Approve" and the hash matches the current doc.
- The hook records nothing if there is no cold read, the text or hash doesn't match, the tool call
  failed, or the answer is not "Approve". `forge next` then still says "waiting for approval" and
  why.
- **Client sign-off.** In a client repo, approval is refused (nothing is recorded) until the
  client's sign-off is recorded: an accepted decision whose slug ends in `client-signoff`.
  `forge next` names the sign-off step. The Forge source repo (it contains `src/forge/`) is exempt,
  as today.
- The approval hook also counts every other question the human answers while working in a story's
  worktree. Those counts are the "human touches" measure.

### Tasks and workers

- `forge task start <KEY>/<TASK>` refuses if the story isn't approved, or if a task this one
  depends on isn't merged yet. Otherwise it creates `task/<KEY>-<TASK>` in a new worktree next to
  the repo, writes the task's state file, commits it on the task branch and prints the path.
- A task branch starts from the story branch while the story doc isn't on the default branch yet,
  and from the default branch after that. The doc then lands with whichever task pull request
  merges first; in the others its content is identical, so git merges it without conflict.
- `forge next` lists every task whose dependencies are ready, so they can start in parallel.
- `forge work <item>` builds a brief and runs the worker in the item's worktree. The brief holds:
  - the story doc's "What changes for you", "Why" and "Done when", this task's row and "Notes";
  - the standards page;
  - in a fix round, the open serious findings from the pull request and the names and log tails of
    failing checks.
- With `workers = "claude"`, the worker runs Claude Code headless (`claude -p`) in the worktree
  with the configured model. It may edit files and run commands there, and it commits its own work.
- With `workers = "codex"`, v1 refuses and says Codex workers come with the warm-threads story.
- Output goes to the terminal and to a log under `.git/forge/`, which is never committed.
- For a user-facing task, the brief also asks the worker to write a short functional check in the
  pull request: what was exercised, and what was seen.

### The fix lane (one way to ship)

- `forge fix start "<why>"` creates `fix/<slug>` in its own worktree. It writes the fix's state file
  with the one-line reason and the commit it started from.
- A fix closes exactly like a task, with `forge close`.
- **Promote rule.** A fix must become a story when it touches:
  - more than 5 code files, counted against its starting commit (Markdown files, `.factory/` and
    `plans/` don't count); or
  - any file under `docs/decisions/` or `docs/specs/`; or
  - a path listed in `interfaces`.
- The git hooks refuse such a commit or push, and name `forge story new <KEY> --from-fix <fix>`.
  That command turns the fix branch into the story's first task branch and keeps its commits. The
  fix's reason becomes the draft "Why".
- The human can overrule the lane in one word; the coordinator then promotes the fix, or keeps it
  under the limit.

### Close

- `forge close <item>` follows the close rule spec: push, open or update the pull request, run the
  Autoreview loop, wait for the checks named in `checks`, then mark the item done.
- Autoreview is run with today's read-only worktree launcher at a pinned helper version. Forge
  reads only its `findings` and `review_status`.
- A serious finding (P0 or P1), or a red, missing or pending check, stops close. Close then prints
  the problem and the next command (`forge work <item>`, or wait).
- The coordinator can dismiss a finding with `--dismiss`, citing the line that proves it wrong
  (host triage, decision 0075).
- For a user-facing task, the review instructions report a missing or hollow functional check as
  a P1 "Not done" finding.
- **Simpler rule.** The review instructions include the story's `New moving parts` line and this
  rule. Complexity the diff adds that no Done-when item needs is a defect, not a style preference.
  - It is a P2 `Simpler: <what to cut> → <what replaces it>`.
  - It becomes P1 when the diff adds a new dependency, service, datastore, queue, background job or
    abstraction layer that the `New moving parts` line doesn't name.
  - Structure the standards page requires for a concern the diff really has (a provider for an
    external service, typed request and response types for an endpoint) is not a finding.
  - Validation, authorization, secrets handling, data-loss protection and accessibility are never
    "simpler"; a missing one is its own P1.
  - Complexity the diff didn't add is an advisory P3 `Simpler (existing):`.
- The reviewed commit, product tree and status go in the item's state file. The findings,
  dismissals and advisory P2/P3 list go in the pull request body, in one Forge block that close
  replaces on each run.
- Close gives every pull request a plain-English title and makes the first line of its body a
  one-line plain-English summary of what changed for the reader. For example, the title "Board
  shows each story in plain English" with the summary "Anyone can now open one page and see where
  each piece of work stands." Squash merges keep both, and the board's timeline is built from them.
- A human merges; the agent never merges.

### Client apps are built simple

The apps Forge builds follow the 11 client-app principles on the standards page: problem first,
smallest slice, only what Done-when needs, fewest moving parts, delete before adding, one home per
fact, the simplest UI, measure then check back, reversible, runnable by a non-technical client, and
security and accessibility never simplified away. They add no gate, record or command. Their checks
run inside steps Forge already has:
- the spec and story cold reads;
- the Simpler rule in review;
- the functional check;
- the check-back.

The Forge skill's "Build simple" section carries them to every phase on both hosts. Three owner
decisions shape them:

- **Structure only where needed.** The standards page asks for an interface only when it wraps an
  external service or a real second implementation exists. It asks for no microservice or "future
  growth" planning, no module that no story needs, and no file split by line count.
- **Smallest stack first.** A new client app starts with the smallest stack that runs its first
  story, for example NestJS, React, Postgres and CI. Redis and queues, CDK, OIDC and a monitoring
  stack are added only when a story's `New moving parts` line names them. The stack conventions
  Forge ships are trimmed to what that stack uses. Briefs point to a convention file only when the
  task touches its concern; nothing has to be read up front.
- **One UI skill.** impeccable is the only required UI skill, and `forge doctor` checks for it.
  Motion skills are used only when a Done-when item needs motion.

The functional check for a user-facing task walks each Done-when item the way the client's user
would:
- an item that fails is `Not done` (P1);
- missing keyboard access, labels or contrast on that path is P1;
- an extra screen, field or step is an advisory `Simpler:`;
- it triggers one likely failure and checks that the message says in plain words what to do next.

At the check-back, after recording the result, the agent asks one question with options:
- target met: "Stop here" (recommended) or "Next problem card";
- target missed: "Change the slice", "Remove it" or "Find out why".

Adding features is never the default.

### Git hooks

`forge sync` installs two one-line shims, `pre-commit` and `pre-push`, into the repo's git hooks
folder, which every worktree shares. They call `forge hook pre-commit` and `forge hook pre-push`.
They are not committed, so each clone runs `forge sync` once, and `forge doctor` reports missing
shims. The rules:

- **pre-commit** refuses:
  - a commit on the default branch;
  - a commit on a branch Forge didn't start (no story, task or fix state);
  - a commit on a fix branch that breaks the promote rule.

  Each refusal names the next command.
- **pre-push** refuses:
  - any push that updates the default branch;
  - pushed fix commits that break the promote rule. This catches commits made with `--no-verify`.
- If `forge` isn't installed, both hooks refuse and print the install line.

### Host hooks and adapters

- Host hooks do exactly three things:
  - `forge hook context` at session start: prints `forge next` and the current story state.
  - `forge hook deny` before shell commands: blocks the destructive commands (the list is carried
    over from the old one), any `--no-verify`, and `gh pr merge`.
  - `forge hook approval` after the question and plan tools: records approvals and counts human
    touches.
- `forge sync` writes these files for the pinned version. Each generated file says it is
  generated, and `forge doctor` reports drift.
- **Shared:**
  - `AGENTS.md`: a Forge block of at most 60 lines between `<!-- forge:begin -->` and
    `<!-- forge:end -->`. It covers the flow, the lanes, `forge next`, never committing to the
    default branch, and plain English for humans. Text outside the block stays the repo's own.
  - The two git hook shims (installed, not committed).
  - `.github/workflows/forge.yml`: installs the pinned Forge with `uv` and runs the `ticket` and
    `roadmap` jobs (`forge hook pr-check`).
- **Claude Code:**
  - `CLAUDE.md`, which imports `AGENTS.md` and adds a few lines: approval goes through Plan Mode
    with the story doc; long `forge work` runs go in the background.
  - `.claude/settings.json`, Forge's hook entries only; other keys stay:
    - SessionStart runs `context`;
    - PreToolUse on Bash runs `deny`;
    - PostToolUse on `ExitPlanMode|AskUserQuestion` runs `approval`.
  - `.claude/skills/forge/SKILL.md`, the Forge skill: the human's intents mapped to commands.
- **Codex:**
  - `.codex/hooks.json`:
    - SessionStart runs `context`;
    - PreToolUse on Bash runs `deny`;
    - PostToolUse on `request_user_input` runs `approval`.
  - `.codex/config.toml`: only the keys Codex needs to run project hooks.
  - `.codex/skills/forge/SKILL.md`: the same skill text.
- The old Codex role files, prompts and model routing are not generated.

### What `.factory/` holds

Only current state, one file per story, task or fix, so parallel branches never edit the same file:

- `.factory/stories/<KEY>/story.json`: the title, the doc path, the status (planning, read,
  approved, building, done), the cold read (who, when, doc hash), the approval (who, when, hash of
  the approved sections), the human-touch count, and the date the story was done.
- `.factory/stories/<KEY>/<TASK>.json`: the task's status (started, working, reviewing, waiting for
  checks, fixing, done), its branch, its start and done dates, and the last review (commit, product
  tree, clean or blocked).
- `.factory/fixes/<fix>.json`: the reason, the branch, the starting commit, the status, the start
  and done dates, and the last review.

Nothing is stored that git or GitHub already holds: pull request links, CI results, findings, test
output, diffs, merge times or any history list. The board's timeline comes from merged pull
requests plus the dates above. `.factory/` is written only by `forge` commands.

### The board

- `forge board` writes one static page to `.git/forge/board.html` (or `--out <path>`) and opens it.
  It reads the state on the default branch, on Forge branches on the remote and in local
  worktrees, plus the roadmap and, when `gh` is available, whether each pull request is open or
  merged.
- It reuses the look of today's board page. For each roadmap story it shows:
  - one state sentence built from the state files and open pull requests, such as "Being built:
    2 of 4 parts finished, 1 waiting for someone to accept it";
  - how long each finished part took, from its start and done dates;
  - the dated timeline, oldest first. It starts with "Ravi approved the plan" on the approval
    date. Then comes each merged pull request of the story (matched by its branch name) as its
    title and summary line, on its merge date. It ends with "The story was finished" on the done
    date.
- Small fixes are listed in their own section: each merged fix's title and summary.
- It shows no IDs, hashes, file paths or jargon ("P0", "CI", "PR", "commit", "branch",
  "worktree"). People are named by their git name.
- Without `gh`, it shows the state and the dates, and says the finished work list is unavailable.

### `forge next`

`forge next` reads the state and the current checkout, then prints where things stand in one
sentence and the exact next command(s). It covers every state:

- no story yet;
- planning, then read and waiting for approval (with the Codex question id, or the missing client
  sign-off);
- tasks ready to start (all of them);
- a worker running;
- close blocked (with the reason);
- waiting for checks;
- done and waiting for a merge.

The session-start hook prints the same output.

### `forge sync`, `forge doctor` and upgrades

- `forge sync` refuses when the installed version differs from the pin. It rewrites only
  Forge-owned files and blocks, and prints what it changed.
- Upgrading is a fix like any other:
  1. `forge fix start "Upgrade Forge to vX.Y.Z"`.
  2. Bump `version`.
  3. Install the new version.
  4. `forge sync`.
  5. `forge close`.
- `forge doctor` checks:
  - `git`, `gh` (signed in), `uv`, and the worker CLI;
  - the Autoreview helper at its pinned version;
  - the installed version against the pin;
  - that the git hook shims are installed;
  - drift in the generated files;
  - that `checks` is not empty.

### `forge migrate` (clients that copied Forge in)

`forge migrate` runs in a client that copied in the `factory/` layout (the myclaw family, copied
on 12 September). It works only on a new `forge/migrate-v1` branch and ends with one pull request
through the normal close.

- **It refuses** while a task, stage or Lite window is in flight, and lists each one to finish or
  drop first.
- **It deletes** the copied Forge files: the files the copied manifest lists (`factory/`, the
  `forge` launcher scripts, `harness.yaml`, `constitution/`, Forge's docs, prompts, schemas and
  workflows, and the Codex role files). It also deletes the old `.factory/` records; they stay in
  git history. Files the client changed are deleted too, and listed by name in the pull request
  body.
- **It keeps** the client's product code, `docs/product/`, `docs/specs/`, `docs/decisions/`,
  `docs/context/`, `prototype/`, `plans/roadmap.json`, and any text of its own in `AGENTS.md` and
  `CLAUDE.md` (kept outside the Forge block).
- **It converts** each active plan into a v1 story doc:
  - "What and why" becomes "Why";
  - "What changes for you" and "Done when" are kept word for word;
  - the task decomposition table becomes "Tasks";
  - the technical approach becomes "Notes".

  A plan approved in the old Forge keeps its approval, recorded as carried over, because the
  approved sections are unchanged. Done tasks stay done; the rest start as not started.
- **It writes** `forge.toml` pinned to the running version and runs `forge sync`. The client's
  accepted sign-off decision stays in `docs/decisions/`, so the sign-off gate is already met.

Clients from before the `factory/` layout (Gantry-fork, openclaw) are refused with a pointer to the
"move vendored clients" story.

In the Forge source repo itself (it contains `src/forge/`), `forge migrate` converts the active
plans, writes `forge.toml` and runs `forge sync`, but deletes nothing. The switch deletes the old
tree after the switch checks pass.

### Tests and CI in this repo

- Behaviour tests drive the real `forge` command in temporary git repos. A bare remote stands in
  for GitHub's git side, and stub `gh`, `claude` and Autoreview programs sit on `PATH`. Host-hook
  tests feed Claude-shaped and Codex-shaped payloads through the commands written in the
  generated `.claude/settings.json` and `.codex/hooks.json`.
- Each acceptance criterion below has one test function, which cites the criterion's number
  (parametrised cases allowed). A CI check fails when:
  - a criterion has no test, or a test cites no criterion;
  - a module in `src/forge/` is over 1,200 lines;
  - the command table has more than 20 commands.
- The new suite runs on Linux, macOS and Windows runners, each in under 5 minutes.

### The switch

1. **Adopt.** This repo moves onto v1 with a release-candidate tag. `forge migrate` runs in its
   source-repo mode: the active plans become story docs, `forge.toml` is written, and the old host
   hooks are replaced. The old tree stays, unused.
2. **Switch checks.** All three must pass:
   - the FDE story runs end to end on v1 (story doc, one read, one approval, tasks built from the
     code already built for it, closed by the close rule, merged);
   - a fresh client made with `forge init` closes one fix;
   - myclaw's `forge migrate` pull request closes and is merged, and a fix in myclaw then closes
     on v1.
3. **Switch.** Tag the last old-tree commit, then delete:
   - the old tree (`factory/`, `forge`, `forge.cmd`, `harness.yaml`, `constitution/`, `install/`,
     `harness/`, `setup`);
   - the old workflows, apart from test CI, ticket and roadmap;
   - every doc other than the guide, the standards page, `docs/specs/` and `docs/decisions/`.

   Then mark the superseded decisions and tag `v1.0.0`.

## Acceptance criteria

1. **What changes first (principle 1).** The template from `forge story new` starts with
   "What changes for you". The roadmap check fails a pull request that carries a story doc if the
   doc doesn't start that way, its read has a finding without a disposition, or its approval hash
   doesn't match the doc.
2. **Gates check outcomes (principle 3).**
   - Close, task start and the pull request checks refuse only for: a red, missing or pending
     required check; an open P0 or P1 finding; a missing or out-of-date approval (including a
     missing client sign-off); or work that isn't finished yet (a dependency, or a review run that
     failed twice).
   - Every refusal anywhere prints the problem in one sentence and a `Next:` line with a command.
3. **Every refusal is tested (principle 4).** Every refusal message is declared in a refusal
   table (one per module), and each has a behaviour test that triggers it and checks its text.
4. **One test per rule (principle 5).** Every numbered criterion here has exactly one test
   function citing it, and every test cites one. No test reads or asserts on the layout of a state
   file; tests look only at command output, git, the files a human reads, and the calls the stubs
   recorded.
5. **Forge stays small (principle 6).** CI fails when a module in `src/forge/` is over 1,200 lines
   or the command table has more than 20 commands.
6. **Third-party contracts (principle 7).** Autoreview, the GitHub CLI, Claude Code (hook payloads
   and the headless worker) and Codex (hook payloads) each have one contract test. Each test feeds
   a recorded sample with an extra unknown field and passes. The Autoreview helper version is
   pinned, and `forge doctor` reports a different one.
7. **Same result on both hosts (principle 9).** The approval, context and deny tests run through
   the commands in both generated adapters and give the same result. An approval through Plan Mode
   and one through `request_user_input` record the same state.
8. **Plain English (principle 11).** The board page for a sample repo and the summary at the top
   of each pull request body contain no story or task IDs, no hex strings of 7 or more characters,
   no file paths and none of the words "P0", "P1", "CI", "PR", "commit", "branch" or "worktree".
   The approval question is exactly "Approve this plan?".
9. **Nothing changes outside a pull request (principle 12).**
   - Running every state-changing command on the default branch leaves that branch's head and
     files unchanged. The only exception is `forge init` in a repo with no commits yet, which makes
     the first commit.
   - `forge migrate` and `forge sync` changes land only on a branch.
10. **Version pin.**
    - A state-changing command refuses when the installed version differs from `forge.toml`, and
      prints the install line.
    - Installing from a tag with `uv tool install` and running `forge version` prints that tag's
      version.
11. **Story doc shape.**
    - `forge story new` refuses a key that isn't on the roadmap.
    - A Tasks table with a duplicate ID, an unknown "After" ID or a dependency cycle is reported
      with the row that's wrong.
12. **Cold read.** `forge story read` writes the notes file and records the reader, time and doc
    hash. Approval is refused (nothing recorded) for a story with no cold read.
13. **Approval scope.** Once approved, editing "What changes for you" or "Done when" makes
    `forge task start` refuse until a new approval. Editing "Why", "Tasks" or "Notes" doesn't.
14. **Approval capture.**
    - A matching `ExitPlanMode`, or an `approve_<KEY>_<hash>` answer of "Approve", records the
      approval.
    - Nothing is recorded, and `forge next` says why, for: a failed tool call, "Request changes",
      a stale hash, or text that matches no story doc.
15. **Human touches.** Each approval and each other answered question in a story's worktree adds
    one to that story's touch count, and the board shows it.
16. **Task start.**
    - `forge task start` refuses before the story is approved, or while a dependency is unmerged.
    - Otherwise it creates the branch, the worktree and the task's state. The branch starts from
      the story branch until the story doc is on the default branch, and from the default branch
      after that.
    - `forge next` lists all dependency-ready tasks.
17. **Worker.**
    - `forge work` with `workers = "claude"` runs `claude -p` in the worktree with a brief holding
      the story's three sections, the task row, the notes and the standards page.
    - In a fix round the brief also holds the open serious findings and the failing checks.
    - `workers = "codex"` refuses with the warm-threads message.
18. **Close.** `forge close` behaves as the close rule spec's acceptance criteria say, for tasks
    and fixes alike. It reads only Autoreview's `findings` and `review_status`, and replaces only
    its own block in the pull request body.
19. **Functional check.** For a user-facing task, the review instructions say a missing functional
    check is a P1 "Not done" finding.
20. **pre-commit.** The hook refuses:
    - a commit on the default branch;
    - a commit on a branch Forge didn't start;
    - a sixth code file on a fix;
    - a fix that touches `docs/decisions/`, `docs/specs/` or an `interfaces` path.

    Each refusal names the next command.
21. **pre-push.** The hook refuses a push to the default branch, and fix commits made with
    `--no-verify` that break the promote rule.
22. **Promote.** `forge story new <KEY> --from-fix <fix>` keeps the fix's commits on the story's
    first task branch and puts the fix's reason in the draft "Why".
23. **Deny hook.** The hook blocks the carried-over destructive commands, `--no-verify` and
    `gh pr merge`, and allows ordinary commands.
24. **Pull request backstop.**
    - The `ticket` job fails a pull request from a branch Forge didn't start, or a fix over the
      limit.
    - The `roadmap` job fails a pull request that marks a task or fix done without a clean review
      covering its head's product tree.
25. **State only.** No command writes a pull request link, CI result, finding, test output or
    history list into `.factory/`. Each task and fix writes only its own state file.
26. **Board.** For each roadmap story, `forge board` shows a state sentence, the time each
    finished part took, and a timeline. The timeline is the approval date, each merged pull
    request's title and summary line by merge date (from a stubbed `gh`), and the done date, in
    that order. Without `gh` it shows the state and dates only.
27. **Pull request title and summary.** Close gives every pull request a plain-English title and
    a one-line plain-English summary as the first line of its body. Re-running close keeps both.
28. **Sync.**
    - `forge sync` writes exactly the listed adapter files for both hosts and installs the two git
      hook shims.
    - A second run changes nothing.
    - Text outside the `AGENTS.md` block and settings keys that aren't Forge's are kept.
29. **Doctor.** `forge doctor` reports one row, with its fix, for each of: a missing tool, a
    version mismatch, unset hooks, adapter drift and an empty `checks`. It passes on a repo just
    made by `forge init`.
30. **Migrate.**
    - On a copy of a myclaw-shaped fixture, `forge migrate` makes one branch that:
      - deletes the copied Forge files and old records;
      - keeps product and client docs;
      - converts each active plan into a story doc with its approval carried over;
      - writes `forge.toml` and the adapter.
    - It refuses while work is in flight, and refuses an `.agents/`-era layout.
    - In a repo that contains `src/forge/`, it converts plans and writes the adapter but deletes
      nothing.
31. **Speed.** The new suite finishes in under 5 minutes on each CI runner.
32. **Client sign-off.**
    - In a client repo with no accepted `client-signoff` decision, a matching approval records
      nothing, and `forge next` names the sign-off step.
    - Once the decision is accepted, the same approval records.
    - In the Forge source repo, approval needs no sign-off.
33. **New moving parts line.**
    - The template from `forge story new` ends its Tasks section with `New moving parts: none`.
    - The roadmap check fails a pull request carrying a story doc with no `New moving parts:` line.
    - The worker brief and the review instructions both contain the story's line.
34. **Simpler rule.** The review instructions contain the Simpler rule:
    - P2 `Simpler: <cut> → <replacement>`;
    - P1 for a new moving part the story doesn't name;
    - required structure for a real concern is not a finding;
    - validation, security, data-loss protection and accessibility are never "simpler".
35. **Simple-enough cold read.**
    - The cold-read prompt contains the scope challenge: `Cut or defer:`, the `New moving parts`
      check, the smaller shape, unlisted one-way steps, and never dropping validation, security,
      data-loss protection or accessibility.
    - The notes template offers "cut", "defer" and "keep" dispositions.
36. **Client apps simple.**
    - The shipped standards page lists the 11 client-app principles.
    - It has no rule asking for an interface per service, microservice or "future growth" planning,
      or a file split by line count.
    - The shipped stack conventions name Redis or queues, CDK, OIDC and a monitoring stack only as
      "add when a story's New moving parts names it".
37. **One UI skill.**
    - `forge doctor` fails without impeccable and passes with impeccable and no other UI skill.
    - The brief and review text name motion skills only for a Done-when item that needs motion.

## Success measure

- Metric: three numbers, from the board and GitHub:
  - task cycle time: the median time from `forge task start` to the task being closed;
  - human touches per story: approvals plus other answered questions; merges are counted
    separately;
  - the share of merged pull requests that fix Forge itself instead of the product.
- Baseline:
  - cycle time: close alone took from minutes to 4.5 hours after a clean build, and one task took
    four days;
  - touches: planning four stories took more than a dozen approvals;
  - fixes to Forge: 11 of the last 25 merged pull requests (to 2026-09-25).
- Target:
  - median task cycle under 2 hours, with close under 30 minutes;
  - three or fewer human touches per story;
  - under 10% of merged pull requests fixing Forge.
- Check date: 2026-11-15

## Out of scope

- The Codex worker backend. It comes with the warm-threads story after the switch, reusing the SDK
  setup code already built.
- The rest of the discovery-to-sign-off story (traced sources, a measurable outcome, the
  show-and-tell loop, a richer sign-off record). v1 keeps only the basic sign-off gate; the rest
  comes after the switch.
- The FDE story's own features (discovery questions, payback, success-measure checks). They ship
  in that story, which runs on v1 as a switch check.
- Moving clients from before the `factory/` layout, and any client other than myclaw. These belong
  to the "move vendored clients" story.
- Merging pull requests automatically; a human merges.
- Lessons, deferrals, audits, outcome files, event export and the old history folders.
- Changing Autoreview or CI sharding inside client repos.
