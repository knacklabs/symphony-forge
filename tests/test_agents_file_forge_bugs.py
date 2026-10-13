"""Every Forge repo tells agents to file a Forge bug with the bug template."""
import re
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT, FORGE_SHIM, _install
from test_setup import _fresh_client, _version

STORY = "report-forge-bugs"
TEMPLATE = ROOT / ".github/ISSUE_TEMPLATE/forge-bug.md"


@pytest.mark.parametrize("setup", ["new", "previous-release adoption"])
def test_1_clients_are_told_to_file_forge_bugs(repo, gh, tmp_path, setup):
    if setup == "new":
        client, made = _fresh_client(repo, gh, tmp_path)
    else:
        old = tmp_path / "previous-release"
        shutil.copytree(ROOT / "tests/fixtures/forge-v1.2.2", old)
        (old / "src/forge/cli-py.txt").rename(old / "src/forge/cli.py")
        _install(repo.bin, "old-forge", FORGE_SHIM.format(
            python=sys.executable, src=str(old / "src")))
        gh.respond("api", stdout="{}")
        made = subprocess.run([sys.executable, str(repo.bin / "old-forge"), "init",
                               "--test", "echo ok", "--checks", "tests",
                               "--interfaces", "api/routes/**", "--approver", "Owner",
                               "--merger", "Owner"], cwd=repo.path,
                              capture_output=True, text=True)
        client = repo.path.parent / "repo-fix-adopt-forge"
    assert made.returncode == 0, made.stdout + made.stderr
    if setup != "new":
        assert "Forge bug" not in (client / "AGENTS.md").read_text("utf-8")
        config = client / "forge.toml"
        config.write_text(config.read_text("utf-8").replace(
            'version = "v1.2.2"', f'version = "{_version(repo)}"'), "utf-8")
        synced = repo.forge("sync", cwd=client)
        assert synced.returncode == 0, synced.stdout + synced.stderr
    agents = " ".join((client / "AGENTS.md").read_text("utf-8").split())
    assert "file a bug on Forge's GitHub" in agents
    assert "Forge bug" in agents
    assert "leave out the repo's code, names, paths and secrets" in agents


def test_2_guide_names_every_bug_template_section(repo, gh, tmp_path):
    client, made = _fresh_client(repo, gh, tmp_path)
    assert made.returncode == 0, made.stdout + made.stderr
    sections = re.findall(r"^## (.+)$", TEMPLATE.read_text("utf-8"), re.M)
    assert len(sections) >= 8
    for host in (".claude", ".codex"):
        guide = " ".join((client / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "gh issue create --repo knacklabs/symphony-forge --title" in guide
        assert "--label bug --body-file" in guide
        for section in sections:
            assert section in guide, (host, section)
