# Forge commands

| Command | What it does |
|---|---|
| `forge init` | Sets up a new repo: `forge.toml`, the docs skeleton, the first commit, then `forge sync` |
| `forge sync` | Writes the generated files for both hosts, the CI workflow and the git hooks |
| `forge doctor` | Checks tools, versions, hooks, generated-file drift and CI; one row per problem, each with a fix; `--fix` repairs what it safely can |
| `forge test` | Run fast_test (else test) in the machine test lane; `--pytest <base>` picks related pytest tests. |
| `forge migrate` | Moves a client from the copied-in Forge in one pull request |
| `forge upgrade [release]` | Upgrades Forge to the release, or the newest: installs it, has it refresh Forge's files in a fix, and closes that fix |
| `forge next` | Says where things stand and gives the exact next command |
| `forge board` | Writes the plain-English board page and opens it (`--out <path>` to write it elsewhere) |
| `forge lanes --json` | Runs on this machine from repos on this Forge release |
| `forge stop <item>` | Person only: stops the item's runs in this repo (`--repo <root>` or `--id <id>`) |
| `forge story new <KEY> "<title>"` | Starts a story's branch, worktree and doc (`--from-fix <fix>` promotes a fix) |
| `forge story done <KEY> "<outcome>"` | Corrects a finished story's outcome on an existing work branch; opens no separate pull request |
| `forge read <KEY or spec>` | Runs the next round of the cold read of a story doc or spec, until a round finds nothing |
| `forge task start <KEY>/<TASK>` | Starts a task in its own branch and worktree |
| `forge fix start "<why>" --done "<done when>"` | Starts a small fix in its own branch and worktree (`--slug <name>` names it) |
| `forge fix allow-large "<reason>"` | Records the human's permission for a fix to go over the fix limit |
| `forge fix amend <fix> --done "<done when>" --because "<why>"` | Replaces a fix's done-when; the old text and the reason stay in its record, and the next review judges the new text |
| `forge work <item>` | Runs the worker on a task or fix: the first build, or a fix round (`--note "<text>"` guides that round) |
| `forge ask "<question>"` | Asks Codex a read-only question about the code without starting a fix (`--model` and `--effort` override `[models.lite]`) |
| `forge close <item>` | Closes a task or fix by the close rule |
| `forge merge <item>` | Merges a ready item when the default branch allows agent merges; the story's last task records it done (`--outcome <sentence>` overrides its title) |
| `forge merge enable` | Run by the repo owner in their own terminal: opens the change that lets the agent merge ready pull requests, for the owner to merge |
| `forge land <item>` | Builds, closes, runs fix rounds and merges a task or fix where the repo allows agent merges; run it in the background |
| `forge spec save <slug>` | Saves a spec as a draft |
| `forge spec confirm <slug> --by "<name>"` | Marks a spec confirmed after the human confirms it in chat |
| `forge spec measure <slug> --result "<text>"` | Records the measured result in a confirmed spec's Success measure, dated today; the spec stays confirmed. `forge next` lists the check once every story from the spec is done and its check date has passed |
| `forge spec payback --build-days <n> --day-rate <n> <value>` | Says whether a build pays back: build (three months or less), smallest slice first (up to twelve), don't build, or find out first when no value can be estimated. The value is any of `--hours-per-month`, `--people` and `--hourly-rate`; `--revenue-per-month`; `--incident-cost` and `--incident-chance`, weighed by `--confidence measured`, `estimated` or `guessed` (the default). Use rounded rates, never real salaries. It changes nothing |
| `forge decision new <slug>` | Writes a decision record |
| `forge decision accept <slug> --by "<name>"` | Accepts a decision after the human confirms it in chat |
| `forge roadmap add <spec>` | Adds roadmap items from a confirmed spec |
| `forge roadmap retire <KEY> --by <spec>` | Marks a pending roadmap item superseded by the spec that replaces it; `forge next` and the board stop showing it |
| `forge hook context` | Session start: prints `forge next` and the story's state |
| `forge hook handoff` | Saves current state before context compaction |
| `forge hook approval` | After the plan and question tools: records approvals and counts human touches |
| `forge hook deny` | Before each shell command: blocks destructive commands, `--no-verify` and `gh pr merge` |
| `forge hook pre-commit` | The git pre-commit rules |
| `forge hook pre-push` | The git pre-push rules |
| `forge hook merge-roadmap` | Git's merge rule for the roadmap and spotted list |
| `forge hook pr-check` | The required `forge-pr-check`, run in CI from the base branch |
