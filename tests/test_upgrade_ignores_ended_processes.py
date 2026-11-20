"""Upgrade must distinguish live work from an interrupted read's unfinished records.

The existing upgrade test covers live lanes only. Killing the real reader leaves
its admission and activity unfinished; no production seam decides the result.
"""
import json

import pytest

from test_close import env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _other_repo, _until
from test_lanes_agents import alive, finish, hold_agents, start
from test_story import worktree
from test_upgrade_command import RELEASE, install, unsynced_up, up  # noqa: F401

STORY = "upgrade-dead-runs"
pytestmark = pytest.mark.platform


def test_1_upgrade_blocks_only_while_the_recorded_process_is_alive(up, tmp_path):
    other = _other_repo(tmp_path, up.repo.bin)
    hold_agents(up.env)
    reader, output = start(other.path, tmp_path / "read", other, "read", "SHOP")
    try:
        marker = up.repo.bin / f"started-{worktree(other, 'story/SHOP').name}"
        _until(lambda: reader.poll() is not None or marker.exists(), "the reader")
        assert reader.poll() is None, output.read_text("utf-8")
        (up.repo.bin / "uv-install-fails").touch()

        live = up.run(RELEASE)
        assert live.returncode == 1, live.stdout + live.stderr
        assert "Forge runs are still in progress" in live.stderr
        assert up.uv() == []

        queue = next((tmp_path / "config").rglob("agent-runs.json"))
        processes = [row["process"]["pid"] for row in json.loads(queue.read_text("utf-8"))]
        reader.kill()
        reader.wait(timeout=30)
        (up.repo.bin / "go-all").touch()
        _until(lambda: all(not alive(pid) for pid in processes), "the reader's model process to end")
        ended = up.run(RELEASE)
        assert ended.returncode == 1, ended.stdout + ended.stderr
        assert "Installing Forge" in ended.stderr, ended.stdout + ended.stderr
        assert "Forge runs are still in progress" not in ended.stderr
        assert [call["args"] for call in up.uv()] == [install()]
    finally:
        finish(up.repo, [reader])
