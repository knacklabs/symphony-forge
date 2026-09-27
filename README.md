# Symphony Forge

Forge takes a change from an approved plan to a reviewed pull request. It keeps the current work in the repository, runs tests and review before closing a task, and leaves merging to a human.

## Install

Install [uv](https://docs.astral.sh/uv/) and then Forge:

```sh
uv tool install git+https://github.com/knacklabs/symphony-forge@v1.0.0
```

Run `forge init` in a new repository to set it up. Run `forge next` to see its state and the next command.

See the [Forge guide](docs/guide.md) for the full workflow, commands, and upgrade instructions.
