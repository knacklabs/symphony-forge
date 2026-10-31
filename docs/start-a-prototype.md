# Start a prototype

Follow these steps from an empty repository to client sign-off and the first production release. Your coding agent
handles the code, tests and review; you bring the customer's problem and decisions.

## GitHub seat and repo

Ask your team for a GitHub seat. Create a new, empty repository on GitHub without a README,
then use its **Code** button to copy the repo URL. Keep it for step 4.

## Set up your laptop

On a Mac, open Terminal and run:

```sh
curl -fsSL https://raw.githubusercontent.com/knacklabs/symphony-forge/main/scripts/install-mac.sh | bash
```

On Windows, open PowerShell and run:

```powershell
irm https://raw.githubusercontent.com/knacklabs/symphony-forge/main/scripts/install-windows.ps1 | iex
```

The script checks your tools, installs what is missing and prints the next step. On Windows,
Docker Desktop needs WSL2, administrator rights and one restart; follow the script's prompts.
If a step fails, read the message, complete the named action and run the same line again.

## Sign in to an AI coding agent

Open Claude Code or Codex and sign in with your account. You can use either one to talk to
Forge.

## Sign in to GitHub

In Terminal or PowerShell, run `gh auth login` and choose the browser login. Finish the
sign-in in your browser before continuing. `forge init` pushes the first commit and protects
the default branch on GitHub, so the GitHub command-line tool needs your login first.

## Open the repo and set up Forge

Run `git clone <repo-url>` with the URL you copied, open the new repo folder, then open your
agent there. Ask: “Run `forge init`, then `forge doctor --fix`.”
The second command installs the Codex SDK that Forge needs. If setup reports a problem,
ask the agent to follow its next step before continuing.

If `forge init` already stopped after its first commit, do not run `forge init` again: it
requires an empty repo. Sign in with `gh auth login`, then ask the agent to push that
existing commit, run `forge sync` to install the hooks and finish branch protection using
`gh api` (or Forge's printed `Next:` command, if it gave one). Then run `forge doctor --fix`.

## Discover the customer's problem

Talk with the customer about the job they do today, their workaround, what it costs, who
feels it and how often. Tell the agent what you learned and ask it to record the discovery.
Choose the one task the demo should let the customer do from start to finish.

## Build and show the demo

Start with a canvas of the screens. You or the FDE approve it before a build. The customer
can sign off on the canvas alone. A working demo needs an FDE request to prove something
the canvas cannot, and the owner's accepted prototype-build decision. Follow the
[client project steps](guide.md#a-new-client-project). Skip the online demo step for a canvas-only sign-off.

After that acceptance, ask the agent to build the smallest working demo of that task. It builds, tests and gets
each demo round reviewed; ready prototype changes merge themselves. Open the demo with the
customer and tell the agent what to change in the next round.

## Put the demo online

Ask your team administrator for Mainline access and its current sign-in link. Resolve access
before this step. This guide does not provide a public platform address.

Tell your coordinating agent: "Deploy this app to dev on Mainline." The agent checks for the
Mainline Deploy plugin and follows its install and sign-in steps when needed. Finish sign-in
with your own account. Confirm the app, repo and dev environment. After the one-time setup,
Mainline deploys dev at each merge and makes a preview for each pull request.
Record the live address under `## Demo` as `- Address: <url>` in `docs/product/BRIEF.md`.
Open that address and check the demo loads before you show the customer.

## Get sign-off

Show the approved canvas or requested live demo and confirm the required answers with the customer's named sign-off
person. First ask the agent to run the [sign-off checks](guide.md#a-new-client-project).
The canvas check needs Codex even when Claude builds and reviews code. After the checks pass,
ask for the customer's approval. Ask the agent to record that approval, its date and where it happened,
the canvas or live demo address and the answers the customer approved. After sign-off, the repo's own
merge setting applies.

## Who does what

- The FDE (forward deployed engineer) learns the customer's job, records answers, shows the
  canvas or demo and coordinates delivery. A salesperson can start, then hand over to a developer.
- The owner chooses scope, accepts decisions and approves stories. The owner merges after
  sign-off unless the repo permits agent merges.
- The customer's named sign-off person approves the design and answers for the customer.
  Agree who can authorize the production release, too.
- The coordinating agent runs Forge. Workers build and commit changes, but never deploy.
- The platform administrator provides access, domains and environment setup. Name the person
  responsible for production support, alerts, backups and recovery before release.

## Prepare the first production release

Client sign-off approves the product direction. It does not prove production readiness.
After sign-off, plan and build the remaining production work through stories and reviewed
pull requests. Follow this checklist before the first Promote:

1. Confirm the production host, account owner, region, domain, budget and release approver
   with the client. Record the decisions in the repo. Keep secrets out of the repo.
2. Confirm production access and secrets in the host, HTTPS and DNS for the real domain,
   database access and migrations, and the external services the app needs.
3. Check the release in a non-production environment. Confirm the full test run is green,
   the customer's main task works, and sign-in and permissions work for each role.
4. Confirm a current database backup and a demonstrated restore. Record who can restore it,
   the recovery steps and the rollback plan for the app and migrations.
5. Confirm health checks, error alerts and the support contact. Agree the release time and
   any data import or downtime with the client.
6. Ask the authorized person to press Promote in Mainline. An agent or worker never promotes
   production. Check the production address and the customer's main task after release.
   If a check fails, use the agreed rollback plan and notify the support contact.

## Use the client's cloud or servers

Confirm this choice before deploy setup. Mainline's deployment path does not imply support
for an arbitrary client cloud account or server. Ask the platform administrator to confirm
whether Mainline supports the requested target.

If it does, follow the Mainline plugin's setup for that target. If it does not, record the
client's host and constraints, then plan the required deploy work as a story. Name who owns
the server, network access, secrets, certificates, database, backups, alerts and release.
Use the client's approved release process and the production checklist above. There is no
Mainline Promote step on a host that does not use Mainline. Do not invent an install command
or change the hosting choice without the client's decision.
