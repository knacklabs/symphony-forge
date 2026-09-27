"""Migration keeps client files that the product still references."""

from test_migrate import _copied_client, _land


STORY = "forge-migrate-sets-aside-client-owned-fi"


def test_1_forge_migrate_keeps_a_referenced_file_under_an_old_forge_folder(
        repo, tmp_path, monkeypatch):
    _copied_client(repo, tmp_path, monkeypatch)
    skill = "factory/skills/gantry-admin/SKILL.md"
    repo.write(skill, "# Gantry admin\n")
    repo.write("package.json", '{"gantrySkill": "factory/skills/gantry-admin/SKILL.md"}\n')
    _land(repo, "Use the Gantry admin skill")

    moved = repo.forge("migrate")
    assert moved.returncode == 0, moved.stderr
    assert repo.git("show", f"forge/migrate-v1:{skill}") == "# Gantry admin"
    assert repo.git("ls-tree", "-r", "--name-only", "forge/migrate-v1",
                    f".forge-migrate/kept/{skill}") == ""
