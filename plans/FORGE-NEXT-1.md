# Forge v1: a lean rebuild that both coordinators drive, then the switch

## What changes for you

- Forge becomes one tool that you install from a release. Every repo pins its version instead of
  carrying its own copy. The pin and every other setting live in one file, `forge.toml`, which your
  coding agent keeps: it asks you, then makes the change in a normal change, upgrades included.
- A story is one short doc: what changes for you, why, when it's done, the tasks and the risks. It
  gets one independent read and one approval from you. There are no task plans and no more
  approvals, unless what the story promises you changes. The doc arrives with the story's first
  finished piece, so there is nothing extra to merge.
- Every change is a pull request that closes the same way: the tests pass and a review finds no
  serious problem. A small fix needs a pull request, one line saying why and one line saying when
  it's done. A fix that grows past five code files or changes an interface becomes a story and
  keeps its work, unless you allow it to stay a fix.
- Mistakes are caught when a commit or push happens, not only at the pull request.
  - Main only changes through a pull request with green checks and a clean review. GitHub enforces
    this for this repo and for every client Forge sets up or moves, and Forge tells you when it
    switches the rule on.
  - The agent can't merge; merging stays yours.
- Claude Code and Codex drive the same steps and get the same result.
- The board tells each story's history and current state in plain English, readable by someone
  who isn't technical.
  - It shows how long each step took and flags the slow ones.
  - It shows the three numbers that tell us whether the rebuild worked.
  - The history comes from each finished change's plain-English title and summary, so Forge keeps
    no separate history of its own.
  - When a story finishes, you give it a one-line outcome.
- Clients that copied Forge in move over in one pull request each, starting with myclaw right after
  the switch, where one fresh story is then built and timed end to end. Older clients follow in a
  later story. Moving a client folds its old verify commands into `forge.toml`, keeps only
  office-hours design docs from gstack's store, and pins its client sign-off record.
- Forge's docs shrink to one standards page (about 300 lines, opening with the 13 principles you
  adopted), a guide, the specs and the decisions, beside the product and context docs your
  discovery work produces.
- The apps Forge builds for clients are built simple.
  - Every story names any new moving part it needs, such as a new service or queue. The review
    flags anything the story doesn't need, and blocks a new moving part the story didn't name.
  - The independent read asks "is this simple enough?".
  - A new client app starts on the smallest stack that runs its first story. Structure like
    interfaces is added only where it's really needed.
  - impeccable is the only required design skill.
- Until the switch, nothing else starts, except the warm-threads story: you asked for Codex workers
  early, so it was re-planned, approved and is being built alongside.
- The FDE story becomes the first real story on the new Forge. It is re-planned for it and needs
  one fresh approval from you; its gstack-removal part becomes "keep only office-hours design
  docs".
- The sign-off story continues after the switch.

## Why

Forge has become heavier than the work it manages. It runs to about 47,000 lines, and most of that
checks its own bookkeeping. On one day four finished tasks could not close because of it, and 11 of
the last 25 merged changes fixed Forge instead of the product. Every client also carries a full copy
of it. You chose to build a small new Forge in this repo, run it beside the old one, switch over
once it has proved itself on real work, and then delete the old tree. The way a task closes (green
tests and a clean review) stays exactly as already agreed.

## Done when

1. The FDE story, re-planned for the new Forge, is built, reviewed clean, tested green and merged.
2. A brand-new client set up with the new Forge makes a small fix, and it is merged the same way.
3. After the switch, myclaw moves to the new Forge in one merged pull request, and one fresh story
   in myclaw is then built and merged the same way, with its time measured.
4. Claude Code and Codex give the same result on the same steps. Every rule in the spec has one
   automatic test, and Forge's own tests finish in under five minutes on Linux, macOS and Windows.
5. Forge stays small: no file over 1,200 lines, the whole tool under its size limit, and at most 20
   commands.
6. The board shows each story in plain English, with step times, slow flags and the three success
   numbers, and no IDs, codes or jargon.
7. The review blocks a new moving part that a story didn't name.
8. New client apps start on the smallest stack, with impeccable as the only required design skill.
9. The old Forge is deleted, its last state is kept under a tag, and version 1.0.0 is released.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| CORE | Core | The package, the full command table, state helpers, the version pin, the line ceiling, the refusal convention, the test harness, the rules check and the new CI workflow | 5 | `pyproject.toml`, `src/forge/__init__.py`, `src/forge/cli.py`, `src/forge/repo.py`, `.github/workflows/forge-next.yml` | `tests/conftest.py`, `tests/test_rules.py` | none | no |
| STORY | Story | The story doc, the read-only cold read for stories and specs, v1 approval capture on both hosts, the client sign-off gate, human touches, promotion from a fix, the `story done` command, `forge next` and the context hook | — | `src/forge/story.py`, `src/forge/approval.py`, `src/forge/nextstep.py`, `src/forge/templates/story.md`, `src/forge/templates/cold-read.md` | `tests/test_story.py`, `tests/test_approval.py`, `tests/test_next.py` | CORE | no |
| RECORDS | Records | Saving and confirming specs (after a cold read); writing and accepting decisions; `roadmap add` | — | `src/forge/records.py` | `tests/test_records.py` | CORE | no |
| WORK | Work | Task start with Scope overlap refusal, fix start with why and done-when, `fix allow-large`, the Claude worker and its brief, git hooks with the promote rule, the deny hook | — | `src/forge/task.py`, `src/forge/worker.py`, `src/forge/githooks.py`, `src/forge/deny.py`, `src/forge/templates/brief.md` | `tests/test_task.py`, `tests/test_worker.py`, `tests/test_githooks.py`, `tests/test_deny.py`, `tests/stubs/claude` | CORE | no |
| CLOSE | Close | Close by the close rule (default branch merged first), the Autoreview loop with retry, review freshness, the committed review result, the check wait, fix kinds, dismissals, the pull request's title, summary and Forge block, the required `forge-pr-check` run from base | — | `src/forge/close.py`, `src/forge/review.py`, `src/forge/checks.py`, `src/forge/prcheck.py`, `src/forge/templates/review.md` | `tests/test_close.py`, `tests/test_prcheck.py`, `tests/stubs/autoreview` | CORE | no |
| SETUP | Setup | init (one first commit, pinned, default interfaces and test, branch protection), sync, doctor (hook health, test workflow), fail-closed adapters for both hosts, the workflow template, the installed-from-tag job | — | `src/forge/sync.py`, `src/forge/init.py`, `src/forge/doctor.py`, `src/forge/templates/adapters/`, `src/forge/templates/skeleton/`, `src/forge/templates/skill.md`, `.github/workflows/forge-next.yml` | `tests/test_setup.py` | CORE | no |
| BOARD | Board | The plain-English board: state sentences, step times, slow flags, touches, a timeline from merged pull requests and state dates, and the three success numbers in `forge next` | 6 | `src/forge/board.py`, `src/forge/board.html`, `src/forge/nextstep.py` (metrics line) | `tests/test_board.py` | CORE, STORY | yes |
| MIGRATE | Migrate | `forge migrate`: preflight (clean, at the fetched default branch, no links, no taken destinations), old records deleted, the old Forge's paths including `.envrc` and gstack's store, verify commands into `test`, office-hours docs kept, kept copies, carried-over approvals, a migrate fix state with a named `allow-large`, pin and branch protection, and the source-repo mode | — | `src/forge/migrate.py`, `src/forge/close.py`, `src/forge/nextstep.py`, `src/forge/cli.py` | `tests/test_migrate.py`, `tests/fixtures/copied-client/` | SETUP, STORY | no |
| DOCS-STANDARDS | Standards | The standards page (Forge and client-app principles, structure only where needed, constitution changes carried over), the trimmed client stack conventions, impeccable as the only UI skill in doctor, the guide, the archive list | 8 | `src/forge/doctor.py`, `src/forge/standards.md`, `src/forge/templates/conventions/`, `docs/guide.md`, `docs/archive.md` | `tests/test_standards.py` | STORY, RECORDS, WORK, CLOSE, SETUP | no |
| DOCS-PHASES | Phases | The build-simple phase texts: skill "Build simple", planning and roadmap rules, story template, cold read, review instructions, worker brief with the functional check, check-back | 7 | `src/forge/templates/*.md` | `tests/test_phases.py` | DOCS-STANDARDS | no |
| ADOPT | Adopt | This repo on v1 (`repo = "forge-source"`, pinned to the release candidate, installed from its own branch commit): three plans converted with approvals read from their plan metadata (this story and warm threads carried over, FDE for re-plan), `AGENTS.md` and `CLAUDE.md` replaced wholly, the walkthrough and contract tests, every criterion tested | 4 | `forge.toml`, `.claude/settings.json`, `.codex/hooks.json`, `.github/workflows/forge.yml`, `src/forge/migrate.py`, `AGENTS.md`, `CLAUDE.md`, `plans/` | `tests/test_walkthrough.py`, `tests/test_contracts.py` | STORY, RECORDS, WORK, CLOSE, SETUP, BOARD, MIGRATE, DOCS-STANDARDS, DOCS-PHASES | no |
| FIXES | Fixes | Close needs every check green; branch protection never weakens; the client sign-off record pinned in `forge.toml` and carried over by migrate | — | `src/forge/checks.py`, `src/forge/init.py`, `src/forge/migrate.py`, `src/forge/repo.py`, `src/forge/approval.py` | `tests/test_close.py`, `tests/test_setup.py`, `tests/test_migrate.py`, `tests/test_approval.py` | ADOPT | no |
| PILOT-FDE | Pilot | The FDE story and its spec re-planned and approved for v1, and its tasks (skill, `spec payback`, `spec measure`, the impeccable row) closed and merged | 1 | the FDE story's own pull requests | the FDE story's tests | ADOPT, FIXES | no |
| CLIENT-FIX | Client | A fresh private client, knacklabs/forge-trial-client, made with `forge init` from the release candidate, closes and merges one fix | 2 | the trial client repo | its CI | ADOPT, FIXES | no |
| SWITCH | Switch | The old workflows replaced by v1's generated CI, branch protection on this repo, the old tree, `.envrc`, gstack's store and old Forge docs deleted (pilot, product and context docs and Codex's role files kept), decisions and old pending stories marked superseded, version 1.0.0 set and tagged on the merge commit | 9 | `.github/workflows/`, `factory/`, `forge`, `forge.cmd`, `harness.yaml`, `constitution/`, `install/`, `harness/`, `setup`, `.envrc`, `.gstack/`, `.codex/` routing, `src/forge/__init__.py`, old Forge docs under `docs/` | the full v1 suite in CI | ADOPT, FIXES, PILOT-FDE, CLIENT-FIX | no |
| MIGRATE-MYCLAW | Myclaw | After the switch: myclaw's open old-Forge work finished or dropped by the owner, its migrate pull request merged, then one fresh small pending story built on v1 end to end and timed | 3 | the myclaw repo | its CI | SWITCH | no |

New moving parts: the v1 package (Done when 4, 5); `.factory/` state files (6); git hooks (4); host adapters for both hosts (4); the generated CI workflow with `forge-pr-check` (2); `forge migrate` (3).

## Risks

- Until the new Forge takes over this repo, the old one runs it. Each change can touch at most five
  code files, so the rebuild is cut into many small pieces. Most of them can be built at the same
  time.
- Other stories wait until the switch, except warm threads. Running the FDE story as the pilot keeps
  that wait short.
- Until the warm-threads story lands, workers run on Claude only. Codex can coordinate, but a
  Codex-only machine still needs Claude Code installed to build.
- Old Forge records are not converted. Moving a client deletes them, and their history stays in git.
  Forge files the client edited are set aside, not deleted, and the pull request lists them for you
  to decide. Migrate never follows a link and refuses before changing anything when a destination
  is already taken.
- In client repos a story still can't be approved until the client's sign-off is recorded. The
  sign-off record is pinned in `forge.toml`, carried over from the old `harness.yaml`. The fuller
  sign-off checks come back with the sign-off story after the switch.
- The switch deletes the old Forge before myclaw moves. The myclaw trial on a throwaway copy, plus
  the migrate tests, stand in for a real client until then.
- There is no reliable cycle-time number for the old Forge. The pilot and the first two weeks
  after the switch set the baseline.

## Notes

Converted from plans/active/FORGE-NEXT-1-lean-forge-v1-a-simpler-factory-rebuilt-and-switched.md by forge migrate.

### What I need from you

Nothing beyond approving this plan, and later one approval of the re-planned FDE story.

---

### Technical approach

- The spec for the new Forge is the contract. The close rule spec is the close rule. Code goes in
  `src/forge/` with a root `pyproject.toml` (Python 3.11+, standard library only). The standards
  page (`src/forge/standards.md`, package data) and all templates (`src/forge/templates/`)
  ship inside the package. Tests go in `tests/`. Install with
  `uv tool install git+https://github.com/knacklabs/symphony-forge@<tag>`.
- **Who writes it.**
  - By owner instruction, Claude Opus subagents write every task. They use Forge's ledgered
    Claude-writer path (degraded windows) temporarily, until v1's own worker runs this repo after
    ADOPT.
  - The coordinator drives: it starts tasks, triages findings, and runs Autoreview (on
    `gpt-6-astra` from 2026-09-26, by owner instruction) until no P0 or P1 finding is left.
  - Once the warm-threads story gives this repo Codex workers, Codex builds the remaining tasks.
  - A task-level grill (one read-only Codex cold read, 2026-09-26) went through the remaining
    tasks before they were built. The owner decided four questions; the rest were settled by
    simple rules written into the task sections below.
  - Each task is closed by its pull request, not by the old stage close. The body carries
    `Ticket: FORGE-NEXT-1` and a `Ticket:` line for the window it closes; today's ticket check
    accepts a Forge development pull request on those lines. Each pull request needs green CI (the
    old suite plus the new one) before a human merges it.
- **Five code files per task.** The hook budget counts code files; tests and Markdown are
  excluded, and so is `.factory/` state, which `forge` commands write, not Claude. So every task
  up to and including ADOPT touches at most five code files. After ADOPT this repo runs on v1,
  where a task has no file limit.
- **Parallel by design.** CORE fixes the shared seams up front, so tasks in the same wave never
  edit the same file:
  - the full command table in `src/forge/cli.py`, where each command points at a module function
    and an unbuilt one prints "not built yet";
  - the list of checks that `forge hook pr-check` runs;
  - the state helpers;
  - the refusal convention: one refusal table per module, each refusal printing the problem and a
    `Next:` command.
- **Prompt text in Markdown.** All prompt and instruction text lives in Markdown templates under
  `src/forge/templates/`, so text changes never count against the five-file limit:
  - the story doc (`story.md`) and cold read (`cold-read.md`), from STORY;
  - the worker brief (`brief.md`), from WORK;
  - the review instructions (`review.md`), from CLOSE;
  - the skill (`skill.md`), from SETUP.

  Each task writes a working first version; DOCS-PHASES writes the final text.
- **Carried over from the old tree** (ported, not imported):
  - the init scaffolds and `forge roadmap add`;
  - the Autoreview read-only worktree launcher and invocation, with the helper version pin;
  - the destructive-command denylist and the fail-closed host hooks;
  - the board page's look.

  The old tree stays untouched until SWITCH.
- **Harvested code.** PILOT-FDE ports the FDE skill text and the payback code from branch
  `feat/FORGE-FDE-1-FDE`, kept until then. The SDK setup code on `feat/FORGE-WARM-1-SDK-SETUP`
  was harvested by the warm-threads story, which is being built now.
- **Approval.** STORY defines v1 approval as the hash of "What changes for you" and "Done when".
  Codex capture keeps today's trust checks, applied to that hash: the exact digest, the runtime,
  the tool identity, replay refusal, and exactly one eligible candidate.
- **Branch protection.** On main it requires a pull request and the `tests` and `forge-pr-check`
  checks, and allows no direct pushes.
  - SETUP applies it through `gh api` to each client it initialises.
  - MIGRATE applies it to each client it moves.
  - SWITCH applies it to this repo.

  Each one reports what it set, never silently. Forge never weakens an existing rule: it reads the
  current protection, adds its pull-request requirement and checks, and keeps everything else. The
  deny hook blocks `gh pr merge` for agents.
- **The pull request check.** `forge-pr-check` runs from the base branch (`pull_request_target`
  with a base checkout, like today's ticket gate). It reads policy and config from the base; the
  pull request head is data only.
- **Review freshness.** A clean review covers the product tree plus the story doc's Tasks, Risks
  and `New moving parts`. A change to any of them after a clean review needs a new review round.
- **Version pins.** `forge init` and `forge migrate` pin `forge.toml` to the running version.
  ADOPT's `forge.toml` pins `v1.0.0-rc.1`. After ADOPT's pull request merges, the coordinator tags
  that merge commit `v1.0.0-rc.1` and installs from the tag.
- **The command table**, at most 20 top-level commands:
  - setup: `init`, `sync`, `doctor`, `migrate`;
  - status: `next`, `board`;
  - stories: `story` (`new`, `done`), `read`;
  - work: `task` (`start`), `fix` (`start`, `allow-large`), `work`, `close`;
  - records: `spec` (`save`, `confirm`, and later the FDE story's `payback` and `measure`),
    `decision` (`new`, `accept`), `roadmap` (`add`);
  - internal: `hook` (`context`, `approval`, `deny`, `pre-commit`, `pre-push`, `pr-check`).

  The version is shown by `forge --version`.
- **One test per criterion.** Each spec criterion's test belongs to exactly one task, listed
  under that task below. Other tasks that touch the same rule refer to it.

**CORE: package skeleton, CLI entry and test harness.** Five code files: `pyproject.toml`,
`src/forge/__init__.py`, `src/forge/cli.py`, `src/forge/repo.py` and
`.github/workflows/forge-next.yml`.
- `repo.py` holds the git helpers and the `forge.toml` reader (including `repo`, `test` and
  `interfaces`). It also holds the roadmap reader, the version pin check, the refusal helper and
  the state helpers: read and write state files, add a dated step, and commit state on the current
  branch.
- `pyproject.toml` ships the package's Markdown and data files, and sets the line ceiling for
  `src/forge/` (8,000).
- The tests are `tests/conftest.py` and `tests/test_rules.py`. `conftest.py` gives a temporary
  repo with a bare remote, a stub `gh`, and Claude and Codex hook payload builders.

Done when:

- Criteria 4, 5, 10 and 31 have their tests and pass. The "every criterion has a test" half of
  criterion 4 stays off until ADOPT.
- `uv run forge --version` prints the version, and every command in the table is listed.
- CI prints each pull request's net lines. The new workflow runs `tests/` on Linux, macOS and
  Windows, each under five minutes with a five-minute job timeout.

**STORY: story doc, cold read, approval, `forge next` and the `story done` command.** Three code
files:
- `src/forge/story.py`:
  - `story new`, and promotion from a fix, which adds the roadmap item;
  - `read`: one read-only cold read of a story doc or spec, discarded if any file changes, with
    `--amended`;
  - the `story done` command, which opens a fix of kind `story-done` holding the outcome;
  - doc parsing: Covers, Scope, Tests, `New moving parts`, Risks;
  - the story-doc part of `forge-pr-check`.
- `approval.py`:
  - v1 approval capture for `ExitPlanMode` and `request_user_input`, keeping today's trust checks
    on the section hash;
  - the Forge-made commit of doc, notes and state on the story branch;
  - the client sign-off gate (exempt with `repo = "forge-source"`);
  - counting human touches per state file.
- `nextstep.py`: `forge next` and the context hook.

The story branch is never a pull request; its doc lands with the story's first task pull request.

Done when:

- Criteria 1, 11, 12, 14, 15, 22 and 32 have their tests and pass.
- `forge next` prints one sentence and the exact next command(s) for every state in the spec.

**RECORDS: specs, decisions and the roadmap.** One code file: `src/forge/records.py`. It holds:
- `spec save` and `spec confirm`; confirm requires the spec's cold read, amended hash and
  dispositions;
- `decision new` and `decision accept`;
- `roadmap add`, ported: it adds items from a confirmed spec through the fix lane.

Done when:

- Criterion 41 has its test and passes.
- `spec confirm --by` marks a spec confirmed only after its cold read.
- `decision accept --by` fills in who confirmed it and marks any superseded record.

**WORK: task and fix start, the worker, git hooks and the deny hook.** Four code files:
- `src/forge/task.py`:
  - `task start`, which refuses a Scope that overlaps a started, unmerged task;
  - `fix start` with its why and done-when lines;
  - `fix allow-large`;
  - start dates.
- `worker.py`: the brief (with the task row's Covers, Scope and Tests, `New moving parts` and
  Risks) and the Claude backend, with Codex refused.
- `githooks.py`: pre-commit, pre-push, the promote rule (code files and interfaces only) and the
  `allow-large` reason.
- `deny.py`: the destructive-command denylist, `--no-verify` and `gh pr merge`.

A stub `claude` goes under `tests/`. Done when:

- Criteria 13, 16, 17, 20, 21, 23 and 39 have their tests and pass.
- The worker's log goes under `.git/forge/` and is never committed.

**CLOSE: close, the review loop, the check wait and `forge-pr-check`.** Four code files:
- `src/forge/close.py`:
  - it merges the default branch in first and stops on a conflict with a plain message;
  - it records review-round, CI-green and ready dates;
  - it closes fixes of every kind, including `story-done` and `migrate`;
  - it detects the story's last merge and names `forge story done`.
- `review.py`:
  - the Autoreview runner, with its ported launcher and pin;
  - only the Done-when items the task covers can block;
  - freshness over the product tree and the story doc's Tasks, Risks and `New moving parts`;
  - the committed review result holds findings, dismissals and status;
  - the `Promote` instruction when `interfaces` is empty.
- `checks.py`: waiting through `gh` for the named checks on the reviewed head.
- `prcheck.py`: the required `forge-pr-check`, run from the base branch with base config.
  - It fails for a branch Forge didn't start, a fix over the limit without an `allow-large`
    reason, a fix without its why or done-when lines, or a head whose committed review result
    isn't clean.
  - It calls STORY's story-doc checks.

A stub Autoreview goes under `tests/`. Done when:

- Criteria 2, 18, 19, 24 and 27 have their tests and pass.
- Explicit tests pass for three cases:
  - a failed or incomplete Autoreview run is retried once, then close refuses;
  - a required check that is missing counts as not green;
  - a GitHub API error counts as not green, and close gives the reason.
- The close rule spec's acceptance criteria that apply to v1 pass for a task and for a fix.

**SETUP: init, sync, doctor, adapters, branch protection and the release.** Four code files:
`src/forge/sync.py`, `init.py`, `doctor.py`, and jobs added to `.github/workflows/forge-next.yml`.
- `init.py`:
  - writes `forge.toml` pinned to the running version, with the stack's default `interfaces` and
    `test`;
  - makes one first commit holding both the scaffold and the sync output (later syncs land on a
    branch);
  - applies branch protection through `gh api` and reports it.
- `sync.py` holds the non-Markdown adapter templates inline:
  - the Claude settings hooks and the Codex hooks, both failing closed with exit code 2;
  - the Codex config key;
  - the git hook shims;
  - `forge.yml`, with a `tests` job running `test` and a `forge-pr-check` job run from the base
    branch.
- `doctor.py`:
  - runs each host hook command as a health check;
  - checks that the `tests` workflow runs `test`.
- The workflow jobs:
  - on a test tag, install from the tag with `uv`;
  - check `forge --version`;
  - open the shipped standards page and templates in a fresh client.

The Markdown templates live under `src/forge/templates/`: the `AGENTS.md` block, `CLAUDE.md`, a
placeholder skill, and the docs skeleton ported from today's init. Done when:

- Criteria 28, 29 and 38 have their tests and pass.
- The installed-from-tag job passes.

**BOARD: the plain-English board and the success numbers.** Three code files:
`src/forge/board.py`, `board.html` (in today's board's style), and the metrics line added to
`src/forge/nextstep.py`.
- It shows how long each step took (from the dated steps in state), the total human touches, and a
  plain "slow" line for a part open over 2 working days or a close over 30 minutes.
- The timeline is the approval date, the story's merged pull requests (read through `gh`, matched
  by branch name, shown as title and summary line), then the finished date with the outcome.
- It computes the three success numbers from state and GitHub: task cycle time, human touches per
  story, and the share of pull requests fixing Forge. After the check date, `forge next` shows
  them in one line.
- The tests use a fixture repo that holds state on the main branch, on a remote branch and in a
  worktree, with a stubbed `gh`.

This task is user-facing and gets a functional check. Done when:

- Criterion 26 has its test and passes.
- A person reads the page for a sample story with three tasks and a fix, and every line reads as
  plain English.

**MIGRATE: moving copied-in clients.** One code file: `src/forge/migrate.py`. A small
myclaw-shaped fixture goes under `tests/fixtures/`.
- **Preflight:**
  - it refuses unless the working tree is clean, the checkout sits exactly at the fetched default
    branch, and no work is in flight;
  - it computes the full change set first, including every file `forge sync` will write, and
    refuses any path outside the repo, any link, and any destination that already exists;
  - it replaces `forge/migrate-v1` only when that branch holds nothing but the one commit migrate
    recorded making. Anything else, or a dirty migrate worktree, stops it, and it never resets user
    work.
- **Deletes old records:** every pre-migration `.factory/` entry goes; git history keeps them. It
  then writes the migrate fix state, with an `allow-large` reason recorded with the name of the
  person running the command.
- **Deletes** the old Forge's own paths, and touches nothing else:
  - `factory/`, `forge`, `forge.cmd`, `setup`, `harness.yaml`, `harness/`, `install/`,
    `constitution/` and `WORKFLOW.md`;
  - Forge's docs files and the old `.claude/CLAUDE.md` adapter;
  - `.codex/agents/`, `.codex/explore.config.toml`, and the two Forge skill folders;
  - the old Forge workflows;
  - the old quickfix, lessons, deferral and brief ledgers under `plans/`;
  - `.envrc`, after its old verify commands become `forge.toml`'s `test` (each phase grouped, then
    joined with `&&`);
  - gstack's store under `.gstack/`, after its office-hours design docs move to `docs/context/`,
    plus the old Forge's own gstack lines in `.gitignore` and `.gitattributes`. Other gstack lines
    are listed for the client.
- **Sets aside** client-changed copies of listed files in `.forge-migrate/kept/`, including an
  `.envrc` with the client's own lines, and lists them in the pull request. A converted story whose
  doc doesn't parse goes to `.forge-migrate/replan/` unapproved, unless every part already shipped.
- **Carries over** approvals given on the default branch. Tasks with a marker on the default branch
  count as done.
- **Pins and protects:** it writes `forge.toml` pinned to the running version. The migrate pull
  request merges on the client's old checks, because the base branch has no `forge-pr-check` yet;
  closing it then turns on branch protection and reports it.
- **Source-repo mode:** in Forge's own repo (it holds `src/forge/cli.py`) it converts plans and
  writes the adapter, and deletes nothing.

Done when:

- Criterion 30 has its test and passes.
- A trial run on a throwaway copy of myclaw lists the right deletions, kept copies, conversions and
  carried-over approvals, and myclaw itself is left unchanged.

**DOCS-STANDARDS: the standards page, the client stack conventions, one UI skill, the guide and the
archive list.** One code file: `src/forge/doctor.py`, where impeccable becomes the only required UI
skill (decision C). Everything else is Markdown:
- `docs/standards.md` (about 300 lines, shipped as package data) replaces the constitution. It opens with the 13 Forge
  principles, then the 11 client-app principles. The structure rules apply only where their
  concern exists (decision A): an interface only for an external service or a real second
  implementation, and no microservice or "future growth" planning. The constitution changes carry
  over: default to the stack already in the repo; add a notification module or shared API client
  only when a story needs it.
- The client stack conventions in `src/forge/templates/conventions/` (decision B): today's scaffold
  prompt and convention files are cut to the smallest stack that runs a first story. Redis and
  queues, CDK, OIDC and the monitoring stack are marked "add when a story's New moving parts names
  it", and conventions are read on demand.
- `docs/guide.md`: install, commands, lanes, upgrade and release steps.
- `docs/archive.md`: what the switch removes, and the tag to find it under.

Done when:

- Criterion 36 has its test and passes.
- The standards page is at most 320 lines, opens with the principles, and is part of every worker
  brief.
- The guide names every command in the table, and nothing that isn't in it.

**DOCS-PHASES: every phase text.** No code files; all Markdown in `src/forge/templates/`:
- **skill:**
  - the "Build simple" section: the ladder, challenging the asked-for solution, and the
    `Use what they have` option;
  - planning rules: Done-when items are observable, each task names the items it covers, its Scope
    and its Tests, the `New moving parts` line, Risks for one-way steps, the repo's stack first,
    and replacing deletes the old path;
  - roadmap order by value, with no setup-only stories;
  - the check-back question;
  - motion skills only for a Done-when item that needs them.
- **story doc template:** with Covers, Scope and Tests columns, `New moving parts: none` and
  `Risks: none`;
- **cold read:** "is this simple enough", with cut, defer and keep dispositions;
- **review instructions:** the Simpler rule, and the `Promote` instruction for an empty
  `interfaces`;
- **worker brief:** the build-simple rules and the functional check walk-through.

Done when:

- Criteria 33, 34, 35, 37 and 40 have their tests and pass.
- The skill stays under 120 lines, maps each common intent to one command, and its "Build simple"
  section stays under 40 lines.

**ADOPT: this repo runs on v1.** Four code files: `forge.toml` (with `repo = "forge-source"` and
pinned to `v1.0.0-rc.1`), `.claude/settings.json`, `.codex/hooks.json` and
`.github/workflows/forge.yml`, plus `src/forge/migrate.py` for source-repo mode. Forge is installed
from the ADOPT branch's own commit, which already reports `1.0.0-rc.1`. It runs `forge migrate` in
source-repo mode, and ADOPT's pull request is migrate's branch plus ADOPT's own files. The
conversion covers only these three plans, reading their approvals from
`.factory/stories/<KEY>/plan-meta.json`:
- this story, with its approval and its `New moving parts` line carried over;
- the FDE story, converted for its v1 re-plan;
- the warm-threads story, with its 2026-09-26 approval carried over.

Other old plans stay untouched until the switch supersedes them. It replaces this repo's
`AGENTS.md` and `CLAUDE.md` wholly with the v1 block; clients keep their own text. The old host
hooks are replaced, and the old tree stays unused. It adds the end-to-end walkthrough and contract
tests, turns on the "every criterion has a test" check, and after merge the coordinator tags
`v1.0.0-rc.1`. Done when:

- Criteria 3, 6, 7, 8, 9, 25 and 42 have their tests and pass.
- The walkthrough drives one story through every step with stubs, and ends with the board showing
  its approval, merged parts and finished date in order.
- Every criterion in the spec has exactly one test.
- `forge doctor` passes in this repo, and a fix in this repo closes on v1.

**PILOT-FDE: the FDE story runs on v1.** Starts after ADOPT.
- The FDE story is re-planned for v1 with one fresh approval. Its spec is amended with it: the
  command is `forge spec payback`, and the gstack part becomes "keep only office-hours design
  docs", as `forge migrate` already does.
- Its tasks build the FDE skill section, `forge spec payback`, `forge spec measure` and the
  impeccable doctor row. They are ported from the FDE branch.
- Its code lands in the FDE story's own pull requests, built by v1's worker.

Done when:

- The re-planned FDE story is approved.
- Each of its tasks is closed by the close rule and merged.

**FIXES: what the task-level grill found for v1 itself (a v1 task, no file limit).** Starts after
ADOPT, before CLIENT-FIX:
- close needs every check on the head green, and the named checks present (`checks.py`);
- branch protection never weakens an existing rule (`init.py`, `migrate.py`);
- the client sign-off record is pinned: `forge.toml`'s `signoff` names it, `forge migrate` carries
  it over from `harness.yaml`'s `signoff_record`, and approval needs exactly that record accepted
  (`repo.py`, `approval.py`, `migrate.py`).

Done when each has its test and passes.

**CLIENT-FIX: a fresh client closes a fix.** In a new private repo, knacklabs/forge-trial-client,
set up with `forge init` from the `v1.0.0-rc.1` tag, one fix is started, built, closed and merged.
Done when:

- The fix's pull request is merged with green checks and a clean review.
- Branch protection was applied and reported.

**MIGRATE-MYCLAW: myclaw moves to v1, after the switch.** First the coordinator lists myclaw's open
old-Forge stages and windows, for the owner to finish or drop. Then `forge migrate` opens its pull
request, which closes and is merged. Then one fresh, small pending story (for example SCHED-3) is
built on v1 end to end, from its story doc to its last merge, and its time is measured. Done when:

- The migrate pull request is merged.
- The timed story is merged on v1, and its time is reported.

**SWITCH: replace the old workflows, delete the old tree and release 1.0.0 (a v1 task, no file
limit).** Starts after ADOPT, FIXES, PILOT-FDE and CLIENT-FIX. The final old commit is tagged. The
switch then:
- replaces the old workflows with v1's generated CI (`tests` and `forge-pr-check`) and deletes the
  old ones;
- applies branch protection to this repo and reports it;
- deletes `factory/`, `forge`, `forge.cmd`, `harness.yaml`, `constitution/`, `install/`, `harness/`,
  `setup` and `.envrc`, and gstack's store after moving its office-hours design doc to
  `docs/context/`;
- keeps Codex's own role files in `.codex/agents/`;
- deletes the old Forge docs and superseded specs. It keeps the guide, `docs/archive.md`,
  `docs/product/`, `docs/context/`, `docs/specs/`, `docs/decisions/` and every doc the pilot
  produced;
- sets the package version to `1.0.0`.

It then marks the superseded decisions and supersedes the old roadmap's pending stories. After its
pull request merges, the coordinator tags the merge commit `v1.0.0`, checking that the tag's tree
equals main. Done when:

- The repo holds only the new package, its tests, the kept docs and v1's generated CI.
- Every check is green, and `forge-pr-check` is required.
- `v1.0.0` points at the merge commit, and its tree equals main.

### Task decomposition

CORE comes first. Then six tasks run in parallel, each with its own Scope: STORY, RECORDS, WORK,
CLOSE, SETUP and BOARD. BOARD waits for STORY because it adds a line to `forge next`.
- After those, MIGRATE and DOCS-STANDARDS run in parallel, then DOCS-PHASES.
- ADOPT comes after those; then FIXES; then PILOT-FDE and CLIENT-FIX; then SWITCH; MIGRATE-MYCLAW
  comes last.

Each task ships its own pull request; every task up to and including ADOPT touches at most five
code files. "Covers" lists only the Done-when items (numbered above) that a task can finish by
itself; building-block tasks show "—" and are judged by their criteria.

| Label / exact task ID | What it delivers | Covers | Scope | Tests | Depends on | user_facing |
|---|---|---|---|---|---|---|
| Core / CORE | The package, the full command table, state helpers, the version pin, the line ceiling, the refusal convention, the test harness, the rules check and the new CI workflow | 5 | `pyproject.toml`, `src/forge/__init__.py`, `src/forge/cli.py`, `src/forge/repo.py`, `.github/workflows/forge-next.yml` | `tests/conftest.py`, `tests/test_rules.py` | none | false |
| Story / STORY | The story doc, the read-only cold read for stories and specs, v1 approval capture on both hosts, the client sign-off gate, human touches, promotion from a fix, the `story done` command, `forge next` and the context hook | — | `src/forge/story.py`, `src/forge/approval.py`, `src/forge/nextstep.py`, `src/forge/templates/story.md`, `src/forge/templates/cold-read.md` | `tests/test_story.py`, `tests/test_approval.py`, `tests/test_next.py` | CORE | false |
| Records / RECORDS | Saving and confirming specs (after a cold read); writing and accepting decisions; `roadmap add` | — | `src/forge/records.py` | `tests/test_records.py` | CORE | false |
| Work / WORK | Task start with Scope overlap refusal, fix start with why and done-when, `fix allow-large`, the Claude worker and its brief, git hooks with the promote rule, the deny hook | — | `src/forge/task.py`, `src/forge/worker.py`, `src/forge/githooks.py`, `src/forge/deny.py`, `src/forge/templates/brief.md` | `tests/test_task.py`, `tests/test_worker.py`, `tests/test_githooks.py`, `tests/test_deny.py`, `tests/stubs/claude` | CORE | false |
| Close / CLOSE | Close by the close rule (default branch merged first), the Autoreview loop with retry, review freshness, the committed review result, the check wait, fix kinds, dismissals, the pull request's title, summary and Forge block, the required `forge-pr-check` run from base | — | `src/forge/close.py`, `src/forge/review.py`, `src/forge/checks.py`, `src/forge/prcheck.py`, `src/forge/templates/review.md` | `tests/test_close.py`, `tests/test_prcheck.py`, `tests/stubs/autoreview` | CORE | false |
| Setup / SETUP | init (one first commit, pinned, default interfaces and test, branch protection), sync, doctor (hook health, test workflow), fail-closed adapters for both hosts, the workflow template, the installed-from-tag job | — | `src/forge/sync.py`, `src/forge/init.py`, `src/forge/doctor.py`, `src/forge/templates/adapters/`, `src/forge/templates/skeleton/`, `src/forge/templates/skill.md`, `.github/workflows/forge-next.yml` | `tests/test_setup.py` | CORE | false |
| Board / BOARD | The plain-English board: state sentences, step times, slow flags, touches, a timeline from merged pull requests and state dates, and the three success numbers in `forge next` | 6 | `src/forge/board.py`, `src/forge/board.html`, `src/forge/nextstep.py` (metrics line) | `tests/test_board.py` | CORE, STORY | true |
| Migrate / MIGRATE | `forge migrate`: preflight (clean, at the fetched default branch, no links, no taken destinations), old records deleted, the old Forge's paths including `.envrc` and gstack's store, verify commands into `test`, office-hours docs kept, kept copies, carried-over approvals, a migrate fix state with a named `allow-large`, pin and branch protection, and the source-repo mode | — | `src/forge/migrate.py`, `src/forge/close.py`, `src/forge/nextstep.py`, `src/forge/cli.py` | `tests/test_migrate.py`, `tests/fixtures/copied-client/` | SETUP, STORY | false |
| Standards / DOCS-STANDARDS | The standards page (Forge and client-app principles, structure only where needed, constitution changes carried over), the trimmed client stack conventions, impeccable as the only UI skill in doctor, the guide, the archive list | 8 | `src/forge/doctor.py`, `src/forge/standards.md`, `src/forge/templates/conventions/`, `docs/guide.md`, `docs/archive.md` | `tests/test_standards.py` | STORY, RECORDS, WORK, CLOSE, SETUP | false |
| Phases / DOCS-PHASES | The build-simple phase texts: skill "Build simple", planning and roadmap rules, story template, cold read, review instructions, worker brief with the functional check, check-back | 7 | `src/forge/templates/*.md` | `tests/test_phases.py` | DOCS-STANDARDS | false |
| Adopt / ADOPT | This repo on v1 (`repo = "forge-source"`, pinned to the release candidate, installed from its own branch commit): three plans converted with approvals read from their plan metadata (this story and warm threads carried over, FDE for re-plan), `AGENTS.md` and `CLAUDE.md` replaced wholly, the walkthrough and contract tests, every criterion tested | 4 | `forge.toml`, `.claude/settings.json`, `.codex/hooks.json`, `.github/workflows/forge.yml`, `src/forge/migrate.py`, `AGENTS.md`, `CLAUDE.md`, `plans/` | `tests/test_walkthrough.py`, `tests/test_contracts.py` | STORY, RECORDS, WORK, CLOSE, SETUP, BOARD, MIGRATE, DOCS-STANDARDS, DOCS-PHASES | false |
| Fixes / FIXES | Close needs every check green; branch protection never weakens; the client sign-off record pinned in `forge.toml` and carried over by migrate | — | `src/forge/checks.py`, `src/forge/init.py`, `src/forge/migrate.py`, `src/forge/repo.py`, `src/forge/approval.py` | `tests/test_close.py`, `tests/test_setup.py`, `tests/test_migrate.py`, `tests/test_approval.py` | ADOPT | false |
| Pilot / PILOT-FDE | The FDE story and its spec re-planned and approved for v1, and its tasks (skill, `spec payback`, `spec measure`, the impeccable row) closed and merged | 1 | the FDE story's own pull requests | the FDE story's tests | ADOPT, FIXES | false |
| Client / CLIENT-FIX | A fresh private client, knacklabs/forge-trial-client, made with `forge init` from the release candidate, closes and merges one fix | 2 | the trial client repo | its CI | ADOPT, FIXES | false |
| Switch / SWITCH | The old workflows replaced by v1's generated CI, branch protection on this repo, the old tree, `.envrc`, gstack's store and old Forge docs deleted (pilot, product and context docs and Codex's role files kept), decisions and old pending stories marked superseded, version 1.0.0 set and tagged on the merge commit | 9 | `.github/workflows/`, `factory/`, `forge`, `forge.cmd`, `harness.yaml`, `constitution/`, `install/`, `harness/`, `setup`, `.envrc`, `.gstack/`, `.codex/` routing, `src/forge/__init__.py`, old Forge docs under `docs/` | the full v1 suite in CI | ADOPT, FIXES, PILOT-FDE, CLIENT-FIX | false |
| Myclaw / MIGRATE-MYCLAW | After the switch: myclaw's open old-Forge work finished or dropped by the owner, its migrate pull request merged, then one fresh small pending story built on v1 end to end and timed | 3 | the myclaw repo | its CI | SWITCH | false |

New moving parts:
- the v1 package (Done when 4, 5);
- `.factory/` state files (6);
- git hooks (4);
- host adapters for both hosts (4);
- the generated CI workflow with `forge-pr-check` (2);
- `forge migrate` (3).

### Verify plan

Each task: its behaviour tests, the Autoreview loop until no P0 or P1 finding is left, and green
CI (the old full suite plus the new suite) on its pull request. The story is done when PILOT-FDE and
CLIENT-FIX have passed, SWITCH has merged with `v1.0.0` tagged, and MIGRATE-MYCLAW has moved myclaw
and timed its story. On 2026-11-15 the coordinator runs the check-back against the three success
numbers.
