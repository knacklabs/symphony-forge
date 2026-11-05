"""Init, sync and work deliver the after-demo instructions."""
import re
import shutil
from pathlib import Path

import pytest

from conftest import ROOT
from test_setup import LISTED, _fresh_client, _version
from test_worker import calls, install_claude

STORY = "FORGE-AFTERDEMO-1"
WAITING = (
    "Add `notify` in the same transaction as the change that makes a record wait; "
    "add `resolve` in the transaction of the action. "
    "A reassignment is `resolve` then `notify` in one transaction."
)
BUILT_IN = "- Built in: the API lists each person's waiting records with a count."
BACKUP = (
    "When a release adds a migration file, Mainline takes a backup at Promote. "
    "Mainline runs one test restore before the first launch. "
    "Mainline checks the release for the added file itself and does both; "
    "the agent does neither and writes no mark. "
    "The migration rule belongs to FORGE-EXPAND-1."
)


def _collapsed(path):
    return " ".join(path.read_text(encoding="utf-8").split())


@pytest.fixture(params=["new init", "previous release"])
def delivered(repo, gh, tmp_path, request):
    # Audit: three distinct delivered prompt contracts; missing text or stale sync is the
    # regression. Other guide tests cover other rules. Real init/sync/work own delivery;
    # only the external worker is stubbed. No production seam is needed.
    log = install_claude(repo)
    if request.param == "new init":
        client, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        client = repo.path
        config = client / "forge.toml"
        config.write_text(config.read_text("utf-8").replace(
            'version = "v1.2.2"', f'version = "{_version(repo)}"'), encoding="utf-8")
        repo.git("add", "-A", cwd=client)
        repo.git("commit", "-q", "-m", "Upgrade the earlier client", cwd=client)
        repo.git("push", "-q", "origin", "main", cwd=client)
    started = repo.forge("fix", "start", "Check after demo guidance", "--done",
                         "The after demo guidance is delivered", "--kind", "mechanical", cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    client = client.parent / f"{client.name}-fix-check-after-demo-guidance"
    if request.param == "previous release":
        synced = repo.forge("sync", cwd=client)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        changed = {line.split(None, 1)[1] for line in repo.git(
            "status", "--porcelain", "-uall", cwd=client).splitlines()}
        assert changed <= LISTED  # No app file is written or removed.
    guides = [_collapsed(client / host / "skills/forge/SKILL.md")
              for host in (".claude", ".codex")]
    config = client / "forge.toml"
    config.write_text(config.read_text("utf-8").replace(
        'workers = "split"', 'workers = "claude"').replace(
        'workers = "codex"', 'workers = "claude"'), encoding="utf-8")
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-q", "-m", "Use the delivered guidance", cwd=client)
    worked = repo.forge("work", "check-after-demo-guidance", cwd=client)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = " ".join(calls(log)[-1]["brief"].split())
    conventions = re.search(r"how-to for each concern .*? in `([^`]+)`", brief)
    assert conventions, brief
    return guides, brief, _collapsed(Path(conventions[1]) / "deploy.md")


@pytest.mark.platform
def test_2_the_guide_says_how_a_record_waits_for_a_person(delivered):
    guides, brief, _ = delivered
    for guide in guides:
        assert "## Waiting records" in guide
        assert WAITING in guide
        assert guide.count(BUILT_IN) == 2
        for text in (
            "`NotificationsApi`", "`NOTIFICATIONS_API`", "`NotificationsPrincipal = { id, organisationId }`",
            "`notify(principal, recipientAccountId, subjectId, subjectName, message, tx?)`",
            "`resolve(principal, subjectId, tx?)`", "`NotificationsService`",
            "`notify(account, recipient_account_id, subject_id, subject_name, message)`",
            "`resolve(account, subject_id)`", "`GET /api/v1/notifications`", "`data: { count, items }`",
            "Build the list and the count in the client's design, as FORGE-NOSCREENS-1 requires.",
            "No email until the SNS story.",
            "An app without the `notifications` module gets it by hand, from these names, when a feature first needs it.",
        ):
            assert text in guide, text
    assert WAITING in brief
    assert "No email until the SNS story." in brief
    assert "Build the list and the count in the client's design" in brief


@pytest.mark.platform
def test_3_the_guide_turns_demo_notes_into_one_list(delivered):
    for guide in delivered[0]:
        assert "[After a demo](#after-a-demo)" in guide
        for text in (
            "Save the notes or transcript in `docs/context/` and read them all.",
            "Show one list of changes, one line per change, in the client's words, with who asked and which screen or record it touches.",
            "Two ideas in one sentence become two lines.",
            'Put questions the notes leave open below the list as "Need an answer".',
            'The FDE answers once: OK, or edits.',
            'After the OK, run `forge start "<change>"` for each line; Forge picks a fix or a story for each.',
            "Nothing starts before the OK. The OK is the FDE's reply; Forge stores no record of it.",
            'A change the FDE says can wait goes to the later list with `forge start "Do this later: <idea>"`, after the OK.',
        ):
            assert text in guide, text


@pytest.mark.platform
def test_4_the_guide_names_the_backup_and_the_test_restore(delivered):
    guides, _, deploy = delivered
    for guide in guides:
        journey = guide.split("6. **Deploy on Mainline.**", 1)[1].split("7. **Run and improve.**", 1)[0]
        assert BACKUP in journey
    assert BACKUP in deploy
