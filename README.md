# Symphony Forge

[![Release](https://img.shields.io/github/v/release/knacklabs/symphony-forge)](https://github.com/knacklabs/symphony-forge/releases/latest)
[![Tests](https://github.com/knacklabs/symphony-forge/actions/workflows/forge.yml/badge.svg)](https://github.com/knacklabs/symphony-forge/actions/workflows/forge.yml)
[![License: MIT](https://img.shields.io/github/license/knacklabs/symphony-forge)](LICENSE)

Forge is a command-line tool that takes a change from an idea to a merged pull request. Your
coding agent, Claude Code or Codex, does the work. You make the decisions.

![A small fix goes from a request to a merged pull request](docs/assets/demo.gif)

*One small fix in a demo repo, from the request to the merge. The recording is sped up.*

You do three things:

- **Approve** the plan of a larger change.
- **Choose** when the agent gives you options.
- **Merge** the finished pull request, or let the agent merge it.

The agent does the rest. It writes the plan, has a second agent read it, builds each part in
its own branch, runs the tests, gets a code review and fixes what the review finds.

## Quick start

You need [git](https://git-scm.com/), the [GitHub CLI](https://cli.github.com/) signed in with
`gh auth login`, [uv](https://docs.astral.sh/uv/), and Claude Code or Codex. uv installs
Python 3.11 if you do not have it. Forge runs on macOS, Linux and Windows.

1. Install Forge:

   ```sh
   uv tool install --python 3.11 "git+https://github.com/knacklabs/symphony-forge@v1.2.41"
   ```

2. Set up a repo. Clone it, go into its folder, and run:

   ```sh
   forge init
   forge doctor --fix
   ```

   `forge init` works in an empty GitHub repo and in a repo that already has code. It writes
   Forge's settings file (`forge.toml`), the instructions for your agent, the CI workflow and
   the git hooks, and it protects the main branch. `forge doctor` checks the setup and prints a
   fix for each problem.

3. Open Claude Code or Codex in the repo and say what you want:

   > Add a dark mode switch to the settings page.

   The agent runs `forge start`, and Forge picks the right path for the change. When you are
   not sure what comes next, ask "what's next?" or run `forge next`.

No experience with git is needed. If you do not code, give your agent the text in
[Start with Claude](docs/start.md) and it sets up the computer for you.

## How a change goes from idea to merge

A *pull request* is a proposed change to the code. *Merging* it makes the change part of the
project.

1. **Plan.** The agent writes one short page: what changes for you, why, when it is done, and
   the tasks.
2. **Cold read.** A second agent that did not write the plan reads it and lists the gaps. The
   agent fixes the plan. By default there are at most two rounds.
3. **Approve.** You approve the plan once. Nothing is built before that.
4. **Build.** Each task gets its own branch and its own folder, so tasks do not get in each
   other's way. A Claude or Codex worker writes the code and the tests.
5. **Review and tests.** A separate code review reads the change, and the tests must pass. A
   serious finding goes back to the worker. Only then is the pull request ready.
6. **Merge.** You merge the pull request. If you set `merge = "agent"` in `forge.toml`, the
   agent merges ready pull requests for you.

Forge picks one of two sizes for each change:

| | Story | Fix |
|---|---|---|
| **When** | The change touches an interface or more than five code files | A small change |
| **Plan** | A plan, the cold read and your approval | One line of why and a "done when" |
| **Build** | One branch for each task | One branch |
| **Before merge** | Code review and passing tests | Code review and passing tests |

The cold read and the code review score each note for how much the fix helps, how much it costs
and what breaks if the problem stays. Only notes above a fixed bar stop the work. Forge keeps
the other notes as follow-ups or known issues. See [how Forge weighs a note](docs/review-rules.md).

## What you can see

**The board.** `forge board` opens a live page on your computer. It shows what is in progress,
what waits for you and what has merged, in plain English.

![The Forge board. This picture shows an earlier design of the board.](docs/assets/board.png)

**The `/forge` pane in Claude Code.** Type `/forge` to see the builds, tests and reviews that
run on your computer now. You can open a run's output or stop a run. It was checked in a
terminal. Nobody has checked it in the Claude desktop app yet.

**`forge next`.** One sentence on where things stand, and the exact next step.

## Commands you will see

Your agent runs these. You see them in its messages.

| Command | What it does |
|---|---|
| `forge start "<idea>"` | Chooses a fix, a plan, discovery or the idea list |
| `forge next` | Says where things stand and gives the exact next step |
| `forge board` | Opens the live board page on your computer |
| `forge story new` | Starts a story and its plan |
| `forge read` | Runs a round of the cold read of a plan |
| `forge task start` | Starts one task of an approved story in its own branch and folder |
| `forge fix start` | Starts a small fix in its own branch and folder |
| `forge work` | Has the worker build a task or fix, or fix what the review found |
| `forge close` | Runs the review, waits for the tests, and marks the pull request ready |
| `forge merge` | Merges a ready pull request, when the repo lets the agent merge |
| `forge land` | Builds, closes and merges one change; `--all` merges every ready change |
| `forge test` | Runs the tests; `--change` runs the tests related to one change |
| `forge assign` | Gives a story or a task to a developer by GitHub username |
| `forge doctor` | Checks your setup and says how to fix each problem |

The [command list](docs/commands.md) has every command.

## Settings

`forge.toml` is the one settings file. Your agent keeps it: ask the agent to change a setting.
It holds the Forge version the repo uses, the test command, who merges (`merge`), which tools
the repo uses (`tools`: Claude, Codex or both), who builds (`workers`), the model and effort for
each kind of work, and the CI runner. The [guide](docs/guide.md) explains each one.

## Start a client prototype

Forge can also start a new app. `forge init --starter react` or `--starter python` creates an
app with sign-in, roles and a database, and no screens. The agent builds each screen in the
client's own design. A salesperson can lead the first steps and a developer can take over.
Follow the [prototype checklist](docs/start-a-prototype.md).

## Upgrade

Tell your agent "upgrade Forge". It runs `forge upgrade`, which installs the release, refreshes
Forge's files in the repo and opens a pull request for the upgrade. Each repo pins its Forge
version, and Forge prints the exact install line when yours does not match.

## Where it comes from

In April 2026 OpenAI published
[an open-source spec for Codex orchestration, Symphony](https://openai.com/index/open-source-codex-orchestration-symphony/)
([openai/symphony](https://github.com/openai/symphony)). The spec describes handing whole pieces
of work to agents. Symphony Forge is a working tool built on that idea. It runs with Claude Code
or Codex, keeps plans and state in the repo, and requires an approved plan, a code review and
passing tests before a change merges.

## Learn more

- [Forge guide](docs/guide.md): installing, the flow, workers and models, closing, merging,
  upgrading and releasing.
- [Command list](docs/commands.md): every command.
- [How Forge weighs a note](docs/review-rules.md): the scores, the bar and when a loop stops.
- [Standards](src/forge/standards.md): the engineering rules every worker follows.
- [Specs](docs/specs/): the designs behind how Forge behaves, starting with
  [Forge v1](docs/specs/lean-forge-v1.md).
- [Release notes](https://github.com/knacklabs/symphony-forge/releases): what changed in each
  release, and its known issues.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
