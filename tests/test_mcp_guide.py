"""Init, sync and work deliver the MCP guide and tool rules."""
import shutil

import pytest

from conftest import ROOT
from test_setup import LISTED, _fresh_client, _version
from test_worker import calls, install_claude


@pytest.mark.platform
@pytest.mark.parametrize("setup", ["new init", "previous release"])
def test_5_the_guides_name_the_mcp_server(repo, gh, tmp_path, setup):
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

    started = repo.forge("fix", "start", "Check MCP guidance", "--done",
                         "The MCP guidance is delivered", "--kind", "mechanical", cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    client = client.parent / f"{client.name}-fix-check-mcp-guidance"
    if setup == "previous release":
        synced = repo.forge("sync", cwd=client)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        assert not (client / "services.toml").exists()
        changed = {line.split(None, 1)[1] for line in
                   repo.git("status", "--porcelain", "-uall", cwd=client).splitlines()}
        assert changed <= LISTED

    for host in (".claude", ".codex"):
        guide = " ".join((client / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        built_in = ("- Built in: the API serves an MCP server at /mcp. An admin adds agent "
                    "accounts on the Members screen, with a role and a key that shows once; "
                    "agents use each feature's tools with that role's permissions, and delete "
                    "and restore tools stay off until an admin turns them on for the feature.")
        assert guide.count(built_in) == 2, host  # TypeScript and Python fixed rules
        for instruction in (
            'mcp = "/mcp"', "each feature's agent tools are in its one tools file",
            "libs/<plural>/server/src/<plural>.tools.ts", "apps/api/app/<plural>/tools.py",
            "idempotency_key", "retryable", "response_format", "structuredContent",
            "retry_after_seconds", "readOnlyHint", "destructiveHint", "idempotentHint",
            "openWorldHint", "10 seconds", "every tool",
        ):
            assert instruction in guide, (host, instruction)

    config = client / "forge.toml"
    config.write_text(config.read_text("utf-8").replace(
        'workers = "split"', 'workers = "claude"').replace(
        'workers = "codex"', 'workers = "claude"'), "utf-8")
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-q", "-m", "Use the current MCP guidance", cwd=client)
    worked = repo.forge("work", "check-mcp-guidance", cwd=client)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = " ".join(calls(log)[-1]["brief"].split())
    for instruction in (
        "a feature's agent tools are in its tools file", "never return an HTTP status",
        "Never call a feature's service from the MCP module", "or MCP path",
        "defineTool", "ToolError", "Hide a default tool only with `hide`",
        "every tool has a description, annotations, schemas and the error shape",
    ):
        assert instruction in brief, instruction
    # Conventions ship in Forge's installed package, whose directory the worker receives.
    deploy_path = ROOT / "src/forge/templates/conventions/deploy.md"
    assert str(deploy_path.parent) in calls(log)[-1]["brief"]
    deploy = " ".join(deploy_path.read_text("utf-8").split())
    assert "Mainline shows it under Connectors" in deploy
