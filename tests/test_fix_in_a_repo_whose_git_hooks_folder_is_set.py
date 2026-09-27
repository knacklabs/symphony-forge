"""Git hooks configured in a Husky-style folder."""
from __future__ import annotations

import subprocess

STORY = "FIX-IN-A-REPO-WHOSE-GIT-HOOKS-FOLDER-IS-SET"


def _client(repo):
    repo.git("checkout", "-q", "-b", "fix/husky")
    repo.write("forge.toml", f'version = "{repo.forge("--version").stdout.split()[-1]}"\n'
                             'test = "true"\nchecks = ["tests", "forge-pr-check"]\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Set up client")
    repo.git("config", "core.hooksPath", ".husky/_")
    hooks = repo.path / ".husky" / "_"
    hooks.mkdir(parents=True)
    return hooks


def test_1_sync_installs_in_husky_folder_and_runs_existing_hooks(repo, tmp_path):
    hooks = _client(repo)
    ran = tmp_path / "existing-hooks"
    (hooks / "h").write_text('n=$(basename "$0")\n'
                             's=$(dirname "$(dirname "$0")")/$n\n'
                             '[ ! -f "$s" ] && exit 0\nsh -e "$s" "$@"\n', encoding="utf-8")
    for name in ("pre-commit", "pre-push"):
        user_hook = hooks.parent / name
        user_hook.write_text(f'#!/bin/sh\necho {name} >> "{ran}"\n', encoding="utf-8")
        path = hooks / name
        path.write_text('#!/usr/bin/env sh\n. "$(dirname "$0")/h"\n', encoding="utf-8")
        path.chmod(0o755)

    done = repo.forge("sync")
    assert done.returncode == 0, done.stderr
    commit = subprocess.run(["git", "commit", "--allow-empty", "-m", "Try a commit"],
                            cwd=repo.path, capture_output=True, text=True)
    assert commit.returncode != 0
    assert "was not started by Forge" in commit.stderr
    push = subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=repo.path,
                          capture_output=True, text=True)
    assert push.returncode != 0
    assert "changes only through a merged pull request" in push.stderr
    assert ran.read_text(encoding="utf-8").splitlines() == ["pre-commit", "pre-push"]


def test_2_doctor_reports_missing_hooks_in_husky_folder(repo):
    hooks = _client(repo)
    with (repo.path / "forge.toml").open("a", encoding="utf-8") as config:
        config.write('repo = "forge-source"\n')
    done = repo.forge("doctor")
    assert done.returncode == 1
    assert "The git hooks that check each commit and push aren't installed." in done.stdout
    assert "Fix: forge sync" in done.stdout

    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    assert (hooks / "pre-commit").exists() and (hooks / "pre-push").exists()
    done = repo.forge("doctor")
    assert "The git hooks that check each commit and push aren't installed." not in done.stdout
