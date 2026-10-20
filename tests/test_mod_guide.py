"""New and previously adopted repos receive the coordinator's guide sections.

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
                    "The pane and strip", "Events", "Save decisions and ideas", "Planning a story"):
        expected = section(template, heading)
        assert expected, heading
        for shipped in guide:
            assert section(shipped, heading) == expected, heading
    # Previously chat could be the only record. The delivered prompt must now
    # name each durable home and how to question a new direction, in a short section.
    decisions = section(template, "Save decisions and ideas")
    assert len(decisions.splitlines()) <= 14
    for contract in ("Understand each", "same turn", "never leave it only in chat",
                     "Grill new directions", "one question at a time", "recommendation first",
                     "plan's Notes", "forge close <item> --resolve", "--reason",
                     "standing rule or direction", "forge decision new <slug>",
                     "next fix", "one pull request per decision", "plans/ideas.md",
                     "short dated list", "forge start", "owner says later",
                     "waiting entries", "Remove an entry", "do it now"):
        assert contract in decisions, contract
    # A clean read used to lead straight to approval, hiding choices made while
    # answering notes. Both delivery paths must carry the questions before approval.
    planning = " ".join(section(template, "Planning a story").split())
    for contract in ("Handle cold-read rounds yourself", "amend the plan and write dispositions",
                     "Once a read is clean, before Plan Mode approval",
                     "all rounds", "behaviour, a limit, a refusal or a scope cut",
                     "Grill the human one question at a time", "your recommendation first",
                     "Record each answer in the plan, then ask for approval",
                     "Plain factual corrections need no question"):
        assert contract in planning, contract
