"""Init and sync deliver the built-in member removal guidance."""
import shutil

import pytest

from conftest import ROOT
from test_setup import LISTED, _fresh_client, _version
from test_worker import install_claude

STORY = "FORGE-MAIL-1/GUIDE"


@pytest.mark.platform
@pytest.mark.parametrize("setup", ["new init", "previous release"])
def test_2_the_guide_states_member_removal(repo, gh, tmp_path, setup):
    install_claude(repo)
    if setup == "new init":
        client, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        client = repo.path
        config = client / "forge.toml"
        config.write_text(config.read_text("utf-8").replace(
            'version = "v1.2.2"', f'version = "{_version(repo)}"'), "utf-8")
        repo.git("add", "-A", cwd=client)
        repo.git("commit", "-q", "-m", "Upgrade the earlier client", cwd=client)
        repo.git("push", "-q", "origin", "main", cwd=client)

    started = repo.forge("fix", "start", "Check member removal guidance", "--done",
                         "The member removal guidance is delivered", "--kind", "mechanical", cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    client = client.parent / f"{client.name}-fix-check-member-removal-guidance"
    if setup == "previous release":
        synced = repo.forge("sync", cwd=client)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        changed = {line.split(None, 1)[1] for line in
                   repo.git("status", "--porcelain", "-uall", cwd=client).splitlines()}
        assert changed <= LISTED

    built_in = ("- Built in: admins invite people by email and remove members, which signs "
                "them out at once; members cannot invite, remove people or change roles.")
    for host in (".claude", ".codex"):
        guide = " ".join((client / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert built_in in guide, host
