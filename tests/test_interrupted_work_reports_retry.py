"""An interrupted work command reports the unfinished round and its retry.

Test-audit: a real signal to the command must produce the retry line and release
the lock. Existing worker tests cover normal returns and explicit human stops,
not shell signals. Holding real Git before a turn catches late handler setup;
answering a real worker question catches retry commands that lose the note.
Only external Git and model calls are held; neither supplies the retry message,
and no production seam is added.
"""
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tomllib

import pytest

from conftest import _install
from test_board_dependency_timelines import _client, _land_fixture
from test_fix_agent_runs_wait_in_line import _until
from test_tools_session_hold import Session
from test_worker import install_claude

STORY = "FIX-INTERRUPTED-WORK"


@pytest.mark.skipif(os.name == "nt", reason="POSIX shell signals; Windows terminate is uncatchable")
@pytest.mark.parametrize("sig,history,stage", [
    (signal.SIGTERM, "new", "turn"), (signal.SIGINT, "new", "turn"),
    (signal.SIGTERM, "adopted-v1.2.2", "turn"),
    (signal.SIGTERM, "new", "fetch"), (signal.SIGINT, "new", "merge"),
    (signal.SIGTERM, "new", "answer"),
], ids=["term-new", "int-new", "term-earlier-adopted", "term-fetch", "int-merge", "term-answer"])
def test_1_interrupted_round_prints_retry_and_releases_lock(
        repo, gh, tmp_path, monkeypatch, history, sig, stage):
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
    host = Session(repo, tmp_path / "host", "codex-session")
    held = None
    try:
        note = []
        if stage == "answer":
            monkeypatch.setenv("STUB_CLAUDE_RESULT", "Question: Use the shared parser?")
            asked = host.forge("work", item)
            assert asked.returncode == 0, asked.stdout + asked.stderr
            assert "Question: Use the shared parser?" in asked.stdout
            monkeypatch.delenv("STUB_CLAUDE_RESULT")
            note = ["--note", "Yes, use Ravi's \"shared parser\"; keep $HOME literal."]
        if stage in ("fetch", "merge"):
            executable = shutil.which("git")
            _install(repo.bin, "git", f'''#!{sys.executable}
import json, os, sys, time
from pathlib import Path
if sys.argv[1] == {stage!r}:
    Path({marker.as_posix()!r}).write_text(json.dumps({{"parent": os.getppid()}}), encoding="utf-8")
    while not Path({release.as_posix()!r}).exists():
        time.sleep(0.01)
os.execv({json.dumps(executable)}, [{json.dumps(executable)}, *sys.argv[1:]])
''')
        else:
            monkeypatch.setenv("STUB_CLAUDE_SDK_STARTED", str(marker))
            monkeypatch.setenv("STUB_CLAUDE_SDK_HOLD", str(release))
        held = host.start("work", item, *note)
        _until(lambda: marker.exists() or held.done(), "work to reach the interruption point")
        assert not held.done(), held.result().stdout
        process = json.loads(marker.read_text("utf-8"))
        if "parent" in process:
            parent = process["parent"]
        else:
            # Session's command process owns the lock; the SDK runs as its child.
            parent = int(subprocess.check_output(
                ["ps", "-o", "ppid=", "-p", str(process["driver"])], text=True))
        os.kill(parent, sig)
        release.touch()
        ended = held.result(timeout=30)
        assert ended.returncode != 0
        retry = f"forge work {item}" + (" --note " + shlex.quote(note[1]) if note else "")
        message = f"The round did not finish. Run {retry} again."
        assert (ended.stdout + ended.stderr).splitlines().count(message) == 1, ended.stdout + ended.stderr
        resumed = host.forge(*shlex.split(retry)[1:])
        assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    finally:
        release.touch()
        try:
            if held is not None:
                held.result(timeout=30)
        finally:
            host.close()
