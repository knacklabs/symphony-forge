# Symphony Forge

Forge takes a change from an idea to a merged pull request. An AI coding agent, Claude Code or
Codex, does the work: it plans, writes the code, runs the tests and gets it reviewed. You stay in
charge of the decisions: what gets built, which option to pick, and when it goes in.

A *pull request* is a proposed change to the code that gets checked before it is added.
*Merging* it is the moment the change becomes part of the real project.

[![Highlights from the explainer; tap to watch it with sound](https://github.com/knacklabs/symphony-forge/releases/download/v1.1.0/forge-explainer-preview.webp)](https://github.com/user-attachments/assets/1a7ec040-190e-4c14-9671-c2271ecedbf7)

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
- **Salespeople starting a prototype:** follow the [Start a prototype](docs/start-a-prototype.md)
  checklist from an empty repo to a live customer demo.

## How it works

After a new client's prototype is signed off, each story follows this loop:

1. **A short story doc.** The agent writes one short page: what changes for you, why, when it's
   done, and the tasks.
2. **One independent read.** A second AI agent, not the one that wrote the plan, reads it cold
   and points out problems. The plan is fixed once.
3. **You approve once.** Nothing is built until you say yes.
4. **The work runs on its own.** Each task gets its own branch (a separate line of work) and its
   own folder, so tasks don't get in each other's way. A Codex or Claude worker writes the code.
5. **Tests and review must pass.** An automatic code review runs, and the tests must be green.
   Only then is the pull request marked ready.
6. **It merges.** Before client sign-off, the agent merges ready prototype changes. After
   sign-off, you click merge by default. Set `merge = "agent"` in the project's `forge.toml`
   if you want the agent to run `forge merge` for each ready change instead.

There are two sizes of change:

- **Story:** a bigger change, one that touches an interface or more than five code files. It gets
  the plan, the independent read and your approval.
- **Fix:** a small change. It needs only a one-line reason and a "done when", but still gets its
  own branch, the tests and the review.

## How Forge weighs a note

Two checks read your work before Forge ships it. The **cold read** reads the plan of a story
before you approve it. The **code review** reads each change before it merges. Both checks use
the same three scores and the same bar. Thus Forge judges a plan note and a code review note in the
same way.

### Three scores

The reader gives each note three scores from 1 to 5. The scores are a judgement. They are not a
measurement.

| Score | 1 | 3 | 5 |
|---|---|---|---|
| **Gain**: how much the fix helps | the words of a sentence, or a rare case that no one named | one case that the "Done when" names does not work | security, data loss, or the main case of a "Done when" does not work |
| **Work**: how much the fix costs | one line, no new test | one file and one test, less than one hour | a new module, a different platform, or a migration |
| **Harm**: what breaks if the problem stays | no part breaks, and a revert removes the change | a change that people can see, and a revert removes it | a change that you cannot reverse: data, a migration, or a release that clients install |

A note about security, data loss or a migration always gets Harm 4 or more. Forge sets this
floor if the reader gave a lower Harm. Forge shows the reason, for example
`Harm 4 (floor: security)`.

### The bar

| When | What occurs |
|---|---|
| Harm 4 or 5, or Gain 5 | The note stops the work. The worker fixes it now. |
| Gain 3 or 4, and Work 1 or 2 | The worker fixes it in this round. |
| Gain 3 or 4, and Work 3 or more | The note becomes a follow-up fix. The work continues. |
| Gain 1 or 2 | Forge keeps the note in its record and does not fix it. |
| Harm 3, and the note adds new scope or reverses your decision | The agent asks you. |

A Gain 1 or 2 note never stops the work. This is true also when the reader calls the note
serious. Only Harm 4 or more can stop the work for such a note.

### Who decides

- **The reader gives the scores.** The worker and the agent do not change a score.
- **Forge applies the bar.** A plan passes its read, and a change is ready to merge, when no
  note is at the bar.
- **The agent decides small items.** The agent decides each note with Harm 1 or 2 that a revert
  can remove. Then the agent tells you.
- **You decide the other items.** The agent asks you about Harm 3 or more, about new scope
  outside the approved "Done when", about your approval and merge steps, and about a change to a
  decision that you made.

### Forge keeps each note, and a settled note does not come back

- **Forge keeps each note below the bar.** The read notes, the pull request and the record of
  the item on the default branch show each note with its scores. Thus you can find a known
  problem when a bug occurs later.
- **A settled note stays settled.** You, the agent or Forge can settle a note. Each later read
  and review gets the settled note as known and accepted. A reader can show the note again only
  with new evidence of harm.
- **The cold read gives its decisions to the code review.** If you accepted a plan note, the
  code review does not show that note again.

### When a loop stops

Forge stops a change after three rounds only in two conditions:

1. A note at the bar comes back.
2. A note with Harm 3 or more is open.

Then Forge asks you a question. The question shows the open notes in one table, in the order of
their scores. A note that an earlier release saved has no scores; then the question shows
the notes as plain lines. It tells you the result of accept, of narrow, and of split.

If you do not answer a code review stop in 30 minutes, Forge can narrow the change. Forge does
this only when each open note has Harm 1 or 2. A repo can set `stop_default = "off"` in
`forge.toml`. Then Forge always waits for you.

The code review also stops at the third note in one area. An area is one function, or one
file when the note is outside a function. The question names the area and proposes one
structural change: cut the code, use one general rule, narrow that "Done when" item, or make the
code fail closed. After your answer, a new note in that area stops the work only when it is at
the bar and has Harm 3 or more.

A note from an earlier release of Forge has no scores. Forge judges that note as before, until
the next read or review gives new scores.

### Three examples

1. **"The default test selection of close breaks Go repos."** Gain 3, Work 4, Harm 2. The fix
   helps, but it needs the tools of a different language. The note becomes a follow-up fix, and
   the change merges.

2. **"The migration removes a column that contains data."** The reader gave Harm 2. Forge sets
   Harm 4 (floor: migration). The note stops the merge until the worker fixes it.

3. **"This sentence in the plan is not clear."** Gain 1, Work 1, Harm 1. Forge keeps the note in
   the read notes and does not fix it. The plan goes to you for approval.

## From idea to production

This is the path for a new client project, from the first conversation to running in production.
The agent starts as a forward deployed engineer (FDE): it learns the customer's problem and
builds the smallest working prototype that tests it. A salesperson can start this work; a
developer can take over using the discovery notes and answers page. To start one, follow the
[prototype checklist](docs/start-a-prototype.md).

| Stage | What happens | Who | Where it's kept |
|---|---|---|---|
| 1. Find the problem | The agent interviews you (and, through you, the customer) about what really happens today, and writes it as a problem card: the job, today's workaround, what it costs, who feels it | Agent asks, you answer | `docs/product/DISCOVERY.md` |
| 2. Pick an option | Two to four options, always including "don't build" and "smallest slice", each with an estimate of when it pays back | Agent proposes, you choose | `forge spec payback` |
| 3. Build the prototype | The agent asks each question when it first affects the build, records the answer and who gave it, confirms specs as they emerge, and builds the smallest working slice through fixes | Agent, with you and the customer | `docs/product/BRIEF.md`, `docs/specs/`, `forge spec save`, `forge read`, `forge spec confirm`, `forge fix start`, `forge work`, `forge close` |
| 4. Demo and review | The customer tries the prototype; a strict review checks the whole prototype and its answers before sign-off | Client and agent | Demo address, `forge decision accept` |
| 5. Client sign-off | The customer's named person approves the demo and answers; no client story or roadmap entry can be created before this | Client approves, agent records | `forge decision new client-signoff`, `forge decision accept` |
| 6. Plan the stories | Start from a problem in the plan's Why; the story's branch adds it to the roadmap. Specs stay optional. Build the smallest usable slice first, with no setup-only stories | Agent plans, one story read loop and one approval | `forge story new`, or `forge roadmap add` for a confirmed spec |
| 7. Build | Each task runs in its own branch and folder, built by a Codex worker (or Claude, if the project chooses) with its tests | Agent | `forge task start`, `forge work` |
| 8. Check | An automatic review plus green tests; anything serious goes back to the worker | Agent | `forge close` |
| 9. Ship | The pull request is merged, and the change goes out through your project's own deployment | You merge, or the agent if you allow it | GitHub, `forge merge` |
| 10. Close the loop | The last task's merge records the story's outcome, and on the spec's check date its success measure is measured and recorded | Agent, with your numbers | `forge merge --outcome`, `forge spec measure` |

Before sign-off, the prototype uses fixes even when the work is larger than an ordinary fix.
Each still goes through tests, review and a pull request. The agent confirms specs during this
work, then adds them to the roadmap after sign-off.
See [decision 0095](docs/decisions/0095-prototype-before-stories.md) for why this order replaces
the earlier roadmap-before-sign-off order.

## What you do vs what the agent does

You do three things:

- **Approve** a story's plan.
- **Choose** between options when the agent asks.
- **Merge** the finished pull request after client sign-off, unless you let the agent do it
  (`merge = "agent"`). The agent merges ready prototype changes before sign-off.

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
uv tool install --python 3.11 "git+https://github.com/knacklabs/symphony-forge@v1.2.12"
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

### Upgrade a project

Tell your agent "upgrade Forge". It asks which release, recommending the newest, then runs
`forge upgrade <release>` from the main branch with nothing uncommitted. That one command
installs the release, has it refresh Forge's files for Claude Code and Codex (your own text and
settings stay), and opens the upgrade's pull request, which merges like any other change. If it
stops, its `Next:` line says what to do; running it again picks up where it stopped.

### Start working

Open Claude Code or Codex in the project and ask "what's next?", or run `forge next` yourself.
Then describe the change you want.

## Contributing

Clone this repository, then run `uv sync` and `uv run pytest` to run the tests. The Codex SDK is
not needed for the tests. Start fixes with `forge fix start "<why>" --done "<done when>"` so the
pull request uses a Forge branch; the pull-request check accepts only Forge branches.

Forge's own CI balances its test groups using the committed `.test_durations` file.
Refresh it from the repository root after changes to slow tests:

```sh
uv run --python 3.11 pytest tests -q -n auto -o faulthandler_timeout=120 --timeout=150 --timeout-method=thread --store-durations --clean-durations
```

Commit the refreshed file after the full run passes. Check the latest CI run on all three
platforms: each group, including setup, must finish within seven minutes on Ubuntu and macOS,
and fourteen minutes on Windows (70% of its job limit). These settings affect only Forge's
own repository; new and existing client repositories get no change.

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
| `forge merge` | Merges a ready pull request, when the project allows the agent to merge |
| `forge ask` | Asks Codex a quick read-only question about the code |
| `forge doctor` | Checks your setup and says how to fix each problem |

The full command list is in the [Forge guide](docs/guide.md#commands).

## Learn more

- [Forge guide](docs/guide.md): installing, every command, the two sizes of change, closing,
  upgrading and releasing.
- [Standards](src/forge/standards.md): the engineering rules every worker follows.
- [Specs](docs/specs/): the detailed designs behind how Forge behaves, starting with
  [Forge v1](docs/specs/lean-forge-v1.md).
