"""Upgrade verification writes generated files without changing the client's local hooks."""
import json
import shutil
import sys
from pathlib import Path

import pytest

from conftest import FORGE_SHIM, ROOT, _install, patient
from test_close import GREEN, env  # noqa: F401
from test_setup import _fresh_client

STORY = "skipped-close"


@pytest.mark.parametrize("history", ["new", "previously-adopted"])
def test_1_upgrade_close_checks_generated_files_without_rewriting_local_git_hooks(env, history):
    repo = env.repo
    version = repo.forge("--version").stdout.split()[-1]
    old = env.tmp / "previous-release"
    patient(lambda: shutil.copytree(ROOT / "tests/fixtures/forge-v1.2.2", old))
    (old / "src/forge/cli-py.txt").rename(old / "src/forge/cli.py")
    _install(repo.bin, "forge", FORGE_SHIM.format(python=sys.executable, src=str(old / "src")))
    try:
        if history == "new":
            client, initialized = _fresh_client(repo, env.gh, env.tmp)
            assert initialized.returncode == 0, initialized.stdout + initialized.stderr
            repo.path = client
        else:
            patient(lambda: shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client",
                                            repo.path, dirs_exist_ok=True))
            repo.git("switch", "-qc", "fix/adopted-client")
            repo.write(".factory/fixes/adopted-client.json", json.dumps({
                "kind": "fix", "status": "working", "branch": "fix/adopted-client",
                "why": "Adopt Forge", "done_when": "Forge is set up",
                "allow_large": "Fixture adoption writes the earlier release's generated files"}))
            synced = repo.forge("sync")
            assert synced.returncode == 0, synced.stdout + synced.stderr
            repo.git("add", "-A")
            repo.git("commit", "-qm", "Client adopted on the earlier release")
            repo.git("switch", "-q", "main")
            repo.git("merge", "--ff-only", "fix/adopted-client")
            remote = Path(repo.git("remote", "get-url", "origin"))
            repo.git("fetch", "-q", str(repo.path), "main:main", cwd=remote)
    finally:
        _install(repo.bin, "forge", FORGE_SHIM.format(python=sys.executable, src=str(ROOT / "src")))
    item, where = env.start_fix()
    config = (where / "forge.toml").read_text("utf-8")
    env.commit(where, "forge.toml", config.replace('version = "v1.2.2"',
                                                 f'version = "{version}"'))
    synced = repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    env.commit(where, "app.py", "print('upgraded client')\n")
    hooks = Path(repo.git("rev-parse", "--path-format=absolute", "--git-path", "hooks", cwd=where))
    custom = b"#!/bin/sh\n# The client's own local hook.\nexit 0\n"
    for name in ("pre-commit", "pre-push"):
        (hooks / name).write_bytes(custom)
        (hooks / name).chmod(0o755)
    env.checks(GREEN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Ready:" in closed.stdout
    for name in ("pre-commit", "pre-push"):
        assert (hooks / name).read_bytes() == custom
        assert not (hooks / f"{name}.pre-forge").exists()
    assert repo.git("status", "--porcelain", cwd=where) == ""
