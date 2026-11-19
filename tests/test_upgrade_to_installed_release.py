"""Upgrade to the installed release while a real read holds a machine lane.

Test-audit: protects upgrade completion without reinstalling a live release and
repairs an earlier-adopted task's published start in the same upgrade. Existing
coverage rebuilds old records separately; it does not cover this upgrade path.
Use the real command and a GitHub edge fake, with no production seam.
"""
import os
import re
import shutil
from pathlib import Path

import pytest

from test_close import env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _other_repo, _until
from test_board_after_upgrade import History
from test_first_start_survives_history_changes import (
    assert_rewritten_published_task_start, prepare_rewritten_published_task,
)
from test_lanes_agents import finish, hold_agents, start
from test_story import worktree
from test_upgrade_command import MARK, assert_ready, ours, unsynced_up, up  # noqa: F401

STORY = "upgrade-no-install-no-refusal"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adoption"])
def test_1_upgrade_to_installed_release_continues_during_runs(
        unsynced_up, tmp_path, adopted, request, monkeypatch):
    upgrade = unsynced_up if adopted else request.getfixturevalue("up")
    history = None
    published_item = None
    started_at = None
    if adopted:
        # History prepares the earlier-adopted repo and publishes a task whose
        # old time record contains the rewritten start. Do this before pinning
        # its version so this stays the installed-release upgrade under test.
        history = History(upgrade, monkeypatch)
        published_item, started_at = prepare_rewritten_published_task(history)
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
        # The release fixture appends its marker to the source template. Both hosts
        # must receive that whole release template, including the marker.
        template = (ROOT / "src/forge/templates/skill.md").read_text(encoding="utf-8")
        expected = (template + f"\n<!-- {MARK} {release} -->\n").strip()
        for host in (".claude", ".codex"):
            assert upgrade.repo.git("show", f"fix/{name}:{host}/skills/forge/SKILL.md") == expected
        assert not [call for call in upgrade.uv() if call["args"][:2] == ["tool", "install"]]
        assert reader.poll() is None, "Upgrade must leave the other repo's run alone"
    finally:
        finish(upgrade.repo, processes)
    assert all(process.returncode == 0 for process in processes)
    if history is not None:
        assert published_item is not None and started_at is not None
        assert_rewritten_published_task_start(history, published_item, started_at)
