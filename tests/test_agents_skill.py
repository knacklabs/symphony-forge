"""Init, sync and work deliver the approved web-chat agent guidance."""
import json
import shutil

import pytest

from conftest import ROOT
from test_setup import LISTED, _fresh_client
from test_worker import calls, install_claude

STORY = "FORGE-AGENTS-1"

BRIEF = (
    "Before any agent, chat, voice or in-app assistant work, load the agents skill "
    "(.codex/skills/agents/SKILL.md) and follow it. Say which of its sections apply to "
    "your change. A review holds a broken Must rule."
)
COORDINATOR = (
    "Follow the agents skill (.codex/skills/agents/SKILL.md) for any agent, chat, voice "
    "or in-app assistant work. When a part adds one, the plan names the skill's sections "
    "that apply and the model service it uses."
)


@pytest.fixture
def client(repo, gh, tmp_path, adoption):
    if adoption == "new init":
        path, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        path = repo.path
        config = path / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        config.write_text(config.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)),
                          encoding="utf-8")
        agent = path / "apps/api/agent.py"
        agent.parent.mkdir(parents=True, exist_ok=True)
        agent.write_text("# Existing agent keeps its own implementation.\n", encoding="utf-8")
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "Keep the earlier app")
        repo.git("push", "-q", "origin", "main")
        before = {file.relative_to(path).as_posix(): file.read_bytes()
                  for file in (path / "apps").rglob("*") if file.is_file()}
        repo.git("checkout", "-b", "fix/agent-guidance")
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
        assert {file.relative_to(path).as_posix(): file.read_bytes()
                for file in (path / "apps").rglob("*") if file.is_file()} == before
        changed = {line.split(None, 1)[1] for line in
                   repo.git("status", "--porcelain", "-uall").splitlines()}
        assert changed <= LISTED
        repo.git("checkout", "main")
    return path


@pytest.mark.platform
@pytest.mark.parametrize("adoption", ["new init", "earlier adopted"])
def test_1_new_and_existing_repos_get_the_agents_skill(client):
    # Audit: delivery and the approved guidance are the contract. Missing shipping or rule
    # text breaks it; database coverage cannot see either. Real init/sync needs no new seam.
    for host in (".claude", ".codex"):
        target = client / host / "skills/agents/SKILL.md"
        assert target.is_file(), f"{host} did not receive agent guidance"
        assert target.read_bytes() == (
            ROOT / "src/forge/templates/skills/agents/SKILL.md").read_bytes()
        text = target.read_text("utf-8")
        assert [line[3:] for line in text.splitlines() if line.startswith("## ")] == [
            "One message, end to end", "Agent shape before any code", "The turn",
            "Fast decisions before the model", "Context and the prompt cache",
            "Memory: writing", "Memory: recall", "Tool design", "Output and side effects",
            "Safety and privacy", "Spoken chat", "Cost and tracing", "Testing and prompt changes",
        ]
        rules = text.split("\n### ")[1:]
        assert len(rules) == 60
        assert sum(rule.splitlines()[2].startswith("**Must.**") for rule in rules) == 55
        assert sum(rule.splitlines()[2].startswith("**Should.**") for rule in rules) == 5
        assert all("\nDefault: " in rule for rule in rules)
        for term in ("WhatsApp and phone calls are not covered", "MAINLINE_AI_KEY", "Can use list",
                     "interrupt()", "recursion_limit",
                     "Check the current docs before relying on exact APIs."):
            assert term in text


@pytest.mark.platform
@pytest.mark.parametrize("adoption", ["new init", "earlier adopted"])
def test_2_the_brief_and_the_coordinator_name_the_skill(repo, client, adoption):
    # Audit: the worker's actual prompt and both delivered guides must name the skill.
    # A missing prompt paragraph is invisible to the delivery test. Only the host is faked.
    for host in (".claude", ".codex"):
        guide = " ".join((client / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert guide.count(COORDINATOR) == 2, host
        planning = guide.split("## Planning a story", 1)[1].split(" ## ", 1)[0]
        assert planning.count(COORDINATOR) == 1, host
        description = next(line for line in (client / host / "skills/agents/SKILL.md")
                           .read_text("utf-8").splitlines() if line.startswith("description:"))
        assert "agent, chat, voice or in-app assistant work" in description

    started = repo.forge("fix", "start", "Check agent guidance", "--done",
                         "Agent guidance reaches the worker", "--kind", "mechanical", cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    client = client.parent / f"{client.name}-fix-check-agent-guidance"
    if adoption == "earlier adopted":
        synced = repo.forge("sync", cwd=client)
        assert synced.returncode == 0, synced.stdout + synced.stderr

    log = install_claude(repo)
    config = client / "forge.toml"
    config.write_text(config.read_text("utf-8").replace(
        'workers = "split"', 'workers = "claude"').replace(
        'workers = "codex"', 'workers = "claude"'), encoding="utf-8")
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-q", "-m", "Use the current guidance", cwd=client)
    worked = repo.forge("work", "check-agent-guidance", cwd=client)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    assert BRIEF in " ".join(calls(log)[-1]["brief"].split())
