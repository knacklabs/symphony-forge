This archive holds the files committed by the real `forge init` from tag v1.2.2
when adopting an existing app, excluding the machine-specific adoption record.
It includes that release's pin and all its synced files, with no current Forge
output substituted. The app had a README and these AGENTS.md lines before adoption:

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
Archive the paths from `git diff --name-only main...fix/adopt-forge`, reading
their bytes from that branch and excluding `.factory/`. The test supplies the
existing application history and commits this adoption snapshot itself; it does
not run today's init or manufacture drift to stand in for the old release.
