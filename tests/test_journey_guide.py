"""The published journey and agent prompts reach new and earlier-adopted clients."""
import re
import shutil

import pytest

from conftest import ROOT
from test_setup import _fresh_client, _version
from test_worker import calls, install_claude

STORY = "FORGE-JOURNEY-1"
STEPS = (
    "Ideas and client notes", "Brief", "Canvas design", "Sign-off", "Build",
    "Deploy on Mainline", "Run and improve",
)
FIRST_INPUT = ("Tell the person the seven steps in the Forge guide's journey, then ask "
               "for the client notes or the idea.")


@pytest.fixture(params=["new init", "previous release"])
def journey_client(repo, gh, tmp_path, request):
    if request.param == "new init":
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        client, initialized = repo.path, None
        config = client / "forge.toml"
        config.write_text(config.read_text("utf-8").replace(
            'version = "v1.2.2"', f'version = "{_version(repo)}"'), "utf-8")
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "Upgrade the earlier client")
        repo.git("push", "-q", "origin", "main")
    started = repo.forge("fix", "start", "Check journey guidance", "--done",
                         "The journey guidance is delivered", "--kind", "mechanical", cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    client = client.parent / f"{client.name}-fix-check-journey-guidance"
    if initialized is None:
        synced = repo.forge("sync", cwd=client)
        assert synced.returncode == 0, synced.stdout + synced.stderr
    return client, initialized


def _guides(client):
    return [(client / host / "skills/forge/SKILL.md").read_text("utf-8")
            for host in (".claude", ".codex")]


def _assert_journey(section):
    steps = re.findall(r"^\d+\. \*\*(.+?)\.\*\* (.+)$", section, re.M)
    assert [name for name, _ in steps] == list(STEPS)
    for _, text in steps:
        assert 'You can say: "' in text
        assert text.split("You can say:")[0].strip()
    for heading, reason in (
        ("The cold read loop", "It exists because"),
        ("The build and review loop", "It exists because"),
        ("The CI checks", "They exist because"),
    ):
        paragraph = section.split(f"**{heading}.**", 1)[1].split("\n\n", 1)[0]
        assert reason in paragraph


@pytest.mark.platform
def test_1_the_guide_and_readme_teach_the_seven_steps(journey_client):
    client, initialized = journey_client
    for guide in _guides(client):
        journey = guide.split("## The journey\n", 1)[1].split("\n## ", 1)[0]
        _assert_journey(journey)
    if initialized is not None:
        readme = (ROOT / "README.md").read_text("utf-8")
        journey = readme.split("## From idea to production\n", 1)[1].split("\n## ", 1)[0]
        _assert_journey(journey)
        assert "| Stage |" not in journey


@pytest.mark.platform
def test_2_the_agent_explains_the_steps_and_refusals(repo, journey_client):
    client, initialized = journey_client
    for guide in _guides(client):
        guide = " ".join(guide.split())
        for instruction in (
            "After `forge init` in a new repo, tell the person the seven steps in one line each, then ask for the first input: the client notes or the idea.",
            'When a person asks what they can do, or seems unsure, run `forge next`, name the current step from its first line, and show that step\'s "You can say" phrases. Name no commands.',
            "When a Forge command refuses, tell the person in plain words what Forge stopped, why, and the fix that it names.",
            "offer to file a Forge bug as Reporting a Forge bug, below, says. File it when the person agrees.",
        ):
            assert instruction in guide
    if initialized is not None:
        assert FIRST_INPUT + "\nNext: forge next\n" in initialized.stdout

    log = install_claude(repo)
    config = client / "forge.toml"
    config.write_text(config.read_text("utf-8").replace(
        'workers = "split"', 'workers = "claude"').replace(
        'workers = "codex"', 'workers = "claude"'), "utf-8")
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-q", "-m", "Use the current journey guidance", cwd=client)
    worked = repo.forge("work", "check-journey-guidance", cwd=client)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = " ".join(calls(log)[-1]["brief"].split())
    assert ("When a forge command refuses, say in your last message what it refused, why, "
            "and the fix it named, in plain words. Say so when the refusal looks like a "
            "fault in Forge itself.") in brief
