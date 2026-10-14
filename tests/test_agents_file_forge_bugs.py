"""Every Forge repo tells agents to file a Forge bug with the bug template."""
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
    assert "with the Forge bug template's sections, fill every one" in agents
    assert "leave out the repo's code, names, paths and secrets" in agents


PROMPTS = ("forge version", "pinned version", "host", "operating system",
           "exact command and full output", "expected vs what happened",
           "steps to reproduce", "upgraded from which version", "new or adopted repo",
           "workaround", "forge.toml settings without secrets",
           "forge next", "what was tried", "how often",
           "no client code, names, paths or secrets")


def test_2_template_and_guide_ask_for_every_required_prompt(repo, gh, tmp_path):
    client, made = _fresh_client(repo, gh, tmp_path)
    assert made.returncode == 0, made.stdout + made.stderr
    texts = {"template": TEMPLATE.read_text("utf-8")}
    for host in (".claude", ".codex"):
        texts[host + " guide"] = (client / host / "skills/forge/SKILL.md").read_text("utf-8")
    for name, text in texts.items():
        flat = " ".join(text.lower().split())
        for prompt in PROMPTS:
            assert prompt in flat, (name, prompt)
        if name != "template":
            assert ('contents/.github/issue_template/forge-bug.md -h "accept: '
                    'application/vnd.github.raw"') in flat
            assert "--title \"<short plain title>\" --body-file <that file>" in flat
            assert "--label" not in flat and "> forge-bug.md" not in flat
