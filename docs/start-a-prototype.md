# Start a prototype

Follow these steps from an empty repository to a live customer demo. Your coding agent
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

## Open the repo and set up Forge

Run `git clone <repo-url>` with the URL you copied, open the new repo folder, then open your
agent there. Ask: “Run `forge init`, then `forge doctor --fix`.”
The second command installs the Codex SDK that Forge needs. If setup reports a problem,
ask the agent to follow its next step before continuing.

## Discover the customer's problem

Talk with the customer about the job they do today, their workaround, what it costs, who
feels it and how often. Tell the agent what you learned and ask it to record the discovery.
Choose the one task the demo should let the customer do from start to finish.

## Build and show the demo

Ask the agent to build the smallest working demo of that task. It builds, tests and gets
each demo round reviewed; ready prototype changes merge themselves. Open the demo with the
customer and tell the agent what to change in the next round.

## Put the demo online

When the agent says the repo is ready to connect, sign in to our deploy platform with your
own login: **[platform address: placeholder until the owner provides it]**. Connect the
GitHub repo, pick a subdomain and record the live address under `## Demo` as
`- Address: <url>` in `docs/product/BRIEF.md`. Open that address and check the demo loads;
if it does not, ask the agent to fix the deployment before showing the customer.

## Get sign-off

Show the live demo and confirm the required answers with the customer's named sign-off
person. Ask the agent to record the customer's approval, its date and where it happened,
the live demo address and the answers the customer approved. After sign-off, the repo's own
merge setting applies.
