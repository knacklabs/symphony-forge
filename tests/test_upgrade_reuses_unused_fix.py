"""Drop and restore records must not block an unused upgrade fix name.

Existing upgrade coverage reaches interrupted runs, not these lifecycle states.
The real commands own the outcome; only external tools use the shared fakes.
"""
import shutil
from pathlib import Path

import pytest

from test_close import env  # noqa: F401
from test_upgrade_command import NAME, RELEASE, assert_ready, ours, up, unsynced_up  # noqa: F401

STORY = "fix-upgrade-reuses-dropped-fix"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("lifecycle,adopted", [("dropped", False), ("restored", False),
                                                ("dropped", True), ("work", False)])
def test_1_upgrade_reuses_unused_fix_or_names_the_recovery_command(unsynced_up, request,
                                                                  lifecycle, adopted):
    upgrade = unsynced_up if adopted else request.getfixturevalue("up")
    if adopted:
        shutil.copytree(Path(__file__).parent / "fixtures/doctor-v1.2.2", upgrade.repo.path,
                        dirs_exist_ok=True)
        text = upgrade.toml().replace('test = "npm test"', 'test = "python -c \'pass\'"')
        (upgrade.repo.path / "forge.toml").write_text(text, "utf-8")
        upgrade.repo.git("switch", "-qc", "adoption")
        upgrade.repo.git("add", "-A")
        upgrade.repo.git("commit", "-qm", "Adopt the earlier release")
        upgrade.repo.git("switch", "-q", "main")
        upgrade.repo.git("merge", "-q", "--ff-only", "adoption")
        upgrade.repo.git("push", "-q", "origin", "main")
    repo = upgrade.repo
    started = repo.forge("fix", "start", "Prepare the Forge release", "--done",
                         "The repo uses the new release", "--slug", NAME)
    assert started.returncode == 0, started.stdout + started.stderr
    if lifecycle == "work":
        upgrade.env.commit(upgrade.folder, "README.md", "Keep the real work\n")
    dropped = repo.forge("fix", "drop", NAME, "--because", "Use the upgrade command")
    assert dropped.returncode == 0, dropped.stdout + dropped.stderr
    if lifecycle == "restored":
        restored = repo.forge("fix", "drop", NAME, "--undo")
        assert restored.returncode == 0, restored.stdout + restored.stderr
    before = repo.git("rev-parse", f"origin/fix/{NAME}")

    done = upgrade.run(RELEASE)

    if lifecycle == "work":
        assert done.returncode == 1
        assert done.stderr.endswith(f"Next: forge fix drop {NAME} --undo\n")
        assert repo.git("rev-parse", f"origin/fix/{NAME}") == before
        assert not upgrade.folder.exists()
        assert upgrade.uv() == []
    else:
        assert_ready(upgrade, done, ours(upgrade, started=False))
        assert f'version = "{RELEASE}"' in upgrade.show("forge.toml")
        assert repo.git("merge-base", "--is-ancestor", before, f"fix/{NAME}") == ""
