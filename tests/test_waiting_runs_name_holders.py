"""Waiters identify real session and process owners, including after a client upgrade.

Test-audit: existing queue tests assert positions but omit holder names and recovery
commands. Real commands create admissions; only model providers wait at their edge.
"""
import json
import os
import subprocess

import pytest

from conftest import machine_cores
from test_close import env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _until
from test_lanes_agents import alive, finish, hold_agents, start
from test_lanes_tests import accepted, configure, reap, release_server, shell  # noqa: F401
from test_runs_wait_for_machine_load import client
from test_story import worktree
from test_tools_session_hold import Session

STORY = "waiting-runs-sit-for-hours-behind-places"
pytestmark = pytest.mark.platform


def stop_command(repo, item):
    root = repo.path.as_posix()
    return (f'forge stop --repo "{root}" {item}' if os.name == "nt" else
            shell(["forge", "stop", "--repo", root, item]))


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adoption"])
def test_1_waiting_run_names_each_holder_and_the_command_that_frees_it(
        env, tmp_path, monkeypatch, adopted):
    repo = client(env, tmp_path, adopted)
    config = (repo.path / "forge.toml").read_text("utf-8")
    config = "\n".join(line for line in config.splitlines()
                       if line.partition("=")[0].strip() not in ("workers", "tools"))
    env.commit(repo.path, "forge.toml", 'workers = "claude"\ntools = "both"\n' + config + "\n")
    repo.git("push", "-q", "origin", "main")
    machine_cores(repo, 6)
    jobs = []
    for name in ("First native typo", "Second native typo", "External typo", "Waiting typo"):
        made = repo.forge("fix", "start", name, "--done", "The typo is corrected", "--kind", "mechanical")
        assert made.returncode == 0, made.stdout + made.stderr
        item = name.lower().replace(" ", "-")
        jobs.append((item, worktree(repo, "fix/" + item).name))
    hold_agents(env)
    processes = []
    host = None
    try:
        with monkeypatch.context() as native:
            native.delenv("CODEX_THREAD_ID", raising=False)
            native.setenv("CLAUDECODE", "1")
            host = Session(repo, tmp_path / "host", "claude-session")
            for item, _ in jobs[:2]:
                result = host.forge("work", item)
                assert result.returncode == 0, result.stdout + result.stderr
                assert f"forge handback {item} --round 1" in result.stdout
        active, _ = start(repo.path, tmp_path / "active", repo, "work", jobs[2][0])
        processes.append(active)
        _until(lambda: (repo.bin / f"started-{jobs[2][1]}").exists(), "the external worker")
        waiting, output = start(repo.path, tmp_path / "waiting", repo, "work", jobs[3][0])
        processes.append(waiting)
        _until(lambda: "in line." in output.read_text("utf-8"), "the waiter to report its holders")
        said = output.read_text("utf-8")
        for item, _ in jobs[:2]:
            assert f"forge handback {item} --round 1 --subagent <id>" in said, said
        assert stop_command(repo, jobs[2][0]) in said, said
        for title in ("First native typo", "Second native typo", "External typo"):
            assert title in said, said
        holders = "\n".join(line for line in said.splitlines() if line.startswith("Held by "))
        assert jobs[3][0] not in holders, "the waiter must not list itself as a holder"
        assert waiting.poll() is None
        # Use the reported native recovery command in its owning session.
        with monkeypatch.context() as native:
            native.delenv("CODEX_THREAD_ID", raising=False)
            native.setenv("CLAUDECODE", "1")
            returned = host.forge("handback", jobs[0][0], "--round", "1", "--subagent", "worker",
                                  input="The round is complete.")
            assert returned.returncode == 0, returned.stdout + returned.stderr
        _until(lambda: (repo.bin / f"started-{jobs[3][1]}").exists(), "the waiter to take the freed place")
    finally:
        if host:
            host.close()
        finish(repo, processes)
    assert all(process.returncode == 0 for process in processes)


def test_2_a_close_with_an_exited_test_process_frees_its_place(env, tmp_path, release_server):
    repo = env.repo
    machine_cores(repo, 4)
    server, connections = release_server
    configure(env, server)
    first_item, first_folder = env.start_fix()
    _, second_folder = env.start("next-test", "fix/next-test", ".factory/fixes/next-test.json",
        {"kind": "fix", "why": "Run the next test", "done_when": "The next test passes"},
        {"app.py": 'print("next client passed")\n'})
    # Record the interpreter PID rather than a possible Windows venv redirector.
    parent_pid = tmp_path / "close-pid"
    launcher = repo.bin / "forge"
    launcher.write_text(launcher.read_text("utf-8").replace("from forge.cli import main",
        "import pathlib\n"
        f"if sys.argv[1:] == ['close', {first_item!r}]:\n"
        f"    pathlib.Path({json.dumps(parent_pid.as_posix())}).write_text(str(os.getpid()))\n"
        "from forge.cli import main"), "utf-8")
    processes = []
    child_pid = None
    try:
        first, first_output = start(first_folder, tmp_path / "first-close", repo, "close", first_item)
        processes.append(first)
        connection, observed = accepted(server, connections, first_folder, first, first_output)
        child_pid = observed["pid"]
        second, output = start(second_folder, tmp_path / "next-test", repo, "test")
        processes.append(second)
        _until(lambda: "in line." in output.read_text("utf-8") or second.poll() is not None,
               "the test waiter to name the close that holds its place")
        assert stop_command(repo, first_item) in output.read_text("utf-8")
        pid = int(parent_pid.read_text("utf-8"))
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=True, capture_output=True)
        else:
            os.kill(pid, 9)
        first.wait(timeout=30)
        assert alive(child_pid), "the real test command still owns the place"
        assert second.poll() is None
        connection.sendall(b"x")
        connection, _ = accepted(server, connections, second_folder, second, output)
        _until(lambda: not alive(child_pid), "the close's test process to exit")
        connection.sendall(b"x")
        assert second.wait(timeout=30) == 0, output.read_text("utf-8")
    finally:
        reap(processes, server, connections)
        if child_pid:
            _until(lambda: not alive(child_pid), "the owned test process to exit")
