"""Forge delivers deployment authorization guidance, without deploying or installing Mainline.

This prompt delivery contract belongs at init/sync and work, rather than source greps.
A missing host copy or upgrade delivery fails it; no production test seam is needed.
"""
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT, FORGE_SHIM, _install
from test_setup import _fresh_client, _version
from test_worker import calls, install_claude

STORY = "FIX-MAINLINE-EXPLICIT-DEPLOY"


@pytest.mark.parametrize("setup", ["new", "previous-release adoption"])
def test_1_clients_receive_explicit_deployment_authorization(repo, gh, tmp_path, setup):
    log = install_claude(repo)
    if setup == "new":
        client, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
        started = repo.forge("fix", "start", "Check deployment instructions", "--done",
                             "Agents receive deployment instructions", cwd=client)
        assert started.returncode == 0, started.stdout + started.stderr
        client = tmp_path / "client-fix-check-deployment-instructions"
        item = "check-deployment-instructions"
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
        assert made.returncode == 0, made.stdout + made.stderr
        client = tmp_path / "repo-fix-adopt-forge"
        item = "adopt-forge"
        assert "Mainline Deploy" not in (client / "AGENTS.md").read_text("utf-8")
    config = client / "forge.toml"
    text = config.read_text("utf-8").replace('version = "v1.2.2"',
                                            f'version = "{_version(repo)}"')
    text = text.replace('workers = "split"', 'workers = "claude"').replace(
        'workers = "codex"', 'workers = "claude"')
    config.write_text(text, "utf-8")
    if setup != "new":
        synced = repo.forge("sync", cwd=client)
        assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-q", "-m", "Use the current client guidance", cwd=client)
    worked = repo.forge("work", item, cwd=client)
    assert worked.returncode == 0, worked.stdout + worked.stderr

    delivered = {"worker brief": calls(log)[-1]["brief"],
                 "AGENTS.md": (client / "AGENTS.md").read_text("utf-8")}
    delivered["installed deploy convention"] = (
        ROOT / "src/forge/templates/conventions/deploy.md").read_text("utf-8")
    for host in (".claude", ".codex"):
        delivered[host + " guide"] = (client / host / "skills/forge/SKILL.md").read_text("utf-8")
    for name, content in delivered.items():
        text = " ".join(content.split())
        for instruction in (
            "available to install through the organization's plugin catalog",
            "Do not assume that the plugin and MCP are installed or that the user is signed in",
            "First check whether it is installed in the current host",
            "host's installation flow",
            "Do not invent an installation command or marketplace address",
            "Check OAuth sign-in and have the user complete it if needed",
            "Wait for successful authentication before deployment",
            "Installation alone does not mean the user is signed in",
            "Do not install Mainline or start OAuth sign-in for those requests",
            "only when the user explicitly requests deployment",
            "Then follow the Mainline Deploy skill",
            "requested app to the requested environment",
            "does not by itself authorize deployment",
            "build, fix, merge, ship/land request",
            "successful test or review, demo preparation, or Forge next step",
        ):
            assert instruction in text, (name, instruction)
    for name in (".claude guide", ".codex guide"):
        text = " ".join(delivered[name].split())
        assert "Say a version is live only after the requested deployment is verified" in text
        assert 'the demo: "the next version is live"' not in text
