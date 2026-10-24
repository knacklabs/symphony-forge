"""An upgrade must leave the installed release alone until both machine lanes are empty.

The real read and test commands hold the lanes; only the model provider waits at its edge.
Existing upgrade tests have no live runs, so they cannot catch an install during another run.
No production test seam is needed.
"""
import json
import shutil
import sys

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _other_repo, _until
from test_lanes_agents import finish, hold_agents, start
from test_story import worktree
from test_upgrade_command import RELEASE, unsynced_up, up  # noqa: F401

STORY = "upgrade-waits-for-running-work"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adoption"])
def test_upgrade_names_runs_in_both_machine_lanes_before_install(unsynced_up, tmp_path, adopted, request):
    up = unsynced_up if adopted else request.getfixturevalue("up")
    if adopted:
        up.repo.git("switch", "-q", "-c", "adoption")
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", up.repo.path,
                        dirs_exist_ok=True)
        up.repo.git("add", "-A")
        up.repo.git("commit", "-qm", "Use the earlier adoption")
        up.repo.git("switch", "-q", "main")
        up.repo.git("merge", "-q", "--ff-only", "adoption")
        up.repo.git("push", "-q", "origin", "main")

    other = _other_repo(tmp_path, up.repo.bin)
    command = json.dumps(f'"{sys.executable}" held-test.py')
    config = (other.path / "forge.toml").read_text("utf-8")
    other.write("forge.toml", config + f"test = {command}\n")
    other.write("held-test.py", "import pathlib, time\n"
                "pathlib.Path('test-started').touch()\n"
                "while not pathlib.Path('test-go').exists(): time.sleep(0.05)\n")
    other.git("add", "-A")
    other.git("commit", "-qm", "Set the client test command")
    other.git("push", "-q", "origin", "main")
    hold_agents(up.env)
    processes = []
    try:
        reader, output = start(other.path, tmp_path / "read", other, "read", "SHOP")
        processes.append(reader)
        marker = up.repo.bin / f"started-{worktree(other, 'story/SHOP').name}"
        _until(lambda: reader.poll() is not None or marker.exists(), "the reader")
        assert reader.poll() is None, output.read_text("utf-8")
        test, output = start(other.path, tmp_path / "test", other, "test")
        processes.append(test)
        _until(lambda: test.poll() is not None or (other.path / "test-started").exists(), "the test")
        assert test.poll() is None, output.read_text("utf-8")
        # If upgrade reaches uv, stop at that external edge instead of starting its own close.
        (up.repo.bin / "uv-install-fails").touch()
        before = up.snapshot()

        result = up.run(RELEASE)

        assert result.returncode == 1, result.stdout + result.stderr
        assert "Wait until no Forge runs are in progress" in result.stderr
        assert "other: SHOP (read)" in result.stderr
        assert "other: main (test)" in result.stderr
        assert "two releases" in result.stderr
        assert f"then forge upgrade {RELEASE}" in result.stderr
        assert up.snapshot() == before
    finally:
        (other.path / "test-go").touch()
        finish(up.repo, processes)
    assert all(process.returncode == 0 for process in processes)
