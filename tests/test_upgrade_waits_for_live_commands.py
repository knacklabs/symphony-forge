"""Upgrade must wait for a live close even after its model and test lanes empty.

Audit: lane-only coverage misses a close waiting on GitHub checks. The real close
creates its process record; only GitHub and the model are third-party fixtures.
The regression is installation while that process can still resume. No new
production seam is needed.
"""
import json
import os

import pytest

from conftest import patient
from test_close import env, run  # noqa: F401
from test_fix_agent_runs_wait_in_line import _until
from test_lanes_agents import start
from test_upgrade_command import RELEASE, install, unsynced_up, up  # noqa: F401

STORY = "upgrade-dead-runs"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("identity", ["ended", "reused"])
def test_2_upgrade_waits_for_a_live_close_with_empty_lanes(up, tmp_path, monkeypatch, identity):
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "600")
    monkeypatch.setenv("FORGE_CHECKS_POLL", "0.1")
    up.env.checks([run("tests", None, "in_progress"), run("forge-pr-check")])
    item, checkout = up.env.start_fix()
    closing, output = start(checkout, tmp_path / "close", up.repo, "close", item)
    history = up.repo.path / ".git/forge/events.jsonl"

    def waiting():
        rows = [json.loads(line) for line in history.read_text("utf-8").splitlines()] if history.exists() else []
        return any(row.get("event") == "run start" and row.get("kind") == "ci" for row in rows)

    try:
        _until(lambda: closing.poll() is not None or waiting(), "the close check wait")
        assert closing.poll() is None, output.read_text("utf-8")
        lanes = up.repo.forge("lanes", "--json")
        assert lanes.returncode == 0, lanes.stderr
        shown = json.loads(lanes.stdout)
        assert shown["agents"]["entries"] == shown["tests"]["entries"] == []
        (up.repo.bin / "uv-install-fails").touch()

        live = up.run(RELEASE)
        assert live.returncode == 1, live.stdout + live.stderr
        assert "Forge runs are still in progress" in live.stderr, live.stdout + live.stderr
        assert f"{item} (ci)" in live.stderr
        assert up.uv() == []

        closing.kill()
        closing.wait(timeout=30)
        if identity == "reused":
            rows = [json.loads(line) for line in history.read_text("utf-8").splitlines()]
            ci = next(row for row in rows if row.get("event") == "run start"
                      and row.get("kind") == "ci")
            assert isinstance(ci["process"], dict)
            ci["process"] = {"pid": os.getpid(), "started": "not this process's start",
                             "command": "other"}
            patient(lambda: history.write_text(
                "".join(json.dumps(row) + "\n" for row in rows), "utf-8"))
        ended = up.run(RELEASE)
        assert ended.returncode == 1, ended.stdout + ended.stderr
        assert "Installing Forge" in ended.stderr, ended.stdout + ended.stderr
        assert "Forge runs are still in progress" not in ended.stderr
        assert [call["args"] for call in up.uv()] == [install()]
    finally:
        if closing.poll() is None:
            closing.kill()
        closing.wait(timeout=30)
