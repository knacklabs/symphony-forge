"""Every Forge lane leaves memory and CPU room for local CI jobs."""
import json
import os
import shutil
import sys

import pytest

from conftest import IDLE_MACHINE, _install, machine_cores
from test_close import env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _other_repo, _until
from test_lanes_agents import finish, hold_agents, make_work, start
from test_lanes_tests import accepted, configure, reap, release_server, rows, shell  # noqa: F401
from test_runs_wait_for_machine_load import client
from test_story import worktree

STORY = "FORGE-BUDGET-1"


def publish(path, text):
    """Readers see either complete measurement, including during recovery and cleanup."""
    pending = path.with_suffix(".next")
    pending.write_text(text, "utf-8")
    pending.replace(path)


def measurements(repo, tmp_path, available=800_000_000, runners=0, total=16_000_000_000, native=False):
    """Supply OS measurements, leaving admission and command execution to Forge."""
    memory = tmp_path / "memory.json"
    busy = tmp_path / "busy-runners"
    publish(memory, json.dumps({"total_bytes": total, "available_bytes": available}))
    publish(busy, str(runners))
    shim = repo.bin / "forge"
    source = shim.read_text("utf-8")
    if native:
        source = source.replace(IDLE_MACHINE, "")
        if sys.platform == "linux":
            source = source.replace("from forge.cli import main",
                "import pathlib\n_real_read = pathlib.Path.read_text\n"
                f"_meminfo = 'MemTotal: {total // 1024} kB\\nMemAvailable: {available // 1024} kB\\n'\n"
                "pathlib.Path.read_text = lambda path, *a, **k: _meminfo if str(path) == '/proc/meminfo' else _real_read(path, *a, **k)\n"
                "from forge.cli import main")
        elif sys.platform == "darwin":
            _install(repo.bin, "sysctl", f"#!{sys.executable}\nprint({total!r})\n")
            stats = ("Mach Virtual Memory Statistics: (page size of 4096 bytes)\n"
                     f"Pages free: {available // 4096 // 2}.\n"
                     f"Pages inactive: {available // 4096 - available // 4096 // 2}.\n")
            _install(repo.bin, "vm_stat", f"#!{sys.executable}\nprint({stats!r})\n")
        else:
            source = source.replace("from forge.cli import main",
                "import ctypes\n"
                "def memory_status(pointer):\n"
                f"    pointer._obj.total, pointer._obj.available = {total}, {available}\n"
                "    return 1\n"
                "ctypes.windll.kernel32.GlobalMemoryStatusEx = memory_status\n"
                "from forge.cli import main")
        command = "tasklist" if os.name == "nt" else "ps"
        real = shutil.which(command)
        inventory = ('"Runner.Worker.exe","101","Console","1","100 K"\n'
                     '"runner.worker.exe","102","Console","1","100 K"\n'
                     '"Runner.Listener.exe","103","Console","1","100 K"\n'
                     '"python.exe","104","Console","1","100 K"\n') if os.name == "nt" else (
                         "/runner/bin/Runner.Worker\n/runner with spaces/bin/Runner.Worker\n"
                         "/runner/bin/Runner.Listener\npython inspect.py /runner/bin/Runner.Worker\n")
        args = ["/FO", "CSV", "/NH"] if os.name == "nt" else ["-axo", "comm="]
        _install(repo.bin, command, f"#!{sys.executable}\nimport subprocess, sys\n"
                 f"if sys.argv[1:] == {args!r}:\n    sys.stdout.write({inventory!r})\n"
                 f"else:\n    sys.exit(subprocess.call([{real!r}, *sys.argv[1:]]))\n")
        shim.write_text(source, "utf-8")
        return memory, busy
    shim.write_text(source.replace("from forge.cli import main",
        "import json, pathlib\nfrom forge import machine\n"
        f"machine.memory = lambda: json.loads(pathlib.Path({memory.as_posix()!r}).read_text('utf-8'))\n"
        f"machine.busy_runners = lambda: int(pathlib.Path({busy.as_posix()!r}).read_text('utf-8'))\n"
        "from forge.cli import main"), "utf-8")
    return memory, busy


def configure_marker(env, marker, picker=False):
    """A client's test records when Forge actually starts it."""
    command = shell([sys.executable, "-c",
                     f"from pathlib import Path; Path({marker.as_posix()!r}).touch()"])
    cfg = (env.repo.path / "forge.toml").read_text("utf-8")
    cfg = "\n".join(line for line in cfg.splitlines()
                    if line.partition("=")[0].strip() not in ("test", "fast_test", "workers"))
    cfg = 'workers = "claude"\n' + cfg
    if picker:
        command = shell([sys.executable, "-m", "pytest", "-q"])
        cfg = 'fast_test = "forge test --pytest {base}"\n' + cfg
    env.commit(env.repo.path, "forge.toml", "test = " + json.dumps(command) + "\n" + cfg)
    env.repo.git("push", "-q", "origin", "main")


@pytest.mark.parametrize("kind,adopted", [
    ("work", False), ("read", False), ("review", False), ("test", False), ("work", True),
], ids=["work", "read", "review", "small-test", "earlier-adoption"])
def test_1_every_lane_waits_for_memory_and_starts_when_it_recovers(env, tmp_path, kind, adopted):
    # Reads, reviews and small selections skip capacity places, but must obey the memory floor.
    repo = client(env, tmp_path, adopted)
    machine_cores(repo, 8)
    marker = repo.bin / "test-started"
    configure_marker(env, marker, picker=kind == "test")
    if kind == "work":
        item, folder = env.start_fix({"README.md": "Work after memory recovers\n"}, status="started")
        where, args, marker = repo.path, ("work", item), repo.bin / f"started-{folder.name}"
    elif kind == "read":
        other = _other_repo(tmp_path, repo.bin)
        where, args = other.path, ("read", "SHOP")
        marker = repo.bin / f"started-{worktree(other, 'story/SHOP').name}"
    elif kind == "review":
        item, _ = env.start_fix({"README.md": "Review after memory recovers\n"})
        where, args, marker = repo.path, ("close", item), repo.bin / "started-review"
    else:
        _, where = env.start_fix({"test_memory_start.py": "from pathlib import Path\n"
            f"def test_starts():\n    Path({marker.as_posix()!r}).touch()\n"})
        args = ("test",)
    hold_agents(env)
    # This read is above the fixed 1.5 GB minimum but below ten percent of RAM.
    available = 1_510_000_000 if kind == "read" else 800_000_000
    memory_wait = f"waiting for memory: {available / 1e9:.1f} GB free, starts above 1.6 GB"
    memory, _ = measurements(repo, tmp_path, available=available)
    processes = []
    try:
        process, output = start(where, tmp_path / "held", repo, *args)
        processes.append(process)
        _until(lambda: memory_wait in output.read_text("utf-8") or marker.exists() or process.poll() is not None,
               "the command to explain its memory wait")
        assert memory_wait in output.read_text("utf-8"), output.read_text("utf-8")
        assert process.poll() is None
        assert not marker.exists()
        publish(memory, json.dumps({"total_bytes": 16_000_000_000,
                                    "available_bytes": 2_000_000_000}))
        _until(lambda: marker.exists() or process.poll() is not None,
               "the command to start after memory recovers")
        assert marker.exists(), output.read_text("utf-8")
        assert output.read_text("utf-8").count(memory_wait) == 1
    finally:
        publish(memory, json.dumps({"total_bytes": None, "available_bytes": None}))
        finish(repo, processes)
    assert process.returncode == 0, output.read_text("utf-8")
    if kind == "test":
        # An unreadable source must fail open rather than hold otherwise runnable work.
        marker.unlink()
        result = repo.forge("test", cwd=where)
        assert result.returncode == 0, result.stdout + result.stderr
        assert marker.exists()
        assert "waiting for memory" not in result.stdout


@pytest.mark.parametrize("kind", ["work", "test"])
def test_3_busy_runners_reduce_budgets_and_idle_runners_release_waiters(
        env, tmp_path, release_server, kind):
    repo = env.repo
    machine_cores(repo, 8)
    _, busy = measurements(repo, tmp_path, available=8_000_000_000, runners=2)
    server, connections = release_server
    if kind == "test":
        configure(env, server)
        jobs = [env.start_fix()[1], env.start("second", "fix/second", ".factory/fixes/second.json",
                {"kind": "fix", "why": "Second test", "done_when": "The test passes"},
                {"app.py": 'print("second passed")\n'})[1]]
    else:
        jobs = [make_work(repo, f"Runner work {number}") for number in range(3)]
        hold_agents(env)
    processes, outputs = [], []
    running = 1 if kind == "test" else 2
    try:
        for index, job in enumerate(jobs):
            if kind == "work" and index == running:
                # Running rounds retain their places when another runner takes room;
                # the first waiter is still first, even when the new capacity is one.
                publish(busy, "3")
            where, args = (job, ("test",)) if kind == "test" else (repo.path, ("work", job[0]))
            process, output = start(where, tmp_path / f"job-{index}", repo, *args)
            processes.append(process)
            outputs.append(output)
            if index < running:
                if kind == "test":
                    _, observed = accepted(server, connections, job, process, output)
                    assert observed["cpus"] == observed["xdist"] == "2"
                else:
                    _until(lambda: (repo.bin / f"started-{job[1]}").exists() or process.poll() is not None,
                           "the worker within the runner-adjusted budget")
                    assert process.poll() is None, output.read_text("utf-8")
            else:
                _until(lambda: "in line." in output.read_text("utf-8") or process.poll() is not None,
                       "the command to wait behind busy runners")
                assert "number 1 in line." in output.read_text("utf-8"), output.read_text("utf-8")
                if kind == "work":
                    assert "2 Forge agents already run" in output.read_text("utf-8"), output.read_text("utf-8")
                assert process.poll() is None
                assert not ((job / "test-started.json") if kind == "test"
                            else repo.bin / f"started-{job[1]}").exists()
        publish(busy, "0")
        if kind == "test":
            _, observed = accepted(server, connections, jobs[-1], processes[-1], outputs[-1])
            assert observed["cpus"] == observed["xdist"] == "4"
        else:
            _until(lambda: (repo.bin / f"started-{jobs[-1][1]}").exists(),
                   "the waiting worker to use an idle runner's room")
        assert all(process.poll() is None for process in processes[:-1])
    finally:
        publish(busy, "0")
        if kind == "test":
            reap(processes, server, connections)
        else:
            finish(repo, processes)
    assert all(process.returncode == 0 for process in processes), [out.read_text("utf-8") for out in outputs]


@pytest.mark.parametrize("adopted,total,floor", [(False, 8_000_000_000, "1.5"),
                                                  (True, 16_000_000_000, "1.6")],
                         ids=["new", "earlier-adoption"])
def test_5_doctor_shows_the_machine_budget_on_new_and_adopted_repos(
        env, tmp_path, release_server, adopted, total, floor):
    repo = client(env, tmp_path, adopted)
    machine_cores(repo, 8)
    measurements(repo, tmp_path, available=2_000_000_000, runners=2, total=total, native=True)
    server, connections = release_server
    cfg = (repo.path / "forge.toml").read_text("utf-8")
    env.commit(repo.path, "forge.toml", "\n".join(line for line in cfg.splitlines()
        if line.partition("=")[0].strip() not in ("test", "fast_test")) + "\n")
    configure(env, server)
    _, folder = env.start_fix()
    processes = []
    try:
        process, output = start(folder, tmp_path / "test", repo, "test")
        processes.append(process)
        accepted(server, connections, folder, process, output)
        _until(lambda: any(row["started_at"] for row in rows(repo)),
               "Forge to register the running test process")
        result = repo.forge("doctor")
        assert "This machine: 8 cores, so 2 agents at once" in result.stdout, result.stdout + result.stderr
        assert f"Memory: 2.0 GB free, floor {floor} GB." in result.stdout, result.stdout
        assert "Test processes in use: 2. Busy runners: 2 (2 cores reserved)." in result.stdout, result.stdout
    finally:
        reap(processes, server, connections)
