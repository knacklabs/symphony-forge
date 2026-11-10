"""Drop and restore records must not block an unused upgrade fix name.

Existing upgrade coverage reaches interrupted runs, not these lifecycle states.
The real commands own the outcome; only external tools use the shared fakes.
"""
import shutil
from pathlib import Path

import pytest

from conftest import Repo
from test_close import env  # noqa: F401
from test_upgrade_command import NAME, RELEASE, assert_ready, ours, up, unsynced_up  # noqa: F401

STORY = "fix-upgrade-reuses-dropped-fix"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("lifecycle,adopted", [("dropped", False), ("restored", False),
                                                ("dropped", True), ("work", False),
                                                ("remote work", False), ("unfetched", False),
                                                ("dirty", False), ("active", False)])
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
    if lifecycle != "active":
        dropped = repo.forge("fix", "drop", NAME, "--because", "Use the upgrade command")
        assert dropped.returncode == 0, dropped.stdout + dropped.stderr
    if lifecycle in ("restored", "dirty"):
        restored = repo.forge("fix", "drop", NAME, "--undo")
        assert restored.returncode == 0, restored.stdout + restored.stderr
    if lifecycle == "dirty":
        (upgrade.folder / "README.md").write_bytes(b"Keep my unfinished work\n")
    if lifecycle == "remote work":
        peer = upgrade.tmp / "teammate"
        repo.git("clone", "-q", repo.git("remote", "get-url", "origin"), str(peer))
        teammate = Repo(peer, repo.bin)
        restored = teammate.forge("fix", "drop", NAME, "--undo")
        assert restored.returncode == 0, restored.stdout + restored.stderr
        folder = peer.with_name(f"{peer.name}-fix-{NAME}")
        upgrade.env.commit(folder, "README.md", "Keep the teammate work\n")
        dropped = teammate.forge("fix", "drop", NAME, "--because", "Keep this work for later")
        assert dropped.returncode == 0, dropped.stdout + dropped.stderr
    before = repo.git("rev-parse", f"origin/fix/{NAME}")
    if lifecycle == "unfetched":
        repo.git("update-ref", "-d", f"refs/remotes/origin/fix/{NAME}")
    original = repo.git("show", f"origin/fix/{NAME}:.factory/fixes/{NAME}.json") if lifecycle == "active" else None

    done = upgrade.run(RELEASE)

    if lifecycle in ("work", "remote work"):
        assert done.returncode == 1
        assert done.stderr.endswith(f"Next: forge fix drop {NAME} --undo\n")
        if lifecycle == "work":
            assert repo.git("rev-parse", f"origin/fix/{NAME}") == before
        else:
            assert repo.git("show", f"origin/fix/{NAME}:README.md") == "Keep the teammate work"
        assert not upgrade.folder.exists()
        assert upgrade.uv() == []
    elif lifecycle == "active":
        assert done.returncode == 1
        assert done.stderr.endswith(f"Next: forge work {NAME}\n")
        assert repo.git("show", f"fix/{NAME}:.factory/fixes/{NAME}.json") == original
        assert upgrade.uv() == []
    elif lifecycle == "dirty":
        assert done.returncode == 1
        assert "stash push --include-untracked" in done.stderr
        assert str(upgrade.folder) in done.stderr
        assert (upgrade.folder / "README.md").read_bytes() == b"Keep my unfinished work\n"
        assert upgrade.uv() == []
        # The named command preserves the edit and actually clears the upgrade stop.
        repo.git("stash", "push", "--include-untracked", cwd=upgrade.folder)
        assert "Keep my unfinished work" in repo.git("stash", "show", "-p")
        assert_ready(upgrade, upgrade.run(RELEASE), ours(upgrade, started=False))
    else:
        assert_ready(upgrade, done, ours(upgrade, started=False))
        assert f'version = "{RELEASE}"' in upgrade.show("forge.toml")
        assert repo.git("merge-base", "--is-ancestor", before, f"fix/{NAME}") == ""
