"""An interrupted work command reports the unfinished round and its retry.

Test-audit: a real signal to the command must produce the retry line and release
the lock. Existing worker tests cover normal returns and explicit human stops,
not shell signals. Only the external model SDK is held; no production seam is
added, and the SDK does not supply the expected message.
"""
import json
import os
import signal
import subprocess
import tomllib

import pytest

from test_board_dependency_timelines import _client, _land_fixture
from test_fix_agent_runs_wait_in_line import _until
from test_tools_session_hold import Session
from test_worker import install_claude

STORY = "FIX-INTERRUPTED-WORK"


@pytest.mark.skipif(os.name == "nt", reason="POSIX shell signals; Windows terminate is uncatchable")
@pytest.mark.parametrize("sig,history", [
    (signal.SIGTERM, "new"), (signal.SIGINT, "new"), (signal.SIGTERM, "adopted-v1.2.2"),
], ids=["term-new", "int-new", "term-earlier-adopted"])
def test_1_interrupted_round_prints_retry_and_releases_lock(repo, gh, tmp_path, monkeypatch, history, sig):
    _client(repo, gh, tmp_path, history)
    repo.git("switch", "-qc", "fix/configure-worker")
    repo.write(".factory/fixes/configure-worker.json", json.dumps({
        "kind": "fix", "branch": "fix/configure-worker", "why": "Choose external Claude worker",
        "done_when": "The client uses Claude", "status": "started"}))
    config = repo.path / "forge.toml"
    version = tomllib.loads(config.read_text("utf-8"))["version"]
    config.write_text(f'version = "{version}"\nrepo = "client"\ntools = "both"\n'
                      'workers = "claude"\ntest = "git status --porcelain"\n', encoding="utf-8")
    repo.git("add", "forge.toml", ".factory")
    repo.git("commit", "-qm", "Choose external Claude worker")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/configure-worker")
    _land_fixture(repo)
    install_claude(repo)
    item = "report-interrupted-work"
    started = repo.forge("fix", "start", "Report interrupted work", "--done",
                         "An interrupted round prints its retry command", "--slug", item)
    assert started.returncode == 0, started.stdout + started.stderr
    marker, release = tmp_path / "sdk-started.json", tmp_path / "sdk-release"
    monkeypatch.setenv("STUB_CLAUDE_SDK_STARTED", str(marker))
    monkeypatch.setenv("STUB_CLAUDE_SDK_HOLD", str(release))
    host = Session(repo, tmp_path / "host", "codex-session")
    held = None
    try:
        held = host.start("work", item)
        _until(lambda: marker.exists() or held.done(), "the builder turn to start")
        assert not held.done(), held.result().stdout
        # Session's command process owns the lock; the SDK runs as its child.
        driver = json.loads(marker.read_text("utf-8"))["driver"]
        parent = int(subprocess.check_output(["ps", "-o", "ppid=", "-p", str(driver)], text=True))
        os.kill(parent, sig)
        ended = held.result(timeout=30)
        assert ended.returncode != 0
        message = f"The round did not finish. Run forge work {item} again."
        assert (ended.stdout + ended.stderr).splitlines().count(message) == 1, ended.stdout + ended.stderr
        release.touch()
        resumed = host.forge("work", item)
        assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    finally:
        release.touch()
        try:
            if held is not None:
                held.result(timeout=30)
        finally:
            host.close()
