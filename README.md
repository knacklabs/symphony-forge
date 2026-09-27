# Symphony Forge

Forge takes a story from an approved plan to a reviewed pull request. The human approves the story, chooses between options when needed, and merges. Agents do the work in separate branches and worktrees.

## How it works

Run `forge next` in a Forge repo to see its current state and the exact next command. `forge board` shows progress. The normal path is:

1. `forge story new <KEY> "<title>"` creates the story doc in `plans/<KEY>.md`.
2. `forge read <KEY>` records one cold read. The human approves the story plan.
3. `forge task start <KEY>/<TASK>` creates a task branch and worktree; `forge work <KEY>/<TASK>` runs its worker.
4. `forge close <KEY>/<TASK>` checks tests and review, then opens its pull request. The human merges it.
5. `forge story done <KEY> "<outcome>"` records the result after the last merge.

For a small change, `forge fix start "<why>" --done "<done when>"` starts a fix. Run `forge work <fix>` and `forge close <fix>` on that branch.

The [agent instructions](AGENTS.md) describe the lanes and rules. The [Forge skill](.codex/skills/forge/SKILL.md) gives the full command guide. Current state lives in `.factory/stories/<KEY>/story.json`, `.factory/stories/<KEY>/tasks/*.json`, and `.factory/fixes/*.json`. `plans/` holds story docs, cold-read notes, and `roadmap.json`. Git keeps the history.

## Develop Forge

Install this package from the checkout with `uv pip install -e .` or another Python 3.11+ installer. `forge.toml` names the full test command; run that command before closing work. `forge --help` lists the available commands.
