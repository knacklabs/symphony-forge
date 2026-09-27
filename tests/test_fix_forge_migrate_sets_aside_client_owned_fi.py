"""Migration keeps client files that the product still references."""

import json

import pytest

from test_migrate import _copied_client, _land


STORY = "forge-migrate-sets-aside-client-owned-fi"


@pytest.mark.parametrize("skill, custom, replaced", [
    ("factory/skills/gantry-admin/SKILL.md", "# Gantry admin", False),
    (".codex/skills/forge/SKILL.md", "# The shop's custom Forge skill", True),
])
def test_1_forge_migrate_keeps_referenced_client_content(
        repo, tmp_path, monkeypatch, skill, custom, replaced):
    _copied_client(repo, tmp_path, monkeypatch)
    repo.write(skill, custom + "\n")
    repo.write("package.json", json.dumps({"shopSkill": skill}) + "\n")
    _land(repo, "Use the shop skill")

    moved = repo.forge("migrate")
    assert moved.returncode == 0, moved.stderr
    if replaced:
        assert repo.git("show", f"forge/migrate-v1:.forge-migrate/kept/{skill}") == custom
        assert repo.git("show", f"forge/migrate-v1:{skill}") != custom
    else:
        assert repo.git("show", f"forge/migrate-v1:{skill}") == custom
        assert repo.git("ls-tree", "-r", "--name-only", "forge/migrate-v1",
                        f".forge-migrate/kept/{skill}") == ""
