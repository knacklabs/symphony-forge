"""Upgrade to the installed release while a real read holds a machine lane.

Test-audit: protects upgrade completion without reinstalling a live release.
The regression is the unconditional run refusal; existing tests cover only installs
with live runs or no-run install skips. Use the real command, with no production seam.
"""
import os
import re
import shutil
from pathlib import Path

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _other_repo, _until
from test_lanes_agents import finish, hold_agents, start
from test_story import worktree
from test_upgrade_command import assert_ready, ours, unsynced_up, up  # noqa: F401

STORY = "upgrade-no-install-no-refusal"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adoption"])
def test_1_upgrade_to_installed_release_continues_during_runs(unsynced_up, tmp_path, adopted, request):
    upgrade = unsynced_up if adopted else request.getfixturevalue("up")
    if adopted:
        upgrade.repo.git("switch", "-q", "-c", "adoption")
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", upgrade.repo.path,
                        dirs_exist_ok=True)
        upgrade.repo.git("add", "-A")
        upgrade.repo.git("commit", "-qm", "Use the earlier adoption")
        upgrade.repo.git("switch", "-q", "main")
        upgrade.repo.git("merge", "-q", "--ff-only", "adoption")
    release = upgrade.repo.forge("--version").stdout.split()[-1]
    # Both a new repo and an earlier-adopted repo can pin an older release.
    upgrade.on_main("forge.toml", re.sub(r'^version = ".*"', 'version = "v1.0.0"',
                                         upgrade.toml(), count=1, flags=re.M))
    other = _other_repo(tmp_path, upgrade.repo.bin)
    hold_agents(upgrade.env)
    # Hold only the other repo's reader, not this upgrade's review service.
    review = Path(os.environ["AUTOREVIEW"])
    shutil.copyfile(review.with_name("autoreview-real"), review)
    processes = []
    try:
        reader, output = start(other.path, tmp_path / "read", other, "read", "SHOP")
        processes.append(reader)
        marker = upgrade.repo.bin / f"started-{worktree(other, 'story/SHOP').name}"
        _until(lambda: reader.poll() is not None or marker.exists(), "the reader")
        assert reader.poll() is None, output.read_text("utf-8")

        result = upgrade.run(release)

        name = "upgrade-forge-to-" + release.replace(".", "-")
        assert_ready(upgrade, result, ours(upgrade, installed=False, release=release, name=name),
                     release=release, name=name)
        assert not [call for call in upgrade.uv() if call["args"][:2] == ["tool", "install"]]
        assert reader.poll() is None, "Upgrade must leave the other repo's run alone"
    finally:
        finish(upgrade.repo, processes)
    assert all(process.returncode == 0 for process in processes)
