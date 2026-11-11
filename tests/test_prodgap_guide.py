"""Init and sync deliver what the agent does with each "Before production" gap."""
import re
import shutil
from pathlib import Path

import pytest

from conftest import ROOT
from test_setup import LISTED, _fresh_client, _version
from test_worker import calls, install_claude


STORY = "FORGE-PRODGAP-1"


def _collapsed(path):
    return " ".join(path.read_text(encoding="utf-8").split())


@pytest.fixture(params=["new init", "previous release"])
def delivered(repo, gh, tmp_path, request):
    log = install_claude(repo)
    if request.param == "new init":
        client, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        client = repo.path
        config = client / "forge.toml"
        config.write_text(config.read_text("utf-8").replace(
            'version = "v1.2.2"', f'version = "{_version(repo)}"'), encoding="utf-8")
        repo.git("add", "-A", cwd=client)
        repo.git("commit", "-q", "-m", "Upgrade the earlier client", cwd=client)
        repo.git("push", "-q", "origin", "main", cwd=client)
    started = repo.forge("fix", "start", "Check prodgap guidance", "--done",
                         "The gap guidance is delivered", "--kind", "mechanical", cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    client = client.parent / f"{client.name}-fix-check-prodgap-guidance"
    if request.param == "previous release":
        synced = repo.forge("sync", cwd=client)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        changed = {line.split(None, 1)[1] for line in repo.git(
            "status", "--porcelain", "-uall", cwd=client).splitlines()}
        assert changed <= LISTED  # No app file is written or removed.
    guides = [_collapsed(client / host / "skills/forge/SKILL.md") for host in (".claude", ".codex")]
    config = client / "forge.toml"
    config.write_text(config.read_text("utf-8").replace(
        'workers = "split"', 'workers = "claude"').replace(
        'workers = "codex"', 'workers = "claude"'), encoding="utf-8")
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-q", "-m", "Use the delivered guidance", cwd=client)
    worked = repo.forge("work", "check-prodgap-guidance", cwd=client)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = " ".join(calls(log)[-1]["brief"].split())
    conventions = re.search(r"how-to for each concern .*? in `([^`]+)`", brief)
    assert conventions, brief
    return guides, _collapsed(Path(conventions[1]) / "deploy.md")


AFTER_SIGN_OFF = (
    "After sign-off, read `Before production` in `forge next`.",
    "First check what is already in progress, so no line is started twice.",
    "Leave sample data by the existing step: settle the `Personal data` answer, set the test command "
    "and checks, then the coordinator turns `sample_data` off.",
    'For the light-review line and the "Demo only" line, start one normal change with '
    '`forge start "<your sentence>"`.',
    "Take the work from the row's Say text, but write your own sentence.",
    "Never paste the Say text into a command, because a file name in it can hold shell characters.",
    "Use only letters, digits, spaces and the signs `. , : _ - /` in your sentence, so the double "
    "quotes are safe in every shell.",
    "Name each part the line lists, so the line clears.",
    "Name a file only when its name uses just those signs.",
    "Describe any other file in words, such as the other files with the Demo only label.",
    "A change that touches code has the full review, and its tests follow the repo's settings once "
    "sample data is off.",
    "A fix that changes only documentation gets only the light check, even after sign-off, and the "
    "light-review line does not count it.",
    "If a part in that line changed only documentation, tell the owner: the owner accepts that line "
    "in chat, or the follow-up change includes the code that the documentation describes.",
    "Do not press or ask for Promote while a line is open, unless the owner accepts the rest in chat.",
    "Tell the owner plainly that Forge cannot see the release or whether the app still shows made-up "
    "data, and that it refuses nothing.",
)
FIRST_STEP = "Run `forge next`: no `Before production` line may be open, or the owner accepts the rest in writing."


def test_4_the_guide_says_what_to_do_with_each_gap(delivered):
    guides, deploy = delivered
    for guide in guides:
        for sentence in AFTER_SIGN_OFF:
            assert sentence in guide
        # A start command that holds the row text, in double quotes or bare, would run a file name
        # such as $(id).tsx on the coordinator's machine.
        assert not re.search(r"forge start\s+[\"']?<[^>`]*(?:row|Say)", guide)
    assert FIRST_STEP in deploy
    assert FIRST_STEP in _collapsed(ROOT / "docs/start-a-prototype.md")
    assert "Forge cannot see the release and refuses nothing." in _collapsed(ROOT / "docs/guide.md")
