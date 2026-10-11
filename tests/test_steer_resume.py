"""Active-writer recovery through forge work and the Codex app-server boundary."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from contextlib import contextmanager

from conftest import _install
from test_codex_resume import RESUMING, _resuming
from test_codex_worker import _lines, _sent, _stub, sdk_data

STORY = "FORGE-STEER-1"

ACTIVE_WRITER = RESUMING.replace(
    "        log(method=method, params=params)\n",
    "        log(method=method, params=params, at=time.monotonic())\n", 1
).replace(
    "        result = {}\n",
    '''        if method == "thread/resume" and os.environ.get("STUB_RESUME_ERROR"):
            mode = os.environ["STUB_RESUME_ERROR"]
            if mode == "other" or (HERE / ("writer-" + id)).exists():
                reason = ("thread " + id + " already has an active writer"
                          if mode != "other" else "stub: store is busy")
                send(id=message["id"], error={"code": -32603, "message": reason})
                if mode == "release":
                    (HERE / ("release-" + id)).touch()
                continue
        result = {}
''', 1
).replace(
    '        elif method == "turn/start":\n',
    '''        elif method == "turn/start":
            if os.environ.get("STUB_HOLD_TURN"):
                (HERE / "turn-held").touch()
                while not (HERE / "release-turn").exists():
                    time.sleep(0.02)
''', 1
).replace(
    "\nmain()\n",
    '''
if sys.argv[1:2] == ["--hold-writer"]:
    conversation, mode = sys.argv[2:]
    held = HERE / ("writer-" + conversation)
    held.touch()
    if mode == "release":
        while not (HERE / ("release-" + conversation)).exists():
            time.sleep(0.02)
        held.unlink()
    while True:
        time.sleep(1)
else:
    main()
''', 1
)


def _ready(repo, monkeypatch, sdk_data):
    folder, calls, turns = _resuming(repo, monkeypatch, sdk_data)
    _install(repo.bin, "codex-app-server", f"#!{sys.executable}\n{ACTIVE_WRITER}")
    first = repo.forge("work", "BOARD/PAGE")
    assert first.returncode == 0, first.stdout + first.stderr
    return folder, calls, turns


@contextmanager
def _writer(repo, mode, conversation="thr-stub-1"):
    held = repo.bin / f"writer-{conversation}"
    release = repo.bin / f"release-{conversation}"
    release.unlink(missing_ok=True)
    holder = subprocess.Popen([sys.executable, str(repo.bin / "codex-app-server"), "--hold-writer",
                               conversation, mode], stdout=subprocess.DEVNULL)
    try:
        for _ in range(100):
            if held.exists():
                break
            time.sleep(0.02)
        assert held.exists()
        yield holder
    finally:
        holder.terminate()
        holder.wait(timeout=5)
        held.unlink(missing_ok=True)
        release.unlink(missing_ok=True)


def test_3_active_writer_retries_and_continues_the_conversation(repo, monkeypatch, sdk_data, claude_session):
    _, calls, turns = _ready(repo, monkeypatch, sdk_data)
    monkeypatch.setenv("STUB_RESUME_ERROR", "release")
    with _writer(repo, "release") as holder:
        resumed = repo.forge("work", "BOARD/PAGE")
        assert resumed.returncode == 0, resumed.stdout + resumed.stderr
        assert holder.poll() is None
    assert [call["threadId"] for call in _sent(calls, "thread/resume")] == ["thr-stub-1"] * 2
    attempts = [call["at"] for call in _stub(calls) if call.get("method") == "thread/resume"]
    assert attempts[1] - attempts[0] >= 1.8
    assert len(_sent(calls, "thread/start")) == 1
    assert "Starting a new Codex conversation" not in resumed.stdout
    assert "stub codex: turn-stub-2 on thr-stub-1" in resumed.stdout
    assert _lines(turns)[-1]["continued"] is True

    monkeypatch.setenv("STUB_RESUME_ERROR", "hold")
    with _writer(repo, "hold") as holder:
        refused = repo.forge("work", "BOARD/PAGE")
        assert refused.returncode != 0, refused.stdout + refused.stderr
        assert holder.poll() is None
    assert len(_sent(calls, "thread/resume")) == 4
    # A busy writer stops this round and preserves the original chat, rather than forking it.
    assert len(_sent(calls, "thread/start")) == 1
    assert "already has an active writer" in refused.stdout + refused.stderr
    assert "Starting a new Codex conversation" not in refused.stdout
    assert len(_sent(calls, "turn/start")) == 2

    monkeypatch.setenv("STUB_RESUME_ERROR", "other")
    refused = repo.forge("work", "BOARD/PAGE")
    assert refused.returncode != 0, refused.stdout + refused.stderr
    assert len(_sent(calls, "thread/resume")) == 5
    assert len(_sent(calls, "thread/start")) == 1
    assert "stub: store is busy" in refused.stdout + refused.stderr
    assert "Starting a new Codex conversation" not in refused.stdout
    assert len(_sent(calls, "turn/start")) == 2

    monkeypatch.setenv("STUB_RESUME_ERROR", "release")
    with _writer(repo, "release", "thr-stub-1") as holder:
        work = subprocess.Popen([sys.executable, str(repo.bin / "forge"), "work", "BOARD/PAGE"],
                                cwd=repo.path, env={**os.environ, "STUB_HOLD_TURN": "1"},
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        held = repo.bin / "turn-held"
        release = repo.bin / "release-turn"
        try:
            for _ in range(1000):
                if held.exists():
                    break
                time.sleep(0.02)
            assert held.exists()
            assert turns.with_suffix(".lock").exists()
            busy = repo.forge("work", "BOARD/PAGE")
            assert busy.returncode != 0
            assert "already running" in busy.stderr
            release.touch()
            output, errors = work.communicate(timeout=30)
            assert work.returncode == 0, output + errors
            assert holder.poll() is None
            assert not turns.with_suffix(".lock").exists()
            assert len(_sent(calls, "thread/start")) == 1
            assert _sent(calls, "thread/resume")[-1]["threadId"] == "thr-stub-1"
        finally:
            release.touch()
            if work.poll() is None:
                work.communicate(timeout=30)
            held.unlink(missing_ok=True)
            release.unlink(missing_ok=True)
