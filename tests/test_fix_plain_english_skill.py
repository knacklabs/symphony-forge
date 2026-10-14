"""New and upgraded clients get the plain English skill, and agents are told to use it."""
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT, FORGE_SHIM, _install
from test_setup import PLAIN_ENGLISH, _fresh_client, _version

STORY = "FIX-PLAIN-ENGLISH-SKILL"
SKILL = "skills/simplified-technical-english"
SOURCE = ROOT / "src/forge/templates" / SKILL


def rule(text: str) -> str:
    """The paragraph that names the skill."""
    return next(" ".join(part.split()) for part in text.split("\n\n")
                if "simplified-technical-english" in part)


@pytest.mark.parametrize("setup", ["new", "previous-release adoption"])
def test_1_clients_get_the_skill_and_agents_write_people_text_with_it(repo, gh, tmp_path, setup):
    if setup == "new":
        client, made = _fresh_client(repo, gh, tmp_path)
    else:
        old = tmp_path / "previous-release"
        shutil.copytree(ROOT / "tests/fixtures/forge-v1.2.2", old)
        (old / "src/forge/cli-py.txt").rename(old / "src/forge/cli.py")
        _install(repo.bin, "old-forge", FORGE_SHIM.format(python=sys.executable, src=str(old / "src")))
        gh.respond("api", stdout="{}")
        made = subprocess.run([sys.executable, str(repo.bin / "old-forge"), "init",
                               "--test", "echo ok", "--checks", "tests",
                               "--interfaces", "api/routes/**", "--approver", "Owner",
                               "--merger", "Owner"], cwd=repo.path, capture_output=True, text=True)
        client = repo.path.parent / "repo-fix-adopt-forge"
    assert made.returncode == 0, made.stdout + made.stderr
    if setup != "new":
        assert not (client / ".codex" / SKILL).exists()
        config = client / "forge.toml"
        config.write_text(config.read_text(encoding="utf-8").replace(
            'version = "v1.2.2"', f'version = "{_version(repo)}"'), encoding="utf-8")
        synced = repo.forge("sync", cwd=client)
        assert synced.returncode == 0, synced.stdout + synced.stderr

    guides = []
    for host in (".claude", ".codex"):
        folder = client / host / SKILL
        for name in PLAIN_ENGLISH:
            assert (folder / name).read_bytes() == (SOURCE / name).read_bytes(), (host, name)
        # The standard's own word list belongs to its owner and is never shipped.
        assert not (folder / "references/word-list.md").exists()
        assert "word-list.md" not in (folder / "SKILL.md").read_text(encoding="utf-8")
        # The license and notice say the word list is left out.
        for name in ("LICENSE", "NOTICE.md"):
            assert (folder / name).read_text(encoding="utf-8").startswith(
                "Forge note: Forge ships this skill without references/word-list.md"), (host, name)
            assert "This bundle leaves it out." in " ".join(
                (folder / name).read_text(encoding="utf-8").split()), (host, name)
        # The skill's check command works from the repo root.
        assert f"python3 .claude/{SKILL}/scripts/ste_check.py" in (folder / "SKILL.md").read_text(
            encoding="utf-8")
        guides.append(rule((client / host / "skills/forge/SKILL.md").read_text(encoding="utf-8")))

    # The check tool works without the word list and still finds broken rules.
    tool = str(client / ".codex" / SKILL / "scripts/ste_check.py")
    draft = client / "draft.md"
    draft.write_text("Run the tests. The board shows the result.\n", encoding="utf-8")
    checked = subprocess.run([sys.executable, tool, str(draft)], capture_output=True, text=True)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "word list" not in checked.stdout
    draft.write_text("You shouldn't run the tests; the board has updated.\n", encoding="utf-8")
    broken = subprocess.run([sys.executable, tool, str(draft)], capture_output=True, text=True)
    assert broken.returncode == 1, broken.stdout + broken.stderr
    assert "ERROR" in broken.stdout

    brief = rule((ROOT / "src/forge/templates/brief.md").read_text(encoding="utf-8"))
    for text in (brief, *guides):
        for phrase in ("What changes for you", "Why and Done when", "a fix's why and Done when",
                       "pull request summaries", "questions to the human", "board",
                       "`forge next` lines"):
            assert phrase in text, phrase
