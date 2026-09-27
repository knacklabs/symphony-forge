"""Active-writer recovery through forge work and the Codex app-server boundary."""
from __future__ import annotations

import os
import subprocess
import sys
import time

from conftest import _install
from test_codex_resume import RESUMING, _resuming
from test_codex_worker import _lines, _sent, _stub, sdk_data

STORY = "FORGE-STEER-1"

ACTIVE_WRITER = RESUMING.replace(
    "    for line in sys.stdin:\n", "    resume_attempts = 0\n    for line in sys.stdin:\n", 1
).replace(
    "        log(method=method, params=params)\n",
    "        log(method=method, params=params, at=time.monotonic())\n", 1
).replace(
    "        result = {}\n",
    '''        if method == "thread/resume" and os.environ.get("STUB_RESUME_ERROR"):
            resume_attempts += 1
            mode = os.environ["STUB_RESUME_ERROR"]
            if mode == "other" or mode == "always" or resume_attempts == 1:
                reason = ("thread " + id + " already has an active writer"
                          if mode != "other" else "stub: store is busy")
                send(id=message["id"], error={"code": -32603, "message": reason})
                continue
        result = {}
''', 1
)


def _ready(repo, monkeypatch, sdk_data):
    folder, calls, turns = _resuming(repo, monkeypatch, sdk_data)
    _install(repo.bin, "codex-app-server", f"#!{sys.executable}\n{ACTIVE_WRITER}")
    first = repo.forge("work", "BOARD/PAGE")
    assert first.returncode == 0, first.stdout + first.stderr
    return folder, calls, turns


def test_3_active_writer_retries_and_continues_the_conversation(repo, monkeypatch, sdk_data):
    _, calls, turns = _ready(repo, monkeypatch, sdk_data)
    monkeypatch.setenv("STUB_RESUME_ERROR", "once")
    resumed = repo.forge("work", "BOARD/PAGE")
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert [call["threadId"] for call in _sent(calls, "thread/resume")] == ["thr-stub-1"] * 2
    attempts = [call["at"] for call in _stub(calls) if call.get("method") == "thread/resume"]
    assert attempts[1] - attempts[0] >= 1.8
    assert len(_sent(calls, "thread/start")) == 1
    assert "Starting a new Codex conversation" not in resumed.stdout
    assert "stub codex: turn-stub-2 on thr-stub-1" in resumed.stdout
    assert _lines(turns)[-1]["continued"] is True

    monkeypatch.setenv("STUB_RESUME_ERROR", "always")
    fresh = repo.forge("work", "BOARD/PAGE")
    assert fresh.returncode == 0, fresh.stdout + fresh.stderr
    assert len(_sent(calls, "thread/resume")) == 4
    assert len(_sent(calls, "thread/start")) == 2
    assert "already has an active writer" in fresh.stdout
    assert "Starting a new Codex conversation" in fresh.stdout
    assert _lines(turns)[-1]["continued"] is False

    monkeypatch.setenv("STUB_RESUME_ERROR", "other")
    fresh = repo.forge("work", "BOARD/PAGE")
    assert fresh.returncode == 0, fresh.stdout + fresh.stderr
    assert len(_sent(calls, "thread/resume")) == 5
    assert len(_sent(calls, "thread/start")) == 3
    assert "Codex couldn't resume its conversation: stub: store is busy" in fresh.stdout
    assert _lines(turns)[-1]["continued"] is False

    monkeypatch.setenv("STUB_RESUME_ERROR", "always")
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    work = subprocess.Popen([sys.executable, str(repo.bin / "forge"), "work", "BOARD/PAGE"],
                            cwd=repo.path, env=os.environ.copy(), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    try:
        for _ in range(100):
            if len(_sent(calls, "thread/resume")) >= 6:
                break
            time.sleep(0.02)
        assert turns.with_suffix(".lock").exists()
        busy = repo.forge("work", "BOARD/PAGE")
        assert busy.returncode != 0
        assert "already running" in busy.stderr
        output, errors = work.communicate(timeout=30)
        assert work.returncode == 0, output + errors
        assert other.poll() is None
        assert not turns.with_suffix(".lock").exists()
    finally:
        if work.poll() is None:
            work.kill()
            work.communicate()
        other.terminate()
        other.wait()
