"""Queue waits and process checks share one cheap pass through Forge commands."""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone

import pytest

from test_close import env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _until

STORY = "FORGE-BUDGET-1-SHARE"


def _run(repo, version: str, item: str, pid: int, *, kind: str = "work", reused: bool = False) -> dict:
    joined = datetime.now(timezone.utc).isoformat(timespec="seconds")
    process = {"pid": pid}
    if reused:
        process.update(started="UTC Mon Jan 1 00:00:00 2001", command="old process")
    return {"id": item, "version": version, "kind": kind, "repo_root": repo.path.as_posix(),
            "checkout_root": repo.path.as_posix(), "repo_name": repo.path.name, "item": item,
            "title": item, "model": None, "effort": None, "joined_at": joined,
            "started_at": joined, "process": process, "forge": {"pid": os.getpid()},
            "agent": None, "round": 1, "unblocks": False, "output_path": None,
            "progress": None, "free": False, "admitted": True}


def _queue_checks_many_processes_in_one_pass_and_leaves_unchanged_queue_alone(
        env, tmp_path, monkeypatch):
    processes = []
    try:
        for _ in range(6):
            processes.append(subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.buffer.read()"],
                                              stdin=subprocess.PIPE))
        assert all(process.poll() is None for process in processes)

        registry = tmp_path / "config" / "forge" / "agent-runs.json"
        registry.parent.mkdir(parents=True, exist_ok=True)
        version = env.repo.forge("--version").stdout.split()[-1].removeprefix("v")
        entries = [_run(env.repo, version, f"fix-shared-{index}", process.pid,
                        reused=index == 0) for index, process in enumerate(processes)]
        registry.write_text(json.dumps(entries), "utf-8")

        expected = {process.pid for process in processes} | {os.getpid()}
        identity_log = tmp_path / "identity-calls.log"
        if os.name == "nt":
            # Count the existing native handle lookup at the real command boundary.
            shim = tmp_path / "sitecustomize.py"
            shim.write_text(
                "import ctypes, os\n"
                "_tracked = {int(value) for value in os.environ['FORGE_IDENTITY_PIDS'].split(',')}\n"
                "_log = os.environ['FORGE_IDENTITY_LOG']\n"
                "_windll = ctypes.WinDLL\n"
                "class _Call:\n"
                "    def __init__(self, call): object.__setattr__(self, '_call', call)\n"
                "    def __call__(self, *args):\n"
                "        if len(args) > 2 and args[2] in _tracked:\n"
                "            with open(_log, 'a', encoding='utf-8') as out: out.write(str(args[2]) + '\\n')\n"
                "        return self._call(*args)\n"
                "    def __getattr__(self, name): return getattr(self._call, name)\n"
                "    def __setattr__(self, name, value): setattr(self._call, name, value)\n"
                "def _load(name, *args, **kwargs):\n"
                "    library = _windll(name, *args, **kwargs)\n"
                "    if name.casefold() == 'kernel32': library.OpenProcess = _Call(library.OpenProcess)\n"
                "    return library\n"
                "ctypes.WinDLL = _load\n", "utf-8")
            monkeypatch.setenv("PYTHONPATH", os.pathsep.join(
                value for value in (shim.parent.as_posix(), os.environ.get("PYTHONPATH", "")) if value))
            monkeypatch.setenv("FORGE_IDENTITY_PIDS", ",".join(map(str, sorted(expected))))
            monkeypatch.setenv("FORGE_IDENTITY_LOG", identity_log.as_posix())
        else:
            ps = shutil.which("ps")
            assert ps
            wrapper_dir = tmp_path / "ps-wrapper"
            wrapper_dir.mkdir()
            wrapper = wrapper_dir / "ps"
            wrapper.write_text(
                "#!/bin/sh\n"
                f"if [ \"$1\" = \"-ww\" ]; then printf '%s\\n' \"$*\" >> {shlex.quote(identity_log.as_posix())}; fi\n"
                f"exec {shlex.quote(ps)} \"$@\"\n", "utf-8")
            wrapper.chmod(0o755)
            monkeypatch.setenv("PATH", os.pathsep.join((wrapper_dir.as_posix(), os.environ["PATH"])))

        first = env.repo.forge("lanes", "--json")
        assert first.returncode == 0, first.stdout + first.stderr
        rows = json.loads(first.stdout)["agents"]["entries"]
        assert len(rows) == len(processes), rows
        assert next(row for row in rows if row["item"] == "fix-shared-0")["process"]["pid"] == os.getpid()

        if os.name == "nt":
            calls = Counter(map(int, identity_log.read_text("utf-8").splitlines()))
            assert calls == Counter(expected)
        else:
            calls = identity_log.read_text("utf-8").splitlines()
            assert len(calls) == 1, calls
            command = shlex.split(calls[0])
            seen = set(map(int, command[command.index("-p") + 1].split(",")))
            assert seen == expected

        written = registry.read_bytes()
        old = 1_234_567_890_000_000_000
        os.utime(registry, ns=(old, old))
        if identity_log.exists():
            identity_log.unlink()
        second = env.repo.forge("lanes", "--json")
        assert second.returncode == 0, second.stdout + second.stderr
        assert registry.read_bytes() == written
        assert registry.stat().st_mtime_ns == old
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
        for process in processes:
            process.communicate(timeout=10)


@pytest.mark.platform
def test_4_waiting_test_polls_once_a_second_then_backs_off_after_a_minute(env, tmp_path, monkeypatch):
    _queue_checks_many_processes_in_one_pass_and_leaves_unchanged_queue_alone(
        env, tmp_path, monkeypatch)
    settings = (env.repo.path / "forge.toml").read_text("utf-8")
    env.commit(env.repo.path, "forge.toml", settings + '\nfast_test = "echo test"\n')
    registry = tmp_path / "config" / "forge" / "agent-runs.json"
    registry.parent.mkdir(parents=True, exist_ok=True)
    version = env.repo.forge("--version").stdout.split()[-1].removeprefix("v")
    registry.write_text(json.dumps([
        _run(env.repo, version, f"fix-holder-{index}", os.getpid(), kind="test")
        for index in range(64)
    ]), "utf-8")

    waits = tmp_path / "waits.log"
    shim = tmp_path / "sitecustomize.py"
    shim.write_text(
        "import os, time\n"
        "_sleep = time.sleep\n"
        "_elapsed = 0\n"
        "_log = os.environ['FORGE_WAIT_LOG']\n"
        "def _monotonic(): return _elapsed\n"
        "def _sleep_for(seconds):\n"
        "    global _elapsed\n"
        "    with open(_log, 'a', encoding='utf-8') as out: out.write(str(seconds) + '\\n')\n"
        "    _sleep(0.005)\n"
        "    _elapsed += seconds\n"
        "time.monotonic = _monotonic\n"
        "time.sleep = _sleep_for\n", "utf-8")
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(
        value for value in (shim.parent.as_posix(), os.environ.get("PYTHONPATH", "")) if value))
    monkeypatch.setenv("FORGE_WAIT_LOG", waits.as_posix())

    output = tmp_path / "waiting-test.out"
    with output.open("w", encoding="utf-8") as sink:
        process = subprocess.Popen([sys.executable, str(env.repo.bin / "forge"), "test"],
            cwd=env.repo.path, stdin=subprocess.DEVNULL, stdout=sink, stderr=subprocess.STDOUT)
    try:
        _until(lambda: waits.is_file() and bool(waits.read_text("utf-8").splitlines()),
               "forge test did not enter its wait")
        first = waits.read_text("utf-8").splitlines()
        assert float(first[0]) == 1, first[:3]
        _until(lambda: any(float(value) == 2 for value in waits.read_text("utf-8").splitlines()),
               "forge test did not back off after a minute")
        intervals = list(map(float, waits.read_text("utf-8").splitlines()))
        assert intervals[:60] == [1] * 60, intervals
        assert intervals[60] == 2, intervals
        assert process.poll() is None
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
