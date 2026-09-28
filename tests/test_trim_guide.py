"""The migration guide has one home under docs."""

from pathlib import Path


STORY = "FORGE-TRIM-1"
ROOT = Path(__file__).resolve().parents[1]


def test_4_migration_guide_lives_in_docs(repo):
    assert repo.forge("--version").returncode == 0

    guide = ROOT / "docs/migrate-skill.md"
    assert guide.read_text(encoding="utf-8").startswith("---\nname: forge-migrate\n")
    assert not (ROOT / "src/forge/templates/migrate-skill.md").exists()
