# Product brief

## Summary

Symphony Forge helps a team turn a planned change into a reviewed pull request. It gives coding agents a clear next step, keeps work on branches, and checks the result before asking a human to merge. Teams use it to make delivery visible and repeatable without maintaining a separate workflow system.

## Users

- **Developers:** plan changes, run Forge commands, and inspect the work before merging.
- **Client teams:** see what changed, why it was built, and whether it works.
- **Forge maintainers:** improve the same workflow they use to build Forge.

## Target outcome

A team can move from an approved story or small fix to a tested, reviewed pull request with a clear record of the outcome in its repository.

## Key flows

1. **Set up:** a developer runs `forge init` in a new repository and sees the files and next step Forge created.
2. **Plan:** a developer writes a story or fix; Forge shows what needs a cold read or human approval before work starts.
3. **Build:** an agent works on a task or fix branch, runs the repository's tests, and hands back the result.
4. **Close:** Forge checks review and CI, opens or updates the pull request, and tells the human when it is ready to merge.
5. **Continue:** a developer runs `forge next` to see the current state and the exact next command.

## Constraints

- Git and the pull request keep history; `.factory` holds current story, task, and fix state.
- A human approves stories, chooses between meaningful options, and merges pull requests.
- Claude Code and Codex can coordinate the same Forge commands. The repository selects its worker in `forge.toml`.
- Each task or fix runs on its own branch; Forge uses the repository's test command and checks before close.

## Out of scope

- A hosted project management service or a database for workflow state.
- Replacing a team's application stack, CI provider, or deployment system.
- Automatically approving plans or merging pull requests.
