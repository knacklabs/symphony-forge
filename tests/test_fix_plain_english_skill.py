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

    for host in (".claude", ".codex"):
        folder = client / host / SKILL
        for name in PLAIN_ENGLISH:
            assert (folder / name).read_bytes() == (SOURCE / name).read_bytes(), (host, name)
        # The standard's own word list belongs to its owner and is never shipped.
        assert not (folder / "references/word-list.md").exists()
        assert "word-list.md" not in (folder / "SKILL.md").read_text(encoding="utf-8")
        guide = rule((client / host / "skills/forge/SKILL.md").read_text(encoding="utf-8"))

    # The check tool works without the word list.
    draft = client / "draft.md"
    draft.write_text("Run the tests. The board shows the result.\n", encoding="utf-8")
    checked = subprocess.run([sys.executable, str(client / ".codex" / SKILL / "scripts/ste_check.py"),
                              str(draft)], capture_output=True, text=True)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "word list" not in checked.stdout

    brief = rule((ROOT / "src/forge/templates/brief.md").read_text(encoding="utf-8"))
    for text in (brief, guide):
        for phrase in ("What changes for you", "Done when", "pull request summar", "question",
                       "board"):
            assert phrase in text, phrase
