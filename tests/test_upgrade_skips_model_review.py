"""An upgrade fix that holds only the version line and Forge's own synced files skips the model review."""
import shutil

import pytest

import conftest
from test_close import GREEN, env  # noqa: F401
from test_setup import _fresh_client
from test_upgrade_command import NAME, RELEASE, Upgrade, unsynced_up  # noqa: F401

STORY = "FIX-UPGRADE-NO-MODEL-REVIEW"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_1_pure_upgrade_skips_review_and_extra_edit_gets_one(unsynced_up, adopted):
    up = unsynced_up
    if adopted:
        shutil.copytree(conftest.ROOT / "tests/fixtures/adopted-v1.2.2/client",
                        up.repo.path, dirs_exist_ok=True)
        up.repo.git("switch", "-q", "-c", "adoption")
        up.repo.git("add", "-A")
        up.repo.git("commit", "-q", "-m", "Adopt the earlier release")
        up.repo.git("switch", "-q", "main")
        up.repo.git("merge", "-q", "--ff-only", "adoption")
        up.repo.git("push", "-q", "origin", "main")
    else:
        client, initialized = _fresh_client(up.repo, up.env.gh, up.tmp)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        up.repo.path = client
        up = Upgrade(up.env, up.tmp)
        up.env.checks(GREEN)

    upgraded = up.run(RELEASE)

    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    assert up.env.review_calls() == []

    # One hand-edited file turns the same fix back into a normal reviewed change.
    (up.folder / "docs").mkdir(exist_ok=True)
    (up.folder / "docs" / "notes.md").write_text("hand edit\n", encoding="utf-8")
    up.repo.git("add", "docs/notes.md", cwd=up.folder)
    up.repo.git("-c", f"core.hooksPath={up.tmp / 'no-hooks'}", "commit", "-q", "-m", "Add a note",
                cwd=up.folder)
    closed = up.repo.forge("close", NAME, cwd=up.folder)

    assert len(up.env.review_calls()) == 1, closed.stdout + closed.stderr
