The `doctor-v1.2.2/` folder holds ordinary text files committed by the real
`forge init` from tag v1.2.2 when adopting an existing app. It retains that
release's pin, both hosts' hooks, the Codex config, hook launcher, workflow,
Claude Forge skill and AGENTS.md. These are the files the regression needs for
repairs, hand-edit protection and preserved team instructions; the other synced
skills and roles and the machine-specific adoption record are omitted. No
current Forge output is substituted. The app had a README and these AGENTS.md
lines before adoption:

```markdown
# Team rules

Keep our application.
```

To reproduce, extract `git archive v1.2.2` into a temporary source folder and run
its CLI with that folder's `src` on PYTHONPATH. In an existing clean repository
with a local bare origin and an initial commit containing those two files, run:

```sh
python -c 'from forge.cli import main; main()' init --test 'npm test' --checks tests \
  --interfaces 'api/routes/**' --approver Team --merger Team
```

Use author `Forge Test <forge@example.test>` and a gh edge stub returning `{}`.
Copy the retained paths from `git diff --name-only main...fix/adopt-forge`, reading
their bytes from that branch. The test supplies the
existing application history and commits this adoption snapshot itself; it does
not run today's init or manufacture drift to stand in for the old release.
