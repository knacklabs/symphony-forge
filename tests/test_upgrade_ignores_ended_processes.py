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
from test_tools_session_hold import Session
from test_upgrade_command import RELEASE, install, unsynced_up, up  # noqa: F401

STORY = "upgrade-dead-runs"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("kind", ["read", "intake", "review"])
def test_1_upgrade_blocks_only_while_the_recorded_process_is_alive(up, tmp_path, monkeypatch, kind):
    hold_agents(up.env)
    owner = None
    reader = None
    try:
        if kind == "intake":
            monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
            monkeypatch.setenv("CLAUDECODE", "1")
            monkeypatch.setenv("CLAUDE_SESSION_ID", "unfinished-intake")
            owner = Session(up.repo, tmp_path / "intake-host", "claude-intake-session")
            offered = owner.forge("start", "Save a basket")
            assert offered.returncode == 0, offered.stdout + offered.stderr
            assert json.loads(offered.stdout)["role"] == "explorer"
            events_path = up.repo.path / ".git/forge/events.jsonl"
        else:
            if kind == "review":
                item, checkout = up.env.start_fix()
                args = ("close", item)
                marker = up.repo.bin / "started-review"
            else:
                other = _other_repo(tmp_path, up.repo.bin)
                checkout = other.path
                args = ("read", "SHOP")
                marker = up.repo.bin / f"started-{worktree(other, 'story/SHOP').name}"
            reader, output = start(checkout, tmp_path / kind, up.repo, *args)
            _until(lambda: reader.poll() is not None or marker.exists(), "the held model")
            assert reader.poll() is None, output.read_text("utf-8")
            events_path = (up.repo.path if kind == "review" else other.path) / ".git/forge/events.jsonl"

        events = [json.loads(line) for line in events_path.read_text("utf-8").splitlines()]
        assert any(row["event"] == "lane joined" for row in events)
        assert any(row["event"] == "lane admitted" for row in events)
        assert not any(row["event"] == "run end" for row in events)
        if kind == "review":
            assert any(row["event"] == "run start" for row in events)
        (up.repo.bin / "uv-install-fails").touch()

        live = up.run(RELEASE)
        assert live.returncode == 1, live.stdout + live.stderr
        assert "Forge runs are still in progress" in live.stderr
        assert up.uv() == []

        queue = next((tmp_path / "config").rglob("agent-runs.json"))
        processes = [row["process"]["pid"] for row in json.loads(queue.read_text("utf-8"))]
        if owner:
            owner.close()
        else:
            reader.kill()
            reader.wait(timeout=30)
        (up.repo.bin / "go-all").touch()
        _until(lambda: all(not alive(pid) for pid in processes), "the reader's model process to end")

        lanes = up.repo.forge("lanes", "--json")
        assert lanes.returncode == 0, lanes.stdout + lanes.stderr
        view = json.loads(lanes.stdout)
        assert not view["agents"]["entries"] and not view["tests"]["entries"]
        events = [json.loads(line) for line in events_path.read_text("utf-8").splitlines()]
        assert any(row["event"] == "lane left" and row.get("end_known") is False for row in events)
        assert not any(row["event"] == "run end" for row in events)
        ended = up.run(RELEASE)
        assert ended.returncode == 1, ended.stdout + ended.stderr
        assert "Installing Forge" in ended.stderr, ended.stdout + ended.stderr
        assert "Forge runs are still in progress" not in ended.stderr
        assert [call["args"] for call in up.uv()] == [install()]
    finally:
        if owner:
            owner.close()
        if reader:
            finish(up.repo, [reader])
