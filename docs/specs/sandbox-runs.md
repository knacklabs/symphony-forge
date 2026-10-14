---
slug: sandbox-runs
title: Close and build rounds overflow to a remote sandbox when the laptop is full
status: confirmed
saved: 2026-10-14T12:56:04.895020+00:00
confirmed_by: "Ravi"
confirmed_hash: 50a346011262e96d8f4ea9b3fe1674be402c4861d6b4f45953c9cf03c1170d81
---

# Close and build rounds overflow to a remote sandbox when the laptop is full

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

1. **What moves: close first, then the whole worker.** Close's local test run and its review run in
   the sandbox first: they are the largest movable share of item time (local tests 10.7% and waits
   for the test lane 11.2%, against 7.8% for build rounds). Then Claude Code or Codex runs the full
   build round there too: it checks out the item's branch, edits, runs the worker's tests and commits.
   The coordinator and the cold reads stay on the laptop, and the laptop posts close's results to the
   pull request.
2. **GitHub access: Mainline pushes, with the team's GitHub App.** The sandbox holds no GitHub
   write credential. With Docker, the agent is in effect root on its machine, so it can read any
   token there. The sandbox gets the code without a write credential: the bundle Forge uploads, or a
   read-only clone through the App. At the end of a round the sandbox uploads its commits to Mainline
   as a git bundle. Mainline's worker checks the bundle: the item's own branch, only new commits on
   top of the round's start, and no changes to workflow files under `.github/workflows`. Then it
   pushes the bundle with a GitHub App installation token for that one repo, with contents and
   pull-request permissions and no workflows permission. The token never enters the sandbox. Mainline
   keeps a round's result until its push succeeds and Forge has fetched it; then it deletes it. If the
   checks refuse a bundle, Mainline pushes nothing and the item shows the reason in Needs you. Forge
   then collects the refused bundle into a local branch, where the developer reviews it and pushes it
   with their own GitHub access, or discards it; either choice clears the result.
3. **Model access: each tool's allowed sign-in.**
   **Claude:** Claude rounds use the team's own Anthropic API key, or the team's own Amazon Bedrock or
   Google Vertex credentials, from Mainline's vault, billed to the team. Anthropic lets a platform run
   the unmodified Claude Code CLI in hosted sandboxes, but does not let it collect, store or
   intermediate Claude.ai credentials or session tokens, so Mainline stores no Claude subscription
   token. The sandbox runs the Claude Code CLI itself in headless mode, not a harness built on the
   Agent SDK. Subscription plans stay on the laptop; the owner asks Anthropic about plans in sandboxes
   later.
   **Codex:** the developer signs in once with `codex login --device-auth` into Mainline's vault. This
   is a separate sandbox login, never a copy of the laptop's `~/.codex/auth.json`: a Codex refresh
   token works only once, and OpenAI says to use one `auth.json` for each runner or serialized stream.
   Mainline lends one login to one running sandbox at a time. The relay writes the refreshed file back
   to the vault each time Codex refreshes it, not only at the end. When a run ends without that
   write-back (for example a reclaimed sandbox), Mainline marks the login "sign in again" and never lends
   it again; the developer signs in once more with `codex login --device-auth`. A second Codex round at the same time needs a second sign-in, or it uses the team's
   OpenAI API key, or it waits. The ChatGPT security settings must allow device sign-in.
4. **When remote: only when the laptop is full.** Each kind of run follows its own line. Close's
   test run (with its review) goes to the sandbox when the laptop's test lane is full; a build round
   goes there when the agent line is full. With a free place, either runs locally. The sandbox has its
   own cap and size in `forge.toml` (2, 4 or 8 CPUs; default 2), separate from the laptop's lanes. When both
   the laptop and the sandbox cap are full, the run waits in its usual first-come line and says its
   place; it takes the next free place, local or remote. Mainline never queues a run: when the team has
   no free place it refuses with a plain reason, and the run stays in Forge's own line. Mainline shares
   a team's places fairly: each active developer has an equal slice of the team cap, and a slice
   nobody is using is lent to others. Lending never stops a running round: when the owner needs the
   slice back, no new borrowed run starts, and the owner gets the next place that frees.
5. **Mainline only, paid in credits.** Forge's sandboxes come only from Mainline. A team buys Mainline
   sandbox credits, priced at our cost plus a markup; Mainline runs them on its own backends (AWS
   first, others later), which teams never see or sign in to. It ships to every repo turned off. A
   repo turns it on in `forge.toml`, set by the agent in a fix after the owner agrees. Forge's own repo
   uses it first, then client repos on upgrade.

**Mainline, through Forge's own relay.** Forge puts its own small relay process in each sandbox,
and the laptop and the relay both connect out to the run's address on Mainline's relay gateway, so
the sandbox takes no inbound traffic. Nothing in a sandbox run polls: the relay drives Codex through
the app server's pushed JSON-RPC events and Claude Code through its streamed output, and the laptop
and the relay each hold a WebSocket to the gateway. The relay starts the worker, streams its
output, passes notes and questions both ways, stops it, keeps it running when the laptop disconnects,
and lets the laptop reattach later. So Mainline's API needs only five plain operations: create a
sandbox, copy files in and out, start one process, give that process an address on the relay gateway, and
delete the sandbox. Inside Mainline each backend is one small adapter for those five, so Mainline can
change backends without any change to Forge; Forge reads only the fields it uses from Mainline's
replies (principle 7). Pushing a finished round (item 2) is Mainline's own step, the same on every
backend.
Who may act on a run is one rule: any team member can watch it; only the
developer who started it sends it notes; the starter or an Owner can stop it. The relay forwards the
run's output to Mainline for the board and every pane. Each run has its own token, valid for that run
and its reconnects; removing a person from the team closes their sessions within a minute, while the
run keeps only the right to upload its own result.

**What goes up: committed code only.** The sandbox gets a git bundle of the item's branch and the
default branch and checks it out in a fresh history with no remote, so the worker can commit and
`forge test` finds where the branch left the default branch; its new commits come back in a bundle.
Files git ignores, such as `.env`, never go up, and neither does the laptop's `.git` folder (its
remotes, hooks and settings).

**Uncommitted work stays local.** A run goes to the sandbox only from a worktree with no uncommitted
changes; otherwise it waits for a laptop place and says why. A remote build round that ends with
changes it did not commit (for example when it is stopped or stuck) has them committed by the relay as
one "left over from round N" commit in its bundle, so the next round, local or remote, starts from them.
If the repo's own commit checks refuse that commit, the relay returns the changes as a patch instead;
the laptop applies the patch to the worktree as uncommitted changes, so the next round runs locally and
the worker sees why the commit was refused.

**Secrets come from Mainline's vault.** Each repo's secrets live in a per-repo vault in Mainline, owned
by the repo's team, the same store its deployed apps use: `forge secrets set NAME` writes one through
Mainline's API, and `forge secrets list` shows the names, never the values. Any team member sets `sandbox` secrets; only an Owner sets `dev` and `production` ones. Mainline injects them as
environment variables only for a run, so a teammate's remote run gets them too; the laptop keychain
holds only the Mainline token. The vault keeps each environment apart: sandbox runs read only the
repo's `sandbox` environment, never `dev`, `staging` or `production` values, and a deploy reads only its own
environment, so an agent's run can never see a production secret. At setup Forge reads the names
in the repo's `.env` and offers to move each value into the vault. `forge.toml` holds only the
on/off switch, the sandbox cap and size, the secret names a run needs, any extra outside hosts the
repo's tests call (sandboxes reach only allowed hosts, so each addition goes through a reviewed pull
request) and the Mainline team the repo belongs to, never a value; Mainline's dashboard shows them
read-only. `forge doctor` names any key the sandbox environment still lacks.
Setup links the repo to one Mainline team, and every run of that repo spends that team's credits. Each
laptop signs in to Mainline once: Forge opens the browser and gets the token through a redirect back
to a local port with PKCE. On a machine with no browser, the developer types a short device code
instead. The token lives in the system keychain; a person who is not a member of the repo's team cannot start its sandbox runs.

**Ready images and test services.** The repo's sandbox image is built once from its lockfiles and
the test setup in `forge.toml`, and the services its tests need (for example a Postgres or Redis
version, named in `forge.toml`) start inside the sandbox before the tests run. `forge doctor` runs one
check in a sandbox and reports what the repo still needs before rounds can move there. Each run gets
its own machine with Docker, used once and then removed, so integration and end-to-end tests that
start containers (for example with Docker Compose or Testcontainers) run in the sandbox as they do on
the laptop. Each image is
named by a hash of the repo's lockfiles, its test setup, its services in `forge.toml` and the repo's
pinned Forge release; when any of
them changes on the branch, the next remote run builds a new image, and the old one stays in use for
other branches until no run needs it. Forge sends the image's hash when it asks for a place; when
Mainline has no image for that hash, it says so, and Forge asks Mainline to build it from the bundle
first. The Mainline token stays on the laptop: the laptop starts and stops sandboxes; each run's relay
gets only a token for that run's own result upload. The sandbox never gets a GitHub write credential. `forge doctor` reports a missing or
expired Mainline sign-in and a token found in a tracked file.

**Forge relays every message.** The coordinator never talks to the sandbox agent directly; it runs
`forge work` as it does today. Inside the sandbox the relay runs Codex through the Codex app server,
as Forge does locally, and runs the Claude Code CLI in headless mode (item 3). Forge on the laptop connects to it through its
relay, so `forge work --note`, a worker's question, the live steps in the pane and
`forge stop` work exactly as for a local round, for Claude and Codex alike. Claude Remote Control is
not used.

**The round's result comes back whole.** At the end of a round the sandbox uploads two things to
Mainline: the git bundle and the worker's result, which is the same record a local round writes (done,
a question for the owner, or stuck, with its text). Mainline pushes the bundle (item 2). Forge on the
laptop fetches the branch and records the result exactly as for a local round, so `forge work --note`, Needs you and close work the same for local and remote rounds.

**CI results arrive as events.** For a repo on Mainline, GitHub sends check-run and status webhooks
to Mainline through the team's GitHub App (the App can read checks and commit statuses). Mainline
forwards them to Forge on the team's event stream, the same feed the board and every pane read. Close
first reads the commit's check state once, then waits for events; after a reconnect or a laptop wake
it reads the state once more, so checks that finished before close started or while the laptop slept
are never missed. Mainline asks GitHub to redeliver failed webhook deliveries. Close never asks GitHub
again and again. A repo not on Mainline keeps today's CI checks.

**No work is lost when a sandbox is reclaimed.** Mainline may run sandboxes on capacity that AWS can
take back with two minutes' notice. On that notice the relay commits the worker's changes as one
"left over from round N" commit (or a patch, as above), uploads the result and ends the round as
interrupted; the next round starts from those commits, on the laptop or in another sandbox. The relay
also uploads a checkpoint after every commit the worker makes and every 5 minutes: the commit bundle
plus a patch of every change not yet committed, new files included. So a sandbox that stops with no
notice loses at most 5 minutes of changes; Forge collects the latest checkpoint, applies its patch to
the worktree as uncommitted changes, and the next round starts from there. An interrupted close holds no code and simply runs
again. A sandbox that stops with no result or checkpoint counts as a failed round with the reason.

## The experience

Two people live with this: a developer, who runs Forge through Claude Code and wants her stories to
finish sooner without extra steps, and her team lead, who owns the Mainline team, its credits and the bill.

- **Meeting it.** When work waits for a free place on the laptop, `forge next` says how many runs are
  waiting and that sandbox runs could start them now, and the agent offers it once. On yes it walks
  the developer through signing in to Mainline (Forge opens the browser, or shows a short device code
  on a machine with no browser; the team's $5 starter credits arrive once an Owner adds a card or UPI mandate),
  moving the `.env` values
  into the vault, the sandbox model access (the team's Anthropic API key or cloud credentials for Claude, and `codex login --device-auth` for Codex), installing the team's GitHub App on the repo, the test services the repo needs, and one close in a sandbox; then a fix turns it on.
- **A team on one app.** Several developers' laptops share one Mainline team: its fair-share places,
  its result store and one live team board that Mainline hosts. The board shows Symphony's team view
  (in progress, needs whom, blocked, go-live) with every run on every laptop and sandbox, by person,
  and each developer's pane reads the same feed. A teammate's laptop runs appear there once that
  teammate signs in to Mainline; until then the board shows their work from git and GitHub only, the
  way Symphony's board does today, and marks them "not signed in". Mainline pushes each finished round at once, so a
  laptop that is asleep never blocks the team.
- **Teammates.** Nothing changes for a teammate until their laptop is full. Then the agent says the
  repo uses sandbox runs and asks them to sign in to Mainline and join the team, which keeps the token in
  that laptop's keychain. Without a sign-in their work stays local.
- **While a round runs.** The Forge pane's Machine tab shows a sandbox round as an ordinary row (live
  steps, `o` for output, `s` to stop) with an "in sandbox" tag and its minutes. Nothing new to learn.
  The item's "How it went" records the round as a sandbox round, with its minutes.
- **Starting.** Each run gets a fresh sandbox, used once and then removed, from the repo's ready
  image, which already has the tools and packages installed, on its own machine with Docker. A test
  command that installs packages itself still runs as written; it downloads them again until the team's
  package cache arrives in a later phase.
- **Cost.** Forge shows the minutes and credits used; buying credits, the balance and limits live on
  Mainline's dashboard, and the lead gets an email at 80% used and at zero.
- **Credits run out.** No new remote run starts at zero. Running rounds may go on for at most one more
  hour each; then Mainline stops them and Forge collects what they left. That overdraft is billed at the
  next top-up. New runs go back to the laptop's line, and the pane row says "Mainline credits used up"
  with where to top up.
- **When something fails.** If Mainline is down before a round
  starts, the round goes to the laptop's line by itself, and its pane row says why in one line. If a
  sandbox stops mid-round, Forge collects what it left and the next round runs on the laptop. If the
  laptop loses touch with a running sandbox, that item waits, with the reason in its row, until Forge
  has stopped the remote round or fetched its result; one item never runs two rounds at once.
  Other items keep using the laptop, so work never stops.
- **Laptop lid closed.** Rounds already running finish in the sandbox. The relay uploads each result
  (its bundle and record, or a patch) to Mainline's result store before the round ends, and Mainline
  then removes the sandbox. Mainline checks each bundle and pushes it at once. When the laptop wakes,
  Forge fetches the pushed branches and updates its records, and the pane says how many rounds
  finished. Fetching can be repeated safely. A patch, or the checkpoint a stopped sandbox left, waits
  until Forge collects it and applies it before the next round. A result stays until its push succeeds
  and Forge has fetched or collected it. Nothing is deleted before then: after 14 days, `forge next`
  names the waiting results, and only the team's own choice deletes one.
- **Turning it off.** A fix turns it off. Forge first lets running rounds finish (or stops them when
  the team asks). It waits until Mainline has pushed every finished round and Forge has fetched it, and
  it collects what stopped sandboxes left and every refused bundle into local branches. Only then does
  it delete the repo's sandboxes, images, caches and stored results in Mainline (the code copies), and it
  says what it removed. No commit is lost. The delete needs an Owner's Mainline sign-in; when a
  Developer turns it off, new runs stop and the delete waits for an Owner on Mainline's dashboard.

## Out of scope

- Running the coordinator or the cold reads in a sandbox.
- One shared Forge account for all repos.

## Acceptance criteria

1. With sandbox runs off (the default), nothing changes for new or existing repos.
2. With them on and the laptop's line full, and Mainline reachable with credits left, close's test run and review, and the next build round, run in the sandbox, with close's results posted to the pull request by the laptop, and Mainline pushes its commits with the team's GitHub App after it checks the bundle; with a free place, the round runs locally; with both full, it waits in line and takes the next free place; when Mainline is down or the team's credits are used up, new runs return to the laptop's line and say why; when credits are used up, running rounds may go on for at most one more hour each, then stop and are collected.
3. The sandbox gets only committed code (a bundle of the item's branch and the default branch, in a fresh history with no remote, where `forge test` runs), never an ignored file, the laptop's `.git` folder or a GitHub write credential; secrets reach it only from the repo's `sandbox` environment in the vault, never `dev` or `production` values, as environment variables for that run; Mainline refuses a bundle with commits outside the item's branch, commits that are not new on top of the round's start, or changes under `.github/workflows`, pushes nothing and shows the reason in Needs you; the App token that pushes covers that one repo, with contents and pull-request permissions and no workflows permission, and never enters the sandbox.
4. A sandbox run shows in the machine view with its minutes, credits used and output, and `forge stop` ends it.
5. The agent offers it when work waits for the laptop and sets it up with the developer (Mainline sign-in in the browser, with the token returned to a local port with PKCE, a device code only on a machine with no browser, and the token in the keychain; `.env` values moved into the vault; the sandbox model sign-ins; the team's GitHub App installed on the repo; test services; one close in a sandbox); `forge secrets` adds and lists vault entries without showing values; the repo's image and test services start in the sandbox and `forge doctor` reports what is missing; `forge.toml` never holds a token or secret value; `forge doctor` names any key the sandbox environment still lacks and any token in a tracked file; a Claude round runs the Claude Code CLI in headless mode with the team's own Anthropic API key or Bedrock or Vertex credentials from the vault, and Mainline stores no Claude subscription token; a Codex round uses that developer's separate `codex login --device-auth` login from the vault, lent to one running sandbox at a time and written back refreshed when the run ends; with no free plan login, a round uses the team's API key from the vault or waits; credits, balance alerts and top-ups live on Mainline's dashboard (FORGE-SANDBOX-3).
6. A remote round's question, stuck stop or failure reaches the laptop and shows in Needs you and `forge work` exactly as a local round's does; a reclaimed sandbox loses at most 5 minutes of a round's changes; Forge collects the checkpoint bundle and patch a stopped or reclaimed sandbox left and applies them before the next round, which starts from the last saved commits.
7. With the laptop asleep, running rounds finish and Mainline pushes them at once; on wake Forge fetches them and updates its records; Mainline deletes a result only after its push succeeds and Forge has fetched it, or after Forge has collected a refused result into a local branch or the developer discarded it; turning it off first waits until every round is pushed and fetched, and collects what stopped sandboxes left and every refused result, then, with an Owner's sign-in, deletes the repo's sandboxes, images, caches and results in Mainline and says what it removed; an item never runs two rounds at once, even when the laptop loses touch with a sandbox.
8. (FORGE-SANDBOX-3) On a team, each active developer gets an equal slice of the team's places, with unused slices lent and returned as the next place frees, never by stopping a running round; every member can watch any run's output, while only the starter can send notes, and the starter or an Owner can stop it; the team board and every pane show every run on every signed-in laptop and every sandbox, and mark teammates who are not signed in.
9. New repos start with it off at init; on upgrade and sync an existing repo keeps whatever its `forge.toml` says, so a repo that never set it stays off and an opted-in repo stays on, with nothing to migrate.
10. For a repo on Mainline, close waits for the CI check-run and status events that GitHub sends to Mainline through the team's GitHub App and that Mainline forwards on the team's event stream, and it does not ask GitHub again and again; a repo not on Mainline keeps today's CI checks; no part of a sandbox run polls: the relay drives Codex through the app server's pushed events and Claude Code through its streamed output, and the laptop and the relay hold WebSockets to the gateway.

## Roadmap

- FORGE-SANDBOX-1: Close runs in a Mainline sandbox when the laptop's test lane is full
- FORGE-SANDBOX-2: Build rounds run in a Mainline sandbox when the laptop's agent line is full
- FORGE-SANDBOX-3: A team shares sandbox places, one live team board and its credits

## Success measure

- Metric: items merged per day in Forge's own repo, and the share of item time spent waiting for a free place
- Baseline: items merged per day over 11 to 14 October 2026 (from git), and 17.5% waiting on the overload day
- Target: more items merged per day than the baseline with the same owner time, under 2% waiting, and no local test timeouts
- Check date: 2026-12-15
