"""Upgrade verification writes generated files without changing the client's local hooks."""
import json
import shutil
import sys
from pathlib import Path

import pytest

from conftest import FORGE_SHIM, ROOT, _install, patient
from test_close import GREEN, env  # noqa: F401
from test_running_commands_follow_changed_forge_pin import _earlier_release
from test_setup import _fresh_client

STORY = "skipped-close"


@pytest.mark.parametrize("history", ["new", "previously-adopted"])
@pytest.mark.parametrize("merge", ["no-conflict", "generated-conflict", "changed-pin-conflict",
                                   "husky-conflict", "changed-pin-husky-conflict"])
def test_1_upgrade_close_checks_generated_files_without_rewriting_local_git_hooks(
        env, history, merge, monkeypatch):
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
    item, where = env.start_fix(allow_large="Fixture upgrade replaces the earlier generated files")
    config = (where / "forge.toml").read_text("utf-8")
    env.commit(where, "forge.toml", config.replace('version = "v1.2.2"',
                                                 f'version = "{version}"'))
    synced = repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    if "husky" in merge:
        hooks = where / ".husky"
        patient(lambda: hooks.mkdir(exist_ok=True))
        repo.git("config", "core.hooksPath", ".husky/_", cwd=where)
    else:
        hooks = Path(repo.git("rev-parse", "--path-format=absolute", "--git-path", "hooks", cwd=where))
    custom = b"#!/bin/sh\n# The client's own local hook.\nexit 0\n"
    for name in ("pre-commit", "pre-push"):
        patient(lambda: (hooks / name).write_bytes(custom))
        patient(lambda: (hooks / name).chmod(0o755))
    if "husky" in merge:
        # Team hooks are committed and deliberately contain no Forge check.
        repo.git("add", "--", ".husky/pre-commit", ".husky/pre-push", cwd=where)
        repo.git("commit", "-qm", "Keep the team's Husky hooks", cwd=where)
    guide = ".codex/skills/forge/SKILL.md"
    if merge != "no-conflict":
        env.commit(where, guide, (where / guide).read_text("utf-8").replace(
            "# Forge", "# Worker's Forge", 1))
    if merge.startswith("changed-pin"):
        env.commit(where, "forge.toml", config)
    env.commit(where, "app.py", "print('upgraded client')\n")
    if merge != "no-conflict":
        env.commit(repo.path, guide, (repo.path / guide).read_text("utf-8").replace(
            "# Forge", "# Default branch's Forge", 1))
        if merge.startswith("changed-pin") or "husky" in merge:
            # Main's upgrade avoids the separate missing-Husky-check sync refusal.
            env.commit(repo.path, "forge.toml", config.replace('version = "v1.2.2"',
                f'version = "{version}"' + ('\nfast_test = ""' if merge.startswith("changed-pin") else '')))
        if merge.startswith("changed-pin"):
            _earlier_release(env)
            monkeypatch.setenv("FORGE_PINNED_RUN", "v1.2.2")
        repo.git("push", "-q", "origin", "main")
    env.checks(GREEN)
    closed = repo.forge("close", item, cwd=where)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Ready:" in closed.stdout
    repo.git("merge-base", "--is-ancestor", "origin/main", "HEAD", cwd=where)
    if merge != "no-conflict":
        assert (where / guide).read_text("utf-8") == (
            ROOT / "src/forge/templates/skill.md").read_text("utf-8")
    for name in ("pre-commit", "pre-push"):
        assert (hooks / name).read_bytes() == custom
        assert not (hooks / f"{name}.pre-forge").exists()
    assert repo.git("status", "--porcelain", cwd=where) == ""
