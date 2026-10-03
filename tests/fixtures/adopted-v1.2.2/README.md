# Repo adopted on Forge v1.2.2

`client.tar.gz` holds the tracked files after a real v1.2.2 `forge init` adoption
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

Git used a local bare origin; gh was the test harness stub. All tracked files
were archived with their git executable modes, excluding `.factory/` adoption
state because it contains machine-specific identity and base commit details.
The archive keeps the release's settings and synced files unchanged, including
its model choices, stage, hooks and both hosts' skills. The upgrade test lands
these files before running the real upgrade command with fake third-party tools.
