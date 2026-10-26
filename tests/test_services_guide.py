"""Init, sync and work deliver the services list prompt contract."""
import shutil

import pytest

from conftest import ROOT
from test_setup import _fresh_client, _version
from test_worker import calls, install_claude

STORY = "FORGE-SERVICES-1"


@pytest.mark.platform
@pytest.mark.parametrize("setup", ["new init", "previous release"])
def test_3_the_guides_name_the_services_list(repo, gh, tmp_path, setup):
    log = install_claude(repo)
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

    started = repo.forge("fix", "start", "Check services guidance", "--done",
                         "The services guidance is delivered", "--kind", "mechanical", cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    client = client.parent / f"{client.name}-fix-check-services-guidance"
    config = client / "forge.toml"
    config.write_text(config.read_text("utf-8").replace(
        'workers = "split"', 'workers = "claude"').replace(
        'workers = "codex"', 'workers = "claude"'), "utf-8")
    if setup == "previous release":
        synced = repo.forge("sync", cwd=client)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        assert not (client / "services.toml").exists()
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-q", "-m", "Use the current services guidance", cwd=client)
    worked = repo.forge("work", "check-services-guidance", cwd=client)
    assert worked.returncode == 0, worked.stdout + worked.stderr

    for host in (".claude", ".codex"):
        guide = " ".join((client / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        top = guide.split("| The human says |", 1)[0]
        for instruction in (
            "Our deploy platform reads `services.toml` at the repo root",
            "When a client repo has a Dockerfile and no `services.toml`, write it before the first deployment the owner asks for",
            "one service per Dockerfile the app runs",
            "the port from its `EXPOSE` line and the health path from the code",
            "Show it to the owner and ask with options: confirm it, or change a service's exposure",
            "Then merge it in a fix",
            "the list does not hold it",
        ):
            assert instruction in top, (host, instruction)
        assert ("10. When the repo has a Dockerfile, write `services.toml` as the deploy paragraph "
                "at the top of this guide says, get the human's confirmation, and add it to the adoption fix.") in guide

    brief = " ".join(calls(log)[-1]["brief"].split())
    for instruction in (
        "when a change adds, moves or removes a Dockerfile, or changes a service's port, health path or start command, update `services.toml` in the same change",
        "Close refuses a `services.toml` that names a Dockerfile the branch does not have",
        'exactly one service with `expose = "main"`',
        "In a repo without `services.toml`, do not create one: the coordinator writes the first list with the owner's confirmation",
    ):
        assert instruction in brief, instruction
    # Conventions are installed with Forge; the worker receives this directory.
    deploy = " ".join((ROOT / "src/forge/templates/conventions/deploy.md").read_text("utf-8").split())
    for instruction in ("`services.toml`", "`main`", "`subdomain`", "`internal`",
                        "Exactly one service is `main`", "One release builds every service",
                        "a rollback rolls them all back", "choose its main subdomain; the list does not hold it"):
        assert instruction in deploy, instruction
