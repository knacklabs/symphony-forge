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

So sandboxes help only when a team runs more at once than its laptop carries. That is the case Forge
is moving towards: `forge land --all` and parallel parts start more work together, and client teams
want many stories at once.

**Payback.** Build about 8 days.

| Case | Payback |
|---|---|
| Today's load, about 4 owner hours a month saved (measured) | Don't build: 16 months |
| An overload month like 11 October, about 40 hours saved (estimated) | Smallest slice first: 3.2 months |

The decision: plan it now and build when the trigger under "When to build" fires.

## Behaviour

The owner chose each of these on 14 October 2026:

1. **What moves: the whole worker.** Claude Code or Codex runs the full build round in the sandbox:
   it clones the branch, edits, runs the worker's tests and commits. The coordinator, the cold reads
   and close stay on the laptop.
2. **GitHub access: the laptop pushes.** The sandbox holds no GitHub credential. It returns its
   commits as a git bundle, and the laptop checks the bundle (the right branch, only new commits on
   top of the round's start) and pushes it.
3. **Model access: the owner's plan login.** The sandbox uses the Claude or ChatGPT plan login from
   the laptop. Before Forge relies on it, the spec's first part checks each plan's terms for use on a
   remote machine. Where the terms forbid it, the repo's own API keys are the fallback.
4. **When remote: only when the laptop is full.** A build round runs locally while the agent line has
   a free place. When the line is full, the next round goes to the sandbox instead of waiting. The
   sandbox has its own cap in `forge.toml`, separate from the laptop's half of the cores.
5. **Rollout: each repo's own provider account.** It ships to every repo turned off. A repo turns it
   on in `forge.toml` with its owner's own provider account and key, set by the agent in a fix after
   the owner agrees. Forge's own repo uses it first.

**Any provider.** Forge talks to one small interface: start a sandbox from an image, copy in the
branch, run the worker command, stream its output, copy out a bundle, stop. Each provider (Agent37,
or another later) is one adapter behind that interface. Forge reads only the fields it uses from the
provider's replies (principle 7).

**What the team sees.** The board's machine view and `forge lanes --json` show a sandbox run in its
own lane, with its provider, its elapsed time and its output. `forge stop` stops a sandbox run like a
local one. The item's "How it went" records the round as a sandbox round, with its minutes.

## Out of scope

- Running the coordinator, cold reads or close's review in a sandbox.
- Runs that continue while the laptop is off; the laptop pushes every round.
- One shared Forge account for all repos.

## Acceptance criteria

1. With sandbox runs off (the default), nothing changes for new or existing repos.
2. With them on and the agent line full, the next build round runs in the sandbox, and the laptop pushes its commits after it checks the bundle; with a free place, the round runs locally.
3. The sandbox never holds a GitHub credential, and a bundle with commits outside the round's branch is refused with the reason.
4. A sandbox run shows in the machine view with its provider, time and output, and `forge stop` ends it.
5. The repo turns it on and off in `forge.toml`; the plan-login terms check is recorded, with API keys as the fallback.

## When to build

Build when lane waits are above 10% of item time for a week, in Forge's own repo or in a client repo
that asks for it.

## Success measure

- Metric: share of item time spent waiting for a free place on the laptop
- Baseline: 17.5% on an overload day (11 October 2026), about 1% on normal days
- Target: under 2% on an overload day, with no local test timeouts (on the check date, review the trigger if it is not built yet)
- Check date: 2026-12-15
