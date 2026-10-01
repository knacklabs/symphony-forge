"""The README and the guide tell an owner to upgrade Forge with the one upgrade command."""

from __future__ import annotations

from conftest import ROOT

STORY = "FORGE-UPGRADECMD-1"


def _section(path: str, heading: str) -> str:
    text = (ROOT / path).read_text(encoding="utf-8")
    start = text.index(heading)
    end = text.find("\n#", start + len(heading))
    return " ".join(text[start:end if end != -1 else None].split())


def test_4_readme_and_guide_upgrade_with_the_one_command():
    for path, heading in (("README.md", "### Upgrade a project"),
                          ("docs/guide.md", "## Upgrading a repo")):
        section = _section(path, heading)
        assert "`forge upgrade <release>`" in section, path
        assert 'forge fix start "Upgrade Forge' not in section, path
        assert "forge sync" not in section, path
