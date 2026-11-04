Buy a Claude plan that includes Claude Code for the person.
Invite the person to the company GitHub organization with permission to create private repositories.
Fill in the company and developer details in the text below.

# Start with Claude

Give the person this text to paste into Claude Code:

> Follow https://github.com/knacklabs/symphony-forge/blob/main/docs/start.md.
> My company GitHub is https://github.com/COMPANY.
> My developer is NAME, GitHub LOGIN, contact CONTACT.
> Help me set up this computer, then ask for my idea or client notes.
> Use plain words and do the technical steps for me.

## Instructions for Claude

Follow this page as instructions for you, not as a command list for the person.
Keep the company and developer details in the project's notes after setup.
Explain each step in one short sentence. Ask the person only for a choice or a sign-in you cannot complete.

Check each installed tool before you install it. Use the computer's tools where possible.
Install only git, GitHub CLI (`gh`), uv, Forge, and Node.js with npm for the browser-only web app.
Forge supplies the design skills.
Do not install Docker, a test browser, Codex, a server, or a database for this first step.

### Mac

1. Run `git --version`. If git is absent, run `xcode-select --install` and guide the person through Apple's dialog.
2. Run `gh --version`. If absent, get the macOS package for this Mac from [GitHub CLI releases](https://github.com/cli/cli/releases/latest).
   Guide the person through the package installer. Homebrew is not required.
3. Run `uv --version`. If absent, use the [official uv installer](https://docs.astral.sh/uv/getting-started/installation/):

   ```sh
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

4. Run `node --version` and `npm --version`.
   If absent, get the Mac `.pkg` installer from [Node.js downloads](https://nodejs.org/en/download).
   Choose the long-term support release for this Mac. Guide the person through the installer.

### Windows

Use PowerShell for these steps.

1. Run `git --version`. If absent, install Git from [Git for Windows](https://git-scm.com/install/windows).
2. Run `gh --version`. If absent, use the [GitHub CLI Windows installer](https://github.com/cli/cli/releases/latest), or run:

   ```powershell
   winget install --id GitHub.cli --exact
   ```

3. Run `uv --version`. If absent, use the [official uv installer](https://docs.astral.sh/uv/getting-started/installation/):

   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

4. Run `node --version` and `npm --version`.
   If absent, get the Windows `.msi` installer from [Node.js downloads](https://nodejs.org/en/download).
   Choose the long-term support release for this computer. Guide the person through the installer.

After an installer, open a new terminal if the command is unavailable.
Check `git --version`, `gh --version`, and `uv --version` before you continue on either system.
Also check `node --version` and `npm --version`.

### Sign in and create the project

1. Run `gh auth status`. If needed, run `gh auth login --hostname github.com --git-protocol https --web`.
   Ask the person to complete browser sign-in and company authorization. Keep passwords and tokens out of chat.

2. Run `gh auth setup-git`. Confirm access to the named organization with `gh api orgs/COMPANY`.

3. Ask for a short project name and a folder. Check that the target folder and company repository do not exist.
   Create a private repository in that company, then clone it into the chosen folder:

   ```sh
   gh repo create COMPANY/PROJECT --private
   gh repo clone COMPANY/PROJECT "PROJECT-FOLDER"
   ```

   Replace the uppercase placeholders with the person's details. Do not create the repo under their personal account.
4. Install the release that Forge's [README](../README.md#install) names with `uv tool install --python 3.11` and its exact package URL.
   uv supplies Python. Run `uv tool update-shell` if the terminal cannot find Forge, then reopen the terminal.

5. Inside the cloned folder, run `forge init --actions yes`, without `--starter`.
   First check `git var GIT_AUTHOR_IDENT`. If git needs a name or email, ask the person for those values.
   Set them with `git config --local user.name` and `git config --local user.email` in this repo.

   This prepares the notes and brief. It also installs the bundled impeccable and emil-design-eng design skills.
   Follow the shipped Forge guide for the sales demo. Add no other tool for setup.

6. Run `forge next`. Tell the person that setup is complete and ask for their idea or client notes.
   Save those notes under `docs/context/`. Use them to write `docs/product/BRIEF.md` before you ask about missing details.

If a step fails, check what it already completed before a safe retry.
If company access or setup still fails, write a short message for the named developer.
Include the goal, the failed step, what you tried, and the help you need.
Let the person send the message. Resume from the saved step when the developer resolves it.
