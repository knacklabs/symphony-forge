"""Command-boundary proof for src/forge/event_log.py: immutable history and bounded writes."""
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime

import pytest

from test_close import env  # noqa: F401
from test_live_status import row
from test_run_records import configure, records
from test_upgrade_command import (NAME, _repo_adopted_on_the_previous_release,
                                  unsynced_up)  # noqa: F401

STORY = "FIX-APPEND-ONLY-EVENTS"


# Trace the Python file-I/O boundary in the real command, rather than replacing
# Forge's recorder. The external worker remains the only stub in the flow.
TRACE = '''import builtins, io, json, os
from pathlib import Path
original_open = builtins.open
original_io_open = io.open
getenv = os.environ.get
if getenv("PROGRESS_CLOCK"):
    clock = Path(getenv("PROGRESS_CLOCK"))
    audit = Path(getenv("PROGRESS_WRITES"))
    crash = Path(getenv("PROGRESS_CRASH")) if getenv("PROGRESS_CRASH") else None
    directory = Path(getenv("PROGRESS_DIRECTORY")).resolve()
    def environment(key, default=None):
        if key == "FORGE_NOW":
            with original_open(clock, encoding="utf-8") as source:
                return source.read()
        return getenv(key, default)
    os.environ.get = environment
    class Traced:
        def __init__(self, stream):
            self.stream = stream
        def __getattr__(self, name):
            return getattr(self.stream, name)
        def __enter__(self):
            self.stream.__enter__()
            return self
        def __exit__(self, *args):
            return self.stream.__exit__(*args)
        def write(self, data):
            size = len(data.encode("utf-8") if isinstance(data, str) else data)
            with original_open(audit, "a", encoding="utf-8") as output:
                output.write(str(size) + "\\n")
            if (crash is not None and crash.exists() and Path(self.stream.name).name == "events.jsonl"
                    and json.loads(data).get("event") == "run start"):
                crash.unlink()
                self.stream.write(data[:len(data) // 2])
                self.stream.flush()
                os.fsync(self.stream.fileno())
                raise OSError("Interrupted event append")
            return self.stream.write(data)
    def traced(opener, file, mode="r", *args, **kwargs):
        stream = opener(file, mode, *args, **kwargs)
        if isinstance(file, (str, bytes, os.PathLike)) and any(c in mode for c in "wax+"):
            path = Path(file).resolve()
            if directory in path.parents and (path.name.startswith("events.") or "progress" in path.parts):
                return Traced(stream)
        return stream
    builtins.open = lambda *a, **kw: traced(original_open, *a, **kw)
    io.open = lambda *a, **kw: traced(original_io_open, *a, **kw)
'''


@pytest.mark.parametrize("history_size,adopted,interrupted", [
    (2, False, False), (45000, False, False), (45000, True, False), (2, False, True)])
@pytest.mark.timeout(600)
def test_1_progress_updates_preserve_history_with_bounded_writes(
        env, monkeypatch, request, tmp_path, history_size, adopted, interrupted):
    if adopted:
        # Keep the real earlier adoption and upgrade in git, then select this
        # checkout's installed release and the same Claude route as new clients.
        settings = (env.repo.path / "forge.toml").read_text("utf-8")
        upgrade = request.getfixturevalue("unsynced_up")
        _repo_adopted_on_the_previous_release(upgrade)
        upgrade.repo.git("-c", f"core.hooksPath={upgrade.tmp / 'no-hooks'}",
                         "merge", "-q", "--ff-only", f"fix/{NAME}")
        # The landed adoption installed commit hooks; this fixture's mainline
        # settings are setup, not a worker commit in the client flow under test.
        upgrade.repo.git("config", "core.hooksPath", str(upgrade.tmp / "no-hooks"))
        env.commit(env.repo.path, "forge.toml", settings)
    repo = configure(env)
    item, _ = env.start_fix()
    instant = "2026-10-06T12:00:00+00:00"
    monkeypatch.setenv("FORGE_NOW", instant)
    history = repo.path / ".git" / "forge" / "events.jsonl"
    history.parent.mkdir(exist_ok=True)
    # A plain-text pre-existing log exercises the same path as real old history.
    seed = {"id": "older-event", "item": "older-fix", "event": "run end",
            "at": "2026-10-05T12:00:00+00:00", "round": 1,
            "detail": "completed earlier work " * 10}
    prefix = "".join(json.dumps({**seed, "id": f"older-{number}"}) + "\n"
                     for number in range(history_size)).encode("utf-8")
    history.write_bytes(prefix)
    clock, writes = tmp_path / "clock", tmp_path / "writes"
    clock.write_text(instant, "utf-8")
    (repo.bin / "sitecustomize.py").write_text(TRACE, "utf-8")
    child_env = {**os.environ, "PROGRESS_CLOCK": str(clock),
                 "PROGRESS_WRITES": str(writes),
                 "PROGRESS_DIRECTORY": str(history.parent)}
    if interrupted:
        # A failed append leaves a partial final record. Already complete history
        # must survive, and the next real command must recover the trailing write.
        crash = tmp_path / "interrupt-next-append"
        crash.write_text("interrupt", "utf-8")
        failed = subprocess.run([sys.executable, str(repo.bin / "forge"), "work", item],
                                cwd=repo.path, env={**child_env, "PROGRESS_CRASH": str(crash)},
                                capture_output=True, text=True, encoding="utf-8", timeout=60)
        assert failed.returncode != 0, failed.stdout + failed.stderr
        assert not crash.exists(), "The command did not reach the interrupted append"
        assert history.read_bytes().startswith(prefix)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.settimeout(60)
        steps = ["first.py", "second.py", "third.py"]
        events = ""
        for path in steps:
            events += (f'yield AssistantMessage([ToolUseBlock("edit", "Edit", '
                       f'{{"file_path": {path!r}}})], options.model)\n'
                       f'with socket.create_connection({listener.getsockname()!r}, timeout=60) as gate:\n'
                       '    gate.settimeout(None)\n    gate.recv(1)\n')
        stub = repo.bin / "claude_agent_sdk" / "__init__.py"
        marker = '    yield AssistantMessage([TextBlock("SDK worker output")], options.model)'
        source = stub.read_text("utf-8")
        assert marker in source
        stub.write_text(source.replace(marker, "    import socket\n" +
                        "".join("    " + line + "\n" for line in events.splitlines()) + marker), "utf-8")
        process = subprocess.Popen([sys.executable, str(repo.bin / "forge"), "work", item],
                                   cwd=repo.path, env=child_env, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, encoding="utf-8")
        connections = []
        immutable = prefix
        try:
            for index, path in enumerate(steps):
                connection, _ = listener.accept()
                connections.append(connection)
                deadline = time.monotonic() + 60
                while True:
                    current, _ = row(repo, item)
                    if (current["worker"] or {}).get("step") == f"editing {path}":
                        break
                    assert time.monotonic() < deadline, f"Latest update missing: {path}"
                sizes = [int(size) for size in writes.read_text("utf-8").splitlines()]
                # Includes startup and all earlier updates: independent of history size.
                assert sum(sizes) < 16384, f"Progress wrote {sum(sizes)} bytes for {len(prefix)} history bytes"
                snapshot = history.read_bytes()
                assert snapshot.startswith(immutable), "Progress rewrote complete history records"
                immutable = snapshot
                if index == 1:
                    # Advance the real command clock, without a timer sleep, to retire
                    # the first coalescing window before the third tool event.
                    instant = "2026-10-06T12:00:11+00:00"
                    clock.write_text(instant, "utf-8")
                    monkeypatch.setenv("FORGE_NOW", instant)
                connection.sendall(b"1")
            output, error = process.communicate(timeout=60)
            assert process.returncode == 0, output + error
        finally:
            for connection in connections:
                connection.close()
            if process.poll() is None:
                process.kill()
                process.communicate()
    assert history.read_bytes().startswith(prefix)
    events = records(repo, "events.jsonl")
    start = next(event for event in events if event["item"] == item and event["event"] == "run start")
    progress = [event for event in events if event.get("run_id") == start["id"] and event["event"] == "progress"]
    assert [event["step"] for event in progress] == ["editing second.py", "editing third.py"]
    assert all(event["round"] == start["round"] for event in progress)
    assert (datetime.fromisoformat(progress[1]["at"]) -
            datetime.fromisoformat(progress[0]["at"])).total_seconds() == 11
    assert any(event["event"] == "run end" and event.get("run_id") == start["id"] for event in events)
    assert any(timing["item"] == item and timing["step"] == "worker round"
               for timing in records(repo, "timings.jsonl"))
    assert row(repo, item)[0]["activity"] == {"status": "idle"}
