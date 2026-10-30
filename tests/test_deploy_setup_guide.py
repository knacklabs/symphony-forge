"""Init, sync and work deliver the one-time deploy setup prompt contract."""
import shutil

import pytest

from conftest import ROOT
from test_setup import _fresh_client, _version
from test_worker import calls, install_claude

STORY = "FORGE-DEPLOY-1"


@pytest.mark.platform
@pytest.mark.parametrize("setup", ["new init", "previous release"])
def test_1_the_guides_give_the_one_time_deploy_setup(repo, gh, tmp_path, setup):
    # Audit: protect the delivered setup order and the after-setup deploy rules.
    # Missing or reordered instructions, or a lost upgrade copy, fail this contract.
    # Services and explicit-request tests own different instructions, not these rules.
    # Use real init/sync/work with the existing external Claude stub; no new seam.
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

    started = repo.forge("fix", "start", "Check deploy setup guidance", "--done",
                         "The deploy setup guidance is delivered", "--kind", "mechanical", cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    client = client.parent / f"{client.name}-fix-check-deploy-setup-guidance"
    config = client / "forge.toml"
    config.write_text(config.read_text("utf-8").replace(
        'workers = "split"', 'workers = "claude"').replace(
        'workers = "codex"', 'workers = "claude"'), "utf-8")
    if setup == "previous release":
        synced = repo.forge("sync", cwd=client)
        assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-q", "-m", "Use the current deploy setup guidance", cwd=client)
    worked = repo.forge("work", "check-deploy-setup-guidance", cwd=client)
    assert worked.returncode == 0, worked.stdout + worked.stderr

    steps = (
        "sign in in the browser with Google or GitHub, and wait until the sign-in succeeds",
        "Connect the client GitHub repository",
        "Read `services.toml`",
        "get the owner's confirmation",
        "Set the main subdomain that the owner picks",
        "Set each variable that `.env.example` names",
        "Deploy dev, and wait until dev reports healthy. Always deploy dev first",
    )
    for host in (".claude", ".codex"):
        guide = " ".join((client / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        top = guide.split("| The human says |", 1)[0]
        for instruction in (
            "is its deploy setup, and that request is the explicit request above",
            "skip a step that is already done",
            *steps,
            "except the ones that the platform provides, such as `DATABASE_URL`",
            "After the setup, do not deploy",
            "Mainline deploys dev at each merge to the default branch and a preview for each pull request",
            "Production changes only when a person presses Promote in Mainline",
            "Never deploy or promote production, also when the owner asks: tell them to press Promote in Mainline",
            "When the owner asks for another deployment after the setup, tell them that Mainline deploys dev at the next merge",
        ):
            assert instruction in top, (host, instruction)
        positions = [top.index(step) for step in steps]
        assert positions == sorted(positions), host

    brief = " ".join(calls(log)[-1]["brief"].split())
    for instruction in (
        "A worker never deploys",
        "Mainline deploys dev at each merge to the default branch and a preview for each pull request",
        "production changes only when a person presses Promote in Mainline",
        "Never deploy or promote production",
    ):
        assert instruction in brief, instruction
    # Conventions are installed with Forge; the worker receives this directory.
    deploy = " ".join((ROOT / "src/forge/templates/conventions/deploy.md").read_text("utf-8").split())
    for instruction in (
        "is the deploy setup, once for each repository",
        "and dev first",
        "Mainline deploys dev at each merge to the default branch and a preview for each pull request",
        "Production changes only when a person presses Promote in Mainline",
        "an agent never deploys or promotes production",
    ):
        assert instruction in deploy, instruction
