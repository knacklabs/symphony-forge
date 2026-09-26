# What the switch removes

The switch to Forge v1 deletes the old Forge from this repo. Nothing is lost: the last commit
before the switch is tagged `old-forge-final`, and every removed file is there.

```
git show old-forge-final:constitution/README.md       read one file
git ls-tree -r --name-only old-forge-final factory/   list a folder
git log old-forge-final -- factory/scripts/            see a file's history
```

## What goes, and what replaces it

| Removed | What it was | Replaced by |
|---|---|---|
| `factory/` | The old Forge: scripts, prompts, schemas, the board and their tests | The `forge` package in `src/forge/` |
| `forge`, `forge.cmd`, `setup`, `install/` | The launchers and the installer | `uv tool install` from a release tag (`docs/guide.md`) |
| `harness.yaml` | Phase owners, model routing and skill lists | `forge.toml` and the `forge` commands |
| `constitution/` | The engineering constitution | The standards page, `src/forge/standards.md` |
| `harness/` | The NestJS and React scaffold and its conventions | `src/forge/templates/conventions/` |
| `.codex/agents/` and the model routing in `.codex/` | The Codex role files | The `workers` setting in `forge.toml`, and the models in `.codex/config.toml` |
| `.envrc` | The three verify commands and gstack's folder | The `test` command in `forge.toml` |
| `.gstack/` | gstack's reviews, plans, decisions and learnings | Office-hours design docs move to `docs/context/`; gstack keeps the rest on each machine |
| `WORKFLOW.md` and the old Forge docs in `docs/` | How the old Forge worked | `docs/guide.md` |
| Specs the switch supersedes | Contracts for machinery the rebuild removes | `docs/specs/lean-forge-v1.md` |
| `board-invariant.yml`, `factory-scaffold.yml`, `gardener.yml`, `harness-health.yml`, `pr-link.yml`, `pr-ticket-check.yml` and `roadmap-gate.yml` in `.github/workflows/` | The old checks | The generated `forge.yml`, with its `tests` and `forge-pr-check` checks |

## Kept

- `docs/guide.md`, this page and the standards page.
- `docs/specs/` (the specs still in force) and `docs/decisions/`, where the switch marks the
  decisions it supersedes.
- `docs/product/`, `docs/context/` and every doc the first story on v1 produced.
