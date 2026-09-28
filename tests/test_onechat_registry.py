"""Forge remembers the main checkout after a successful setup or next command."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from test_migrate import _copied_client
from test_setup import _fresh_client

STORY = "FORGE-ONECHAT-1"


def test_2_successful_commands_remember_one_main_checkout(repo, gh, tmp_path, monkeypatch):
    config = tmp_path / "config"
    monkeypatch.setenv("APPDATA" if os.name == "nt" else "XDG_CONFIG_HOME", str(config))
    registry = config / "forge" / "repos"

    # A successful command before forge.toml exists cannot register a repo.
    assert repo.forge("next").returncode == 0
    assert not registry.exists()

    client, init = _fresh_client(repo, gh, tmp_path)
    assert init.returncode == 0, init.stderr
    assert registry.read_text(encoding="utf-8").splitlines() == [str(client.resolve())]

    repo.git("worktree", "add", "-q", "-b", "task/remember", str(tmp_path / "other-tree"),
             cwd=client)
    tree = tmp_path / "other-tree"
    assert repo.forge("next", cwd=tree).returncode == 0
    assert registry.read_text(encoding="utf-8").splitlines() == [str(client.resolve())]

    registry.unlink()
    synced = repo.forge("sync", cwd=tree)
    assert synced.returncode == 0, synced.stderr
    assert registry.read_text(encoding="utf-8").splitlines() == [str(client.resolve())]

    registry.unlink()
    assert repo.forge("sync", "--not-a-flag", cwd=tree).returncode != 0
    assert not registry.exists()
    assert repo.forge("next", cwd=tree).returncode == 0
    assert registry.read_text(encoding="utf-8").splitlines() == [str(client.resolve())]

    no_config = tmp_path / "no-config"
    no_config.mkdir()
    registry.write_text("\n".join((str(client), str(tmp_path / "missing"),
                                    str(no_config), str(client))) + "\n", encoding="utf-8")
    # APPROVE is the first command that will consume the reader; exercise its exported file
    # boundary now without adding a test-only Forge command.
    src = Path(__file__).resolve().parents[1] / "src"
    read = subprocess.run(
        [sys.executable, "-c", "import json, sys; sys.path.insert(0, sys.argv[1]); "
         "from forge.machine import remembered; "
         "print(json.dumps([str(path) for path in remembered()]))", str(src)],
        capture_output=True, text=True, check=True)
    assert json.loads(read.stdout) == [str(client.resolve())]

    _copied_client(repo, tmp_path, monkeypatch)
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "client"\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Set Forge version")
    repo.git("push", "-q", "origin", "main")

    dry = repo.forge("migrate", "--dry-run")
    assert dry.returncode == 0, dry.stderr
    assert str(repo.path.resolve()) not in registry.read_text(encoding="utf-8").splitlines()

    repo.write("dirty.txt", "uncommitted\n")
    assert repo.forge("migrate").returncode != 0
    assert str(repo.path.resolve()) not in registry.read_text(encoding="utf-8").splitlines()
    (repo.path / "dirty.txt").unlink()

    migrated = repo.forge("migrate")
    assert migrated.returncode == 0, migrated.stderr
    assert registry.read_text(encoding="utf-8").splitlines()[-1] == str(repo.path.resolve())

    registry.unlink()
    registry.mkdir()
    assert repo.forge("next").returncode == 0
