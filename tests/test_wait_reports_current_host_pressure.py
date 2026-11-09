"""Test wait messages describe host pressure even behind another waiter."""
import json
import shutil

import pytest

from conftest import ROOT, Repo, machine_cores
from test_close import env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _until
from test_lanes_agents import start
from test_lanes_tests import accepted, configure, reap, release_server  # noqa: F401
from test_setup import _fresh_client
from test_waiting_runs_name_holders import stop_command

STORY = "test-lane-stuck-waiter"


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_1_waiters_report_memory_and_load_then_start_in_order(
        env, tmp_path, release_server, monkeypatch, adopted):
    # Contract: host pressure must not appear as running tests. The previous
    # implementation checked memory/load messages only for the first waiter.
    repo = env.repo
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        version = repo.forge("--version").stdout.split()[-1]
        config = repo.path / "forge.toml"
        config.write_text(config.read_text("utf-8").replace('version = "v1.2.2"',
                                                          f'version = "{version}"'), "utf-8")
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Upgrade the earlier client")
    else:
        client, result = _fresh_client(repo, env.gh, tmp_path)
        assert result.returncode == 0, result.stdout + result.stderr
        env.repo = repo = Repo(client, repo.bin)
    repo.git("config", "core.hooksPath", str(tmp_path / "fixture-hooks"))
    config = (repo.path / "forge.toml").read_text("utf-8")
    env.commit(repo.path, "forge.toml", "\n".join(line for line in config.splitlines()
        if line.partition("=")[0].strip() not in ("test", "fast_test")) + "\n")
    machine_cores(repo, 4)
    monkeypatch.setenv("FORGE_TEST_CPUS", "2")
    server, connections = release_server
    configure(env, server)
    pressure = tmp_path / "pressure"
    pressure.mkdir()
    (pressure / "memory").touch()
    launcher = repo.bin / "forge"
    launcher.write_text(launcher.read_text("utf-8").replace("from forge.cli import main",
        "from pathlib import Path\n"
        f"pressure = Path({json.dumps(pressure.as_posix())})\n"
        "machine.memory = lambda: dict(total_bytes=16_000_000_000, "
        "available_bytes=500_000_000 if (pressure / 'memory').exists() else 8_000_000_000)\n"
        "os.getloadavg = lambda: ((8.0 if (pressure / 'load').exists() else 0.0), 0.0, 0.0)\n"
        "from forge.cli import main"), "utf-8")
    processes, outputs, folders = [], [], []
    try:
        for number in range(2):
            _, folder = env.start(f"waiter-{number}", f"fix/waiter-{number}",
                f".factory/fixes/waiter-{number}.json",
                {"kind": "fix", "why": "Run the client test", "done_when": "The test completes"},
                {"app.py": f'print("waiter {number} passed")\n'})
            folders.append(folder)
            process, output = start(folder, tmp_path / f"waiter-{number}", repo, "test")
            processes.append(process)
            outputs.append(output)
            _until(lambda: "wait" in output.read_text("utf-8") or process.poll() is not None,
                   "the test command to wait")
            assert process.poll() is None, output.read_text("utf-8")
            message = output.read_text("utf-8")
            assert "waiting for memory: 0.5 GB free, starts above 1.6 GB." in message, message
            assert "already run" not in message and "Held by" not in message
        (pressure / "load").touch()
        (pressure / "memory").unlink()
        for output in outputs:
            _until(lambda: "load 2.0 per core" in output.read_text("utf-8"),
                   "the message to change from memory to load")
        (pressure / "memory").touch()
        (pressure / "load").unlink()
        for output in outputs:
            _until(lambda: output.read_text("utf-8").count("waiting for memory") == 2,
                   "the memory message to repeat after the reason changes")
        (pressure / "memory").unlink()
        for number, (folder, process, output) in enumerate(zip(folders, processes, outputs)):
            connection, observed = accepted(server, connections, folder, process, output)
            assert observed["cpus"] == "2"
            assert all(not (later / "test-started.json").exists() for later in folders[number + 1:])
            if number == 0:
                # A real test fills the lane. Pressure must preserve its recovery
                # details, including when the reason changes without moving us.
                waiting_output = outputs[1]
                _until(lambda: "2 Forge test processes already run" in waiting_output.read_text("utf-8"),
                       "the second test to observe the admitted holder")
                for reason, message in (("memory", "waiting for memory"), ("load", "load 2.0 per core")):
                    offset = len(waiting_output.read_text("utf-8"))
                    (pressure / reason).touch()
                    other = "load" if reason == "memory" else "memory"
                    (pressure / other).unlink(missing_ok=True)
                    _until(lambda: message in waiting_output.read_text("utf-8")[offset:],
                           "the occupied lane to report host pressure")
                    said = waiting_output.read_text("utf-8")[offset:]
                    assert "Held by Run the client test" in said, said
                    assert stop_command(repo, "waiter-0") in said, said
                    assert stop_command(repo, "waiter-1") not in said, said
                (pressure / "load").unlink()
            connection.sendall(b"x")
            assert process.wait(timeout=30) == 0, output.read_text("utf-8")
    finally:
        (pressure / "memory").unlink(missing_ok=True)
        (pressure / "load").unlink(missing_ok=True)
        reap(processes, server, connections)
