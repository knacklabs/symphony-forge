"""Forge remembers the main checkout after a successful setup or next command."""
from __future__ import annotations

from pathlib import Path

from test_migrate import _copied_client
from test_setup import _fresh_client

STORY = "FORGE-ONECHAT-1"


def test_2_successful_commands_remember_one_main_checkout(repo, gh, tmp_path, monkeypatch):
    config = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    registry = config / "forge" / "repos"

    # A refusal and a successful command before forge.toml exists cannot register a repo.
    assert repo.forge("sync").returncode != 0
    assert repo.forge("next").returncode == 0
    assert not registry.exists()

    client, init = _fresh_client(repo, gh, tmp_path)
    assert init.returncode == 0, init.stderr
    assert registry.read_text(encoding="utf-8").splitlines() == [str(client.resolve())]

    repo.git("worktree", "add", "-q", "-b", "task/remember", str(tmp_path / "other-tree"),
             cwd=client)
    tree = tmp_path / "other-tree"
    assert repo.forge("next", cwd=tree).returncode == 0
    assert repo.forge("sync", cwd=tree).returncode == 0
    assert registry.read_text(encoding="utf-8").splitlines() == [str(client.resolve())]

    _copied_client(repo, tmp_path, monkeypatch)

    dry = repo.forge("migrate", "--dry-run")
    assert dry.returncode == 0, dry.stderr
    assert registry.read_text(encoding="utf-8").splitlines() == [str(client.resolve())]

    migrated = repo.forge("migrate")
    assert migrated.returncode == 0, migrated.stderr
    # Migration puts forge.toml on its new branch, not yet in the main checkout.
    assert registry.read_text(encoding="utf-8").splitlines() == [str(client.resolve())]

    migrated_toml = tmp_path / "repo-forge-migrate-v1" / "forge.toml"
    (repo.path / "forge.toml").write_text(migrated_toml.read_text(encoding="utf-8"),
                                          encoding="utf-8")
    assert repo.forge("next").returncode == 0
    assert registry.read_text(encoding="utf-8").splitlines() == [str(client.resolve()),
                                                                  str(repo.path.resolve())]

    registry.unlink()
    registry.mkdir()
    assert repo.forge("next").returncode == 0
