"""The migration guide has one packaged home, available to clients."""

from pathlib import Path


STORY = "FORGE-TRIM-1"
ROOT = Path(__file__).resolve().parents[1]


def test_4_migration_guide_lives_in_package(repo):
    assert repo.forge("--version").returncode == 0

    # The old docs-only home kept the guide out of client installations.
    guide = ROOT / "src/forge/templates/migrate-skill.md"
    assert guide.read_text(encoding="utf-8").startswith("---\nname: forge-migrate\n")
    assert not (ROOT / "docs/migrate-skill.md").exists()
