# Repo adopted on Forge v1.2.2

`client/` holds the files used by the upgrade test after a real v1.2.2 `forge init` adoption
was fast-forwarded onto main. It is not output from the current sync.
The source was the local release tag v1.2.2
(`3febf07f414725bdb5028830655f1c83368b5ec0`), exported with `git archive`.

The input was a repo with a README and two commits. Its AGENTS.md said
`Keep the public API stable.` and its Codex config had an MCP server named
`docs` with command `docs-server`. With the release's source on PYTHONPATH,
the real Forge entry point ran:

```sh
forge init --test 'python -c "print(123)"' --checks tests \
  --interfaces 'api/routes/**' --approver Owner --merger Owner
git merge --ff-only fix/adopt-forge
```

Git used a local bare origin; gh was the test harness stub. The fixture keeps the
release's `forge.toml`, `AGENTS.md`, both hosts' Forge skills and hook settings,
Codex config and `.forge/hooks.sh` as ordinary text files, with their original
bytes and executable modes. These are the files the test checks before and after
upgrade. Other adoption output is omitted, including `.factory/` state with
machine-specific identity and base commit details. The upgrade test copies this
folder into a temporary repo and commits and lands these files before running
the real upgrade command with fake third-party tools.
