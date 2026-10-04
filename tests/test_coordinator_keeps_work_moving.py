"""Clients receive coordinator recovery guidance, and close points to it on a conflict."""
import shutil
from pathlib import Path

import pytest

from test_close import env  # noqa: F401
from test_setup import _fresh_client

STORY = "FIX-A-CLIENT-S-COORDINATING-AGENT-HAS-NO-SHI"


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "previously-adopted-client"])
def test_1_synced_skill_explains_keeping_work_moving_and_close_names_it(env, tmp_path, previous):
    repo = env.repo
    if previous:
        client = tmp_path / "previous-client"
        shutil.copytree(Path(__file__).parent / "fixtures/adopted-v1.2.2/client", client)
        repo.git("init", "-q", "-b", "fix/coordinator-guide", str(client))
        config = client / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        config.write_text(config.read_text().replace('version = "v1.2.2"',
                                                    f'version = "{version}"'), encoding="utf-8")
    else:
        client, initialized = _fresh_client(repo, env.gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr

    item, where = env.start_fix({"README.md": "# Hello, shoppers\n"})
    env.commit(repo.path, "README.md", "# Welcome\n")
    repo.git("push", "-q", "origin", "main")
    refused = env.close(item)
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "Merging main into fix/tidy-readme conflicts in README.md." in refused.stderr
    assert "Keeping work moving" in refused.stderr
    assert "then forge close tidy-readme" in refused.stderr
    assert repo.git("status", "--porcelain", cwd=where) == ""

    for host in (".claude", ".codex"):
        skill = client / host / "skills/forge/SKILL.md"
        assert f"{host}/skills/forge/SKILL.md" in refused.stderr
        section = skill.read_text(encoding="utf-8").split("## Keeping work moving\n", 1)[1]
        flat = " ".join(section.split("\n## ", 1)[0].split())
        for instruction in (
            "`forge land <item>`", "build, close, fix rounds and merge",
            "`forge work <item> --note", "`forge task start <KEY>/<TASK>`",
            "`forge fix start", "team-owned", "`forge.toml`", "pinned Forge",
            "`forge sync`", "approval", "cold-read", "stage only resolved paths",
            "overlapping work", "other ready work", "`forge next` after each merge",
            "`forge doctor --fix`",
        ):
            assert instruction in flat, instruction
