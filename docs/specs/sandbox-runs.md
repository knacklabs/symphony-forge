---
slug: sandbox-runs
title: Build rounds overflow to a remote sandbox when the laptop is full
status: draft
saved: 2026-10-14T05:18:47.231672+00:00
---

# Build rounds overflow to a remote sandbox when the laptop is full

## Why

A coordinator's laptop is the limit on how much Forge can build at once. Forge gives agents half the
cores and the test lane one place, so work past that waits in line. On 11 October 2026 Forge's own
repo ran more work than one laptop carries: load reached 211, local tests timed out, and items waited
107 hours in total for a free place (17.5% of all item time). The median item took 10.3 hours.

Since 12 October the same repo runs fewer things at once, and the waits fell to about 1% of item time
(median item 1.9 hours). Measured over 86 items from 11 to 14 October:

| Where item time went | Share |
|---|---|
| Not recorded (native Claude builds, coordinator time, gaps) | 44% |
| Waiting for a free place on the laptop (almost all on 11 October) | 17.5% |
| Local tests in close | 11% |
| Waiting for the owner | 9.5% |
| Waiting for CI | 8% |
| Fixing review findings | 6.5% |
| Review and first build | 3% |

These waits understate the cost. After 11 October the coordinator held work back so the laptop
would cope: it closed items one at a time and started fewer builds together. That shows up as work
that never started, not as time in line. More places in sandboxes let independent work run at once
again: stories in different areas, fixes and client repos. Within one story, plan order and parts
that edit the same files still set the pace, and so do CI runners, model rate limits and the owner's
approvals.

**Payback.** Build about 8 days.

| Case | Payback |
|---|---|
| Today's held-back load, about 4 owner hours a month saved (measured) | Don't build: 16 months |
| Running independent work at once again, about 40 hours a month saved (estimated) | Smallest slice first: 3.2 months |

The owner chose to build it in full now (14 October 2026).

## Behaviour

The owner chose each of these on 14 October 2026:

1. **What moves: the whole worker.** Claude Code or Codex runs the full build round in the sandbox:
   it gets the item's whole working folder, edits, runs the worker's tests and commits. The coordinator, the cold reads
   and close stay on the laptop.
2. **GitHub access: the laptop pushes.** The sandbox holds no GitHub credential. It returns its
   commits as a git bundle, and the laptop checks the bundle (the right branch, only new commits on
   top of the round's start) and pushes it.
3. **Model access: the owner's plan login.** Forge carries the laptop's current Claude or ChatGPT
   plan login into each run and wipes it when the run ends, so nobody signs in again. Before Forge relies on it, the first part of the work checks each plan's terms for use
   on a remote machine. Where the terms forbid it, the repo's own API keys are the fallback.
4. **When remote: only when the laptop is full.** A build round runs locally while the agent line has
   a free place. When the line is full, the next round goes to the sandbox instead of waiting. The
   sandbox has its own cap in `forge.toml`, separate from the laptop's half of the cores. When both
   the laptop and the sandbox cap are full, the round waits in the same first-come line and says its
   place; it takes the next free place, local or remote.
5. **Rollout: each repo's own provider account.** It ships to every repo turned off. A repo turns it
   on in `forge.toml`, set by the agent in a fix after the owner agrees. Forge's own repo uses it
   first, then client repos on upgrade.

**Any provider.** Forge talks to one small interface: start a sandbox from an image, copy in the
branch, run the worker command, stream its output, copy out a bundle, stop. Each provider (Agent37,
or another later) is one adapter behind that interface. Forge reads only the fields it uses from the
provider's replies (principle 7).

**What goes up and what stays.** The sandbox gets the item's working folder, including files git
ignores, such as `.env`, so tests that need local settings work there too. Three things never go up:
the laptop's `.git` folder (its remotes, hooks and settings); instead the sandbox gets a fresh git history made from a bundle of the item's branch, with no remote, so the worker can commit, and its new commits come back in a bundle, any file setup finds holding a GitHub
credential or a model login, and any path the team lists in `forge.toml` to never send. Setup lists
every ignored file it will send and every file it leaves out, with the reason, before the team says
yes; other real keys in ignored files do reach the provider, and setup says so. `forge.toml` holds
only the provider's name, the sandbox cap, the never-send paths and the name of the place the
provider key lives (an environment variable or the system keychain entry), never a key. The provider
key stays on the laptop: the laptop starts and stops sandboxes. The sandbox never gets a GitHub
credential. `forge doctor` reports a provider key that is missing or found in a tracked file.

**Forge relays every message.** The coordinator never talks to the sandbox agent directly; it runs
`forge work` as it does today. Inside the sandbox the worker runs under the same driver Forge uses
locally (the Claude Agent SDK or the Codex app server). Forge on the laptop connects to it through the
provider's command stream, so `forge work --note`, a worker's question, the live steps in the pane and
`forge stop` work exactly as for a local round, for Claude and Codex alike. Claude Remote Control is
not used.

**The round's result comes back whole.** At the end of a round the sandbox returns two things: the
git bundle and the worker's result, which is the same record a local round writes (done, a question
for the owner, or stuck, with its text). The laptop records that result exactly as for a local round,
so `forge work --note`, Needs you and close work the same for local and remote rounds. A sandbox that
stops without a result counts as a failed round with the reason, and the next round can run.

## The experience

Two people live with this: a developer, who runs Forge through Claude Code and wants her stories to
finish sooner without extra steps, and her team lead, who owns the provider account and the bill.

- **Meeting it.** When work waits for a free place on the laptop, `forge next` says how many runs are
  waiting and that sandbox runs could start them now, and the agent offers it once. On yes it walks
  the developer through choosing a provider, adding the key to the keychain, the list of ignored
  files that will go up, and one test run; then a fix turns it on.
- **Teammates.** Nothing changes for a teammate until their laptop is full. Then the agent says the
  repo uses sandbox runs and asks for the team's provider key, which it keeps in that laptop's
  keychain. Without a key their work stays local.
- **While a round runs.** The Forge pane's Machine tab shows a sandbox round as an ordinary row (live
  steps, `o` for output, `s` to stop) with an "in sandbox" tag and its minutes. Nothing new to learn.
  The item's "How it went" records the round as a sandbox round, with its minutes.
- **Starting fast.** The first run installs what the repo needs from its lockfiles and the test
  setup in `forge.toml`; the provider keeps that sandbox's disk, so later rounds start in seconds.
- **Cost.** Forge shows the minutes used; spending limits live in the provider's own dashboard.
- **When something fails.** If the provider is down or its spending limit is reached before a round
  starts, the round goes to the laptop's line by itself, and its pane row says why in one line. If a
  sandbox stops mid-round, Forge collects what it left and the next round runs on the laptop. If the
  laptop loses touch with a running sandbox, that item waits, with the reason in its row, until Forge
  has stopped the remote round or collected its result; one item never runs two rounds at once.
  Other items keep using the laptop, so work never stops.
- **Laptop lid closed.** Rounds already running finish in the sandbox, and their results wait at the
  provider. When the laptop wakes, Forge collects, checks and pushes them, and the pane says how many
  rounds it collected.
- **Turning it off.** A fix turns it off. Forge first collects and pushes every finished round, and
  lets running rounds finish (or stops them when the team asks) and collects them too. Only then does
  it delete the repo's sandboxes and their disks at the provider (the code copy and any `.env`), and it
  says what it removed. No commit is lost.

## Out of scope

- Running the coordinator, cold reads or close's review in a sandbox.
- Pushing while the laptop is asleep; results wait at the provider until it wakes.
- One shared Forge account for all repos.

## Acceptance criteria

1. With sandbox runs off (the default), nothing changes for new or existing repos.
2. With them on and the agent line full, and the provider reachable, the next build round runs in the sandbox, and the laptop pushes its commits after it checks the bundle; with a free place, the round runs locally; with both full, it waits in line and takes the next free place; when the provider fails or its limit is reached, the round returns to the laptop's line and says why.
3. The sandbox never holds a GitHub credential or the laptop's `.git` folder (it commits in a fresh history made from a bundle of the item's branch, with no remote), setup leaves out files holding a GitHub credential or a model login and says which, and a bundle with commits outside the round's branch is refused with the reason.
4. A sandbox run shows in the machine view with its provider, time and output, and `forge stop` ends it.
5. The agent offers it when work waits for the laptop and sets it up with the developer (provider, key in the keychain, the ignored files that will go up, a test run); `forge.toml` names where the key lives and never holds a key; `forge doctor` reports a missing key or one in a tracked file; the plan-login terms check is recorded, with API keys as the fallback.
6. A remote round's question, stuck stop or failure reaches the laptop and shows in Needs you and `forge work` exactly as a local round's does.
7. With the laptop asleep, running rounds finish and their results wait; on wake Forge collects, checks and pushes them; turning it off first collects every round, then deletes the repo's sandboxes and disks at the provider and says what it removed; an item never runs two rounds at once, even when the laptop loses touch with a sandbox.
8. New repos start with it off at init; on upgrade and sync an existing repo keeps whatever its `forge.toml` says, so a repo that never set it stays off and an opted-in repo stays on, with nothing to migrate.

## Success measure

- Metric: items merged per day in Forge's own repo, and the share of item time spent waiting for a free place
- Baseline: items merged per day over 11 to 14 October 2026 (from git), and 17.5% waiting on the overload day
- Target: more items merged per day than the baseline with the same owner time, under 2% waiting, and no local test timeouts
- Check date: 2026-12-15
