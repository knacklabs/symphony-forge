"""New and previously adopted repos receive the mod's guide sections.

The shipped text is the delivery contract. Plugin tests own runtime behavior;
this check does not keep a second copy of the guide's wording.
"""
import shutil

import pytest

from conftest import ROOT
from test_setup import _fresh_client, _version

STORY = "FIX-TEST-AUDIT-FOLLOWUPS"


@pytest.fixture(params=["new", "previous adoption"])
def guide(repo, gh, tmp_path, request):
    if request.param == "new":
        client, result = _fresh_client(repo, gh, tmp_path)
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("checkout", "-q", "-b", "fix/mod-guide")
        config = (repo.path / "forge.toml").read_text(encoding="utf-8")
        repo.write("forge.toml", config.replace('version = "v1.2.2"',
                                               f'version = "{_version(repo)}"'))
        client, result = repo.path, repo.forge("sync")
    assert result.returncode == 0, result.stdout + result.stderr
    return [(client / host / "skills/forge/SKILL.md").read_text(encoding="utf-8")
            for host in (".claude", ".codex")]


def section(guide, heading):
    return guide.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0].strip()


def test_1_new_and_previously_adopted_repos_receive_the_mod_guide_sections(guide):
    template = (ROOT / "src/forge/templates/skill.md").read_text(encoding="utf-8")
    for heading in ("Claude Code plugin core", "Installing the mod", "Approving with the pane",
                    "The pane and strip", "Events"):
        expected = section(template, heading)
        assert expected, heading
        for shipped in guide:
            assert section(shipped, heading) == expected, heading
