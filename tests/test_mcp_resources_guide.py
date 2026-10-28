"""Init, sync and work deliver the resource and prompt guidance contract."""
import shutil

import pytest

from conftest import ROOT
from test_setup import LISTED, _fresh_client, _version
from test_worker import calls, install_claude

STORY = "FORGE-MCPRES-1"


@pytest.mark.platform
@pytest.mark.parametrize("setup", ["new init", "previous release"])
def test_3_the_guides_name_resources_and_prompts(repo, gh, tmp_path, setup):
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

    started = repo.forge("fix", "start", "Check resource guidance", "--done",
                         "The resource guidance is delivered", "--kind", "mechanical", cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    client = client.parent / f"{client.name}-fix-check-resource-guidance"
    if setup == "previous release":
        synced = repo.forge("sync", cwd=client)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        changed = {line.split(None, 1)[1] for line in
                   repo.git("status", "--porcelain", "-uall", cwd=client).splitlines()}
        assert changed <= LISTED  # Sync delivers guidance without writing app files.

    for host in (".claude", ".codex"):
        guide = " ".join((client / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        built_in = ("- Built in: each feature also offers its items, its field guide and its "
                    "allowed values as MCP resources; agents get a prompt only for a task "
                    "under ## Agent tasks; the MCP server never uses elicitation or sampling.")
        assert guide.count(built_in) == 2, host
        for instruction in (
            "In an app with libs/mcp or apps/api/app/mcp, check the client notes",
            "Which tasks will people ask an agent to do again and again?",
            "Write each task under ## Agent tasks",
            "`- <task>: <feature>; inputs: <the inputs it needs>`",
            "With no task, write `- None`",
            "Ask it again only when the person wants to change the list",
            "## Agent tasks - <the task>: <feature>; inputs: <the inputs it needs>, or None",
            "Each feature's resources come from its tools file's `defineFeatureTools` and need no code",
            "the name in the form `<feature>_<verb>`, its inputs and its permission",
            "Write no other prompt. Add no elicitation and never use sampling.",
        ):
            assert instruction in guide, (host, instruction)

    config = client / "forge.toml"
    config.write_text(config.read_text("utf-8").replace(
        'workers = "split"', 'workers = "claude"').replace(
        'workers = "codex"', 'workers = "claude"'), "utf-8")
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-q", "-m", "Use the current resource guidance", cwd=client)
    worked = repo.forge("work", "check-resource-guidance", cwd=client)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = " ".join(calls(log)[-1]["brief"].split())
    for instruction in (
        "A feature's resources come from `defineFeatureTools`; add none by hand",
        "Add a prompt with `definePrompt` only when your part names it, with a strict `arguments` schema and one permission",
        "Never send an elicitation or a sampling request",
    ):
        assert instruction in brief, instruction
