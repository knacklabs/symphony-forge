STORY = "FORGE-TRIM-1"

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_5_sync_places_standards_beside_both_forge_skills(repo):
    repo.git("checkout", "-q", "-b", "fix/standards")
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\ntest = "true"\n')

    result = repo.forge("sync")
    assert result.returncode == 0, result.stderr
    # read_text normalizes CRLF checkouts, matching sync's LF byte write.
    expected = (ROOT / "src/forge/standards.md").read_text(encoding="utf-8").encode("utf-8")
    for host in (".claude", ".codex"):
        folder = repo.path / host / "skills/forge"
        assert (folder / "standards.md").read_bytes() == expected
        skill = (folder / "SKILL.md").read_text(encoding="utf-8")
        build_simple = skill.split("## Build simple\n", 1)[1].split("\n## ", 1)[0]
        assert "standards.md" in build_simple
        assert "**Finding forms.**" in build_simple
        assert "Problem first:" not in build_simple
