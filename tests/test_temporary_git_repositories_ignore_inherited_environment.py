"""Temporary Git repositories must never rewrite a hook's real repository.

Audit: real pytest and migrate commands run with a disposable sentinel's Git
environment. Before the fix, bare init changes the sentinel's core.bare.
Existing migration tests do not inherit a hook environment; no Git call is faked.
"""
import json
import os
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT
from test_migrate import _copied_client, _land

STORY = "no-bare-flip"


def test_1_every_test_clears_inherited_git_environment_before_bare_remote_setup(tmp_path):
    sentinel = tmp_path / "sentinel"
    subprocess.run(["git", "init", "-q", str(sentinel)], check=True)
    suite = tmp_path / "suite"
    suite.mkdir()
    shutil.copy2(ROOT / "tests/conftest.py", suite / "conftest.py")
    (suite / "test_remote.py").write_text(
        "import os, subprocess\n"
        "def test_bare_remote_without_repo_fixture(tmp_path):\n"
        "    subprocess.run(['git', 'init', '-q', '--bare', str(tmp_path / 'remote.git')], "
        "check=True)\n"
        "    assert not any(name.startswith('GIT_') for name in os.environ)\n",
        encoding="utf-8")
    environment = {**os.environ, "GIT_DIR": str(sentinel / ".git"),
                   "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "test.inherited",
                   "GIT_CONFIG_VALUE_0": "yes", "PYTEST_ADDOPTS": ""}
    done = subprocess.run([sys.executable, "-m", "pytest", "-q", str(suite)],
                          cwd=tmp_path, env=environment, capture_output=True, text=True,
                          encoding="utf-8", timeout=120)
    bare = subprocess.run(["git", "-C", str(sentinel), "config", "--local", "core.bare"],
                          check=True, capture_output=True, text=True).stdout.strip()
    assert bare == "false", done.stdout + done.stderr
    assert done.returncode == 0, done.stdout + done.stderr


@pytest.mark.parametrize("history", ["new", "upgraded"])
@pytest.mark.parametrize("with_work_tree_and_index", [False, True])
def test_2_migrate_source_fetch_preserves_sentinel_repository_settings(
        repo, tmp_path, monkeypatch, history, with_work_tree_and_index):
    _copied_client(repo, tmp_path, monkeypatch)
    if history == "upgraded":
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        _land(repo, "Adopt the earlier release")
        repo.git("switch", "-qc", "fix/upgrade-client")
        version = repo.forge("--version").stdout.split()[-1]
        config = repo.path / "forge.toml"
        config.write_text(config.read_text().replace('"v1.2.2"', json.dumps(version)),
                          encoding="utf-8")
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Upgrade Forge")
        repo.git("switch", "main")
        repo.git("merge", "--ff-only", "fix/upgrade-client")
        repo.git("push", "-q", "origin", "main")

    # The copied-in client is the sentinel, separate from Forge's real checkout.
    before = (repo.git("config", "--local", "--list"), repo.git("rev-parse", "HEAD"),
              (repo.path / ".git/index").read_bytes())
    with monkeypatch.context() as inherited:
        inherited.setenv("GIT_DIR", str(repo.path / ".git"))
        if with_work_tree_and_index:
            inherited.setenv("GIT_WORK_TREE", str(repo.path))
            inherited.setenv("GIT_INDEX_FILE", str(repo.path / ".git/index"))
        done = repo.forge("migrate", "--dry-run")
    assert repo.git("config", "--local", "core.bare") == "false", done.stdout + done.stderr
    assert done.returncode == 0, done.stdout + done.stderr
    assert "Nothing was changed. forge migrate would do this" in done.stdout
    assert "factory/" in done.stdout
    assert (repo.git("config", "--local", "--list"), repo.git("rev-parse", "HEAD"),
            (repo.path / ".git/index").read_bytes()) == before
