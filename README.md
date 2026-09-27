# Symphony Forge

Forge takes a change from an idea to a merged pull request. An AI coding agent, Claude Code or
Codex, does the work: it plans, writes the code, runs the tests and gets it reviewed. You stay in
charge of the decisions: what gets built, which option to pick, and when it goes in.

A *pull request* is a proposed change to the code that gets checked before it is added.
*Merging* it is the moment the change becomes part of the real project.

## Where it comes from

In April 2026 OpenAI published
[*An open-source spec for Codex orchestration: Symphony*](https://openai.com/index/open-source-codex-orchestration-symphony/)
([openai/symphony](https://github.com/openai/symphony)). Its idea: the slow part of building with
AI agents was never the agents, it was people watching them. So stop supervising agent sessions
one by one and hand them whole pieces of work instead. The spec is a description of the idea, not
a tool.

Symphony Forge is that idea made into a working tool. It keeps the core (you assign work, agents
do it) and differs in three ways:

| | Symphony (the spec) | Symphony Forge |
|---|---|---|
| **Who runs it** | Codex only | Claude Code or Codex plans with you; Codex workers build |
| **Where the truth lives** | The issue tracker | The repo: plans, specs, decisions and each change's state |
| **Checks before a change goes in** | Left open on purpose | One approval of the plan, an automatic review and green tests on every change |

## Who it's for

- **Developers:** every change runs in its own branch, and it isn't ready until the tests pass
  and an automatic code review finds no serious problem. Nothing is committed straight to the
  main branch.
- **Product people who don't code:** you approve a short plan written in plain English, and
  follow progress on a simple board page instead of in code.
- **Vibe coders who build with AI:** you don't need to know git. Forge handles branches, commits
  and pull requests for your agent, and tells you the next step whenever you're unsure.

## How it works

1. **A short story doc.** The agent writes one short page: what changes for you, why, when it's
   done, and the tasks.
2. **One independent read.** A second AI agent, not the one that wrote the plan, reads it cold
   and points out problems. The plan is fixed once.
3. **You approve once.** Nothing is built until you say yes.
4. **The work runs on its own.** Each task gets its own branch (a separate line of work) and its
   own folder, so tasks don't get in each other's way. A Codex or Claude worker writes the code.
5. **Tests and review must pass.** An automatic code review runs, and the tests must be green.
   Only then is the pull request marked ready.
6. **A human merges.** You click merge. Forge blocks the agent from merging.

There are two sizes of change:

- **Story:** a bigger change, one that touches an interface or more than five code files. It gets
  the plan, the independent read and your approval.
- **Fix:** a small change. It needs only a one-line reason and a "done when", but still gets its
  own branch, the tests and the review.

## From idea to production

This is the whole path a piece of work takes, from a first conversation to running in
production. There is no separate prototype step: the first story is already the smallest version
the client can really use.

| Stage | What happens | Who | Where it's kept |
|---|---|---|---|
| 1. Find the problem | The agent interviews you (and, through you, the customer) about what really happens today, and writes it as a problem card: the job, today's workaround, what it costs, who feels it | Agent asks, you answer | `docs/product/DISCOVERY.md` |
| 2. Pick an option | Two to four options, always including "don't build" and "smallest slice", each with an estimate of when it pays back | Agent proposes, you choose | `forge spec payback` |
| 3. Write the spec | What it should do, how you'll know it worked, and what's out of scope. One independent read, then you confirm it | Agent writes, you confirm | `docs/specs/`, `forge spec save`, `forge read`, `forge spec confirm` |
| 4. Client sign-off | In a client's repo, no story can be approved until the client's sign-off is recorded | Client and you | `forge decision new client-signoff`, `forge decision accept` |
| 5. Plan the stories | The spec becomes stories on the roadmap, the smallest usable slice first, with no setup-only stories | Agent plans, you approve each story once | `plans/roadmap.json`, `forge roadmap add`, `forge story new` |
| 6. Build | Each task runs in its own branch and folder, built by a Codex worker (or Claude, if the project chooses) with its tests | Agent | `forge task start`, `forge work` |
| 7. Check | An automatic review plus green tests; anything serious goes back to the worker | Agent | `forge close` |
| 8. Ship | The pull request is merged, and the change goes out through your project's own deployment | You merge | GitHub |
| 9. Close the loop | The story gets a one-line outcome, and on the spec's check date its success measure is measured and recorded | Agent, with your numbers | `forge story done`, `forge spec measure` |

A small change is a fix: it gets a short version of stage 1 (at most two questions), then goes
straight to build, check and ship.

## What you do vs what the agent does

You do three things:

- **Approve** a story's plan.
- **Choose** between options when the agent asks.
- **Merge** the finished pull request.

The agent does everything else: the plan, the code, the tests, fixing what the review finds, and
keeping Forge's settings file up to date.

Not sure where things stand? Run `forge next`, or just ask your agent "what's next?". It says
where things are in one sentence and gives the exact next step.

## Get started

### What you need

- **git**, which keeps track of changes.
- **GitHub CLI** (`gh`), signed in with `gh auth login`.
- **uv**, a tool that installs Python programs. Get it from
  [docs.astral.sh/uv](https://docs.astral.sh/uv/).
- **Python 3.11** or later. uv can install it for you.
- **Claude Code and Codex.** You talk to either one. Forge uses the other one for the
  independent read.

### Install

```sh
uv tool install --python 3.11 "git+https://github.com/knacklabs/symphony-forge@v1.0.2"
```

Check it worked with `forge --version`. Each project pins the Forge version it uses, and Forge
prints the exact install line if yours doesn't match.

### Set up a project

- **A new project:** create an empty repository on GitHub (no files yet), clone it, and run
  `forge init` inside it. It writes Forge's settings, a starter docs folder and the agent
  instructions, makes the first commit and protects the main branch.
- **A project with an older, copied-in Forge:** run `forge migrate`. It moves you over in one
  pull request.
- **Every new copy of a project on your machine:** run `forge sync` once, then `forge doctor` to
  check your setup. Doctor prints a fix for each problem it finds.

### Start working

Open Claude Code or Codex in the project and ask "what's next?", or run `forge next` yourself.
Then describe the change you want.

## Commands you'll see

Your agent runs these for you. You'll see them in its messages.

| Command | What it does |
|---|---|
| `forge next` | Says where things stand and gives the exact next step |
| `forge board` | Opens a plain-English page showing the work and its progress |
| `forge story new` | Starts a new story and its plan |
| `forge read` | Runs the one independent read of a plan |
| `forge task start` | Starts one task of an approved story in its own branch and folder |
| `forge fix start` | Starts a small fix in its own branch and folder |
| `forge work` | Has the worker build a task or fix, or fix what the review found |
| `forge close` | Runs the review, waits for the tests, and marks the pull request ready |
| `forge doctor` | Checks your setup and says how to fix each problem |

The full command list is in the [Forge guide](docs/guide.md#commands).

## Learn more

- [Forge guide](docs/guide.md): installing, every command, the two sizes of change, closing,
  upgrading and releasing.
- [Standards](src/forge/standards.md): the engineering rules every worker follows.
- [Specs](docs/specs/): the detailed designs behind how Forge behaves, starting with
  [Forge v1](docs/specs/lean-forge-v1.md).
