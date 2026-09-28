STORY = "FORGE-TRIM-1"

import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_5_sync_places_standards_beside_both_forge_skills(repo):
    repo.git("checkout", "-q", "-b", "fix/standards")
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\ntest = "true"\n')

    result = repo.forge("sync")
    assert result.returncode == 0, result.stderr
    expected = (ROOT / "src/forge/standards.md").read_bytes()
    for host in (".claude", ".codex"):
        folder = repo.path / host / "skills/forge"
        assert (folder / "standards.md").read_bytes() == expected
        skill = (folder / "SKILL.md").read_text(encoding="utf-8")
        build_simple = skill.split("## Build simple\n", 1)[1].split("\n## ", 1)[0]
        assert "standards.md" in build_simple
        assert "**Finding forms.**" in build_simple
        assert "Problem first:" not in build_simple


def test_6_forge_fits_trim_target_without_raising_ceiling(repo):
    assert repo.forge("--help").returncode == 0
    # The approved trim target is the existing 8,000-line ceiling, not the old 7,561 goal.
    ceiling = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "tool"]["forge"]["line_ceiling"]
    assert ceiling == 8000
    files = [p for p in (ROOT / "src/forge").rglob("*")
             if p.is_file() and "__pycache__" not in p.parts]
    assert sum(p.read_bytes().count(b"\n") for p in files) <= ceiling
