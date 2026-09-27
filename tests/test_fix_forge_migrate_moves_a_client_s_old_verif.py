"""Migrated Node verify commands install dependencies before CI runs them."""

import tomllib

import pytest

from test_migrate import TEST, _copied_client, _land

STORY = "forge-migrate-moves-a-client-s-old-verif"


@pytest.mark.parametrize("has_package", [True, False])
def test_1_migrated_verify_commands_install_for_a_package_json_client(
        repo, tmp_path, monkeypatch, has_package):
    _copied_client(repo, tmp_path, monkeypatch)
    if has_package:
        repo.write("package.json", '{"scripts": {"test": "echo ready"}}\n')
        _land(repo, "Add the client's package")

    moved = repo.forge("migrate")
    assert moved.returncode == 0, moved.stderr
    config = tomllib.loads(repo.git("show", "forge/migrate-v1:forge.toml"))
    assert config["test"] == ("npm ci && " if has_package else "") + TEST
