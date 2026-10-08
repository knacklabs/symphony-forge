"""Forge's committed Husky hooks survive npm's real prepare lifecycle in every checkout."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

STORY = "FIX-HUSKY-HOOKS"
FIXTURES = Path(__file__).parent / "fixtures"


def _install(where):
    # The unchanged upstream installer runs through npm without fetching dependencies.
    done = subprocess.run(["npm.cmd" if os.name == "nt" else "npm", "install", "--offline",
                           "--no-audit", "--no-fund"], cwd=where, capture_output=True,
                          text=True, timeout=60)
    assert done.returncode == 0, done.stdout + done.stderr


def _guards(repo, where):
    commit = subprocess.run(["git", "commit", "--allow-empty", "-m", "Try a commit"],
                            cwd=where, capture_output=True, text=True)
    assert commit.returncode != 0
    assert "was not started by Forge" in commit.stderr
    push = subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=where,
                          capture_output=True, text=True)
    assert push.returncode != 0
    assert "changes only through a merged pull request" in push.stderr
    assert (where / "existing-hooks.log").read_text("utf-8").splitlines()[-2:] == [
        "pre-commit", "pre-push"]
    doctor = repo.forge("doctor", cwd=where)
    assert "doctor compared the synced files" in doctor.stdout
    assert "The git hooks that check each commit and push aren't installed." not in doctor.stdout
    assert ".husky/pre-commit differs" not in doctor.stdout
    assert ".husky/pre-push differs" not in doctor.stdout


@pytest.mark.parametrize("adopted", [False, "old-shims", "reinstalled"],
                         ids=["new-repo", "adopted-on-v1.2.7", "v1.2.7-after-install"])
def test_committed_husky_checks_survive_install_in_worktrees_and_fresh_clone(repo, tmp_path, adopted):
    repo.git("checkout", "-q", "-b", "client-hooks")
    repo.write("forge.toml", f'version = "{repo.forge("--version").stdout.split()[-1]}"\n'
                             'test = "echo ok"\nchecks = ["tests", "forge-pr-check"]\n')
    if adopted:
        shutil.copytree(FIXTURES / "forge-v1.2.7-husky/client", repo.path, dirs_exist_ok=True)
    shutil.copytree(FIXTURES / "husky-v9.1.7", repo.path / "husky")
    repo.write("package.json", json.dumps({"private": True, "scripts": {
        "prepare": 'node --input-type=module -e "import install from \'./husky/index.js\'; install()"'}}) + "\n")
    repo.write(".gitignore", "node_modules/\nexisting-hooks.log\n")
    original = {}
    for hook in ("pre-commit", "pre-push"):
        original[hook] = f'#!/bin/sh\necho {hook} >> existing-hooks.log\n'
        repo.write(f".husky/{hook}", original[hook])
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Set up Husky client")
    _install(repo.path)
    wrappers = {hook: (repo.path / ".husky/_" / hook).read_bytes() for hook in original}
    if adopted:
        for path in (FIXTURES / "forge-v1.2.7-husky").glob("pre-*"):
            installed = repo.path / ".husky/_" / path.name
            shutil.copyfile(path, installed)
            installed.chmod(0o755)
        if adopted == "reinstalled":
            _install(repo.path)
        config = (repo.path / "forge.toml").read_text("utf-8")
        repo.write("forge.toml", config.replace("v1.2.7", repo.forge("--version").stdout.split()[-1]))
    done = repo.forge("sync")
    assert done.returncode == 0, done.stderr
    for hook, before in original.items():
        text = (repo.path / ".husky" / hook).read_text("utf-8")
        assert text.startswith(before)
        assert text.count("forge hook " + hook) == 1
        assert (repo.path / ".husky/_" / hook).read_bytes() == wrappers[hook]
        assert not (repo.path / ".husky/_" / (hook + ".pre-forge")).exists()
    again = repo.forge("sync")
    assert again.returncode == 0, again.stderr
    assert "Nothing to change" in again.stdout
    # Adoption bootstraps before a Forge item exists. All guard checks enable Husky.
    bootstrap = dict(os.environ, HUSKY="0")
    repo.git("add", "-A")
    subprocess.run(["git", "commit", "-qm", "Commit Forge's Husky checks"], cwd=repo.path,
                   env=bootstrap, check=True)
    subprocess.run(["git", "push", "-q", "origin", "client-hooks"], cwd=repo.path,
                   env=bootstrap, check=True)
    _install(repo.path)
    _guards(repo, repo.path)
    worktree = tmp_path / "another worktree"
    repo.git("worktree", "add", "-qb", "another-client", str(worktree), "HEAD")
    clone = tmp_path / "fresh clone"
    repo.git("clone", "-qb", "client-hooks", repo.git("remote", "get-url", "origin"), str(clone))
    for where in (worktree, clone):
        _install(where)
        _guards(repo, where)
