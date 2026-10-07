"""The client's real commands prove worker admission, lifecycle and reporting."""
import json
import os
import shlex
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import machine_cores
from test_close import Forge, env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _other_repo, _until
from test_lanes_agents import alive, finish, hold_agents, make_work, start

STORY = "FORGE-LANES-1"


def shell(argv):
    return subprocess.list2cmdline(argv) if os.name == "nt" else shlex.join(argv)


def configure(owner, server):
    repo = owner.repo
    script = '''import json, os, pathlib, runpy, socket, sys
here = pathlib.Path.cwd()
print("collected 2 items", flush=True)
print("test_app.py . [ 50%]", flush=True)
with socket.create_connection(("127.0.0.1", int(sys.argv[1])), timeout=60) as connection:
    marker = here / "test-started.json"
    marker.with_suffix(".tmp").write_text(json.dumps({
        "pid": os.getpid(), "base": sys.argv[2],
        "cpus": os.environ.get("FORGE_TEST_CPUS"),
        "xdist": os.environ.get("PYTEST_XDIST_AUTO_NUM_WORKERS")}))
    marker.with_suffix(".tmp").replace(marker)
    connection.recv(1)
runpy.run_path(str(here / "app.py"))
'''
    owner.commit(repo.path, "run_check.py", script, "Add the client test")
    owner.commit(repo.path, "app.py", 'print("client passed")\n', "Add the client app")
    cfg = (repo.path / "forge.toml").read_text("utf-8")
    cmd = shell([sys.executable, "run_check.py", str(server.getsockname()[1]), "{base}"])
    owner.commit(repo.path, "forge.toml", cfg + 'test = "exit 99"\nfast_test = ' + json.dumps(cmd) + '\n',
                 "Use related client tests")
    repo.git("push", "-q", "origin", "main")


@pytest.fixture
def release_server():
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        server.settimeout(30)
        connections = []
        try:
            yield server, connections
        finally:
            release(connections)
            for connection in connections:
                connection.close()


def release(connections):
    for connection in connections:
        try:
            connection.sendall(b"x")
        except OSError:
            pass


def accepted(server, connections, folder, process, output):
    _until(lambda: (folder / "test-started.json").exists() or process.poll() is not None,
           "the client test to start")
    assert process.poll() is None, output.read_text("utf-8")
    connection, _ = server.accept()
    connections.append(connection)
    return connection, json.loads((folder / "test-started.json").read_text("utf-8"))


def rows(repo):
    result = repo.forge("board", "--json")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["lanes"]["tests"]["entries"]


def reap(processes, server, connections):
    # A waiter may start after its predecessor is released during failed-test cleanup.
    release(connections)
    server.settimeout(0.1)
    deadline = time.monotonic() + 30
    while any(process.poll() is None for process in processes) and time.monotonic() < deadline:
        try:
            connection, _ = server.accept()
        except socket.timeout:
            continue
        connections.append(connection)
        connection.sendall(b"x")
    for process in processes:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=30)


@pytest.mark.parametrize("scenario", [
    "shared-lane", "killed-forge", "no-command", "missing-origin", "dirty-picker", "upgrade",
])
def test_2_workers_and_close_share_one_test_lane(env, tmp_path, release_server, monkeypatch, scenario):
    if scenario == "shared-lane":
        check_worker_and_close_share_the_lane_and_dirty_tests_always_run(env, tmp_path, release_server)
    elif scenario == "killed-forge":
        check_killing_forge_keeps_the_lane_until_the_test_command_ends(env, tmp_path, release_server)
    elif scenario in ("no-command", "missing-origin"):
        check_test_names_an_absent_command_or_missing_default_reference(env, scenario == "missing-origin")
    elif scenario == "dirty-picker":
        check_worker_picker_tests_dirty_code_even_with_only_docs_committed(env, monkeypatch)
    else:
        from test_lanes_upgrade import check_previous_release_upgrade_keeps_settings_and_runs_both_lanes
        check_previous_release_upgrade_keeps_settings_and_runs_both_lanes(env, tmp_path)


def check_worker_and_close_share_the_lane_and_dirty_tests_always_run(env, tmp_path, release_server):
    # Close's existing docs/cache skips must not bypass a worker's dirty code.
    server, connections = release_server
    repo = env.repo
    machine_cores(repo, 6)
    configure(env, server)
    _, worker = env.start_fix({"README.md": "A doc-only committed change\n"})
    (worker / "app.py").write_text('raise SystemExit(7)\n', "utf-8")
    other = _other_repo(tmp_path, repo.bin)
    closing_home = tmp_path / "closing"
    closing_home.mkdir()
    closing = Forge(other, env.gh, closing_home)
    cfg = (other.path / "forge.toml").read_text("utf-8")
    closing.commit(other.path, "forge.toml", cfg + 'checks = ["tests", "forge-pr-check"]\n',
                   "Name the client's CI checks")
    configure(closing, server)
    item, folder = closing.start_fix({"app.py": 'print("close passed")\n'})
    processes = []
    try:
        first, output = start(worker, tmp_path / "worker", repo, "test")
        processes.append(first)
        connection, observed = accepted(server, connections, worker, first, output)
        assert observed["cpus"] == observed["xdist"] == "3"
        assert observed["base"] == repo.git("merge-base", "origin/main", "HEAD", cwd=worker)
        second, close_output = start(other.path, tmp_path / "close", repo, "close", item)
        processes.append(second)
        _until(lambda: "in line." in close_output.read_text("utf-8") or second.poll() is not None,
               "close to wait for the test lane")
        assert second.poll() is None, close_output.read_text("utf-8")
        assert not (folder / "test-started.json").exists()
        entries = rows(repo)
        assert len(entries) == 2 and sum(e["started_at"] is not None for e in entries) == 1
        active = next(e for e in entries if e["started_at"])
        assert active["process"]["pid"] != first.pid
        assert active["progress"] == {"done": 1, "total": 2}
        assert Path(active["output_path"]).is_file()
        assert "collected 2 items" in Path(active["output_path"]).read_text("utf-8")
        connection.sendall(b"x")
        assert first.wait(timeout=30) == 7
        assert "exited with status 7" in output.read_text("utf-8")
        connection, observed = accepted(server, connections, folder, second, close_output)
        assert observed["cpus"] == observed["xdist"] == "3"
        assert observed["base"] == other.git("merge-base", "origin/main", "HEAD", cwd=folder)
        connection.sendall(b"x")
        assert second.wait(timeout=60) == 0, close_output.read_text("utf-8")
        assert "exited with status 0" in env.prompt()
        assert rows(repo) == []
        for status in (0, 7):
            (worker / "test-started.json").unlink()
            (worker / "app.py").write_text(f'raise SystemExit({status})\n', "utf-8")
            run, output = start(worker, tmp_path / f"again-{status}", repo, "test")
            processes.append(run)
            connection, _ = accepted(server, connections, worker, run, output)
            connection.sendall(b"x")
            assert run.wait(timeout=30) == status
            assert f"exited with status {status}" in output.read_text("utf-8")
        (worker / "app.py").write_text('print("clean worker passed")\n', "utf-8")
        env.commit(worker, ".gitignore", "test-started.json\ntest-started.tmp\n",
                   "Commit the passing app and ignore test diagnostics")
        assert repo.git("status", "--porcelain", cwd=worker) == ""
        # Close may cache identical clean commits. A worker must execute twice even then.
        for attempt in range(2):
            (worker / "test-started.json").unlink()
            assert repo.git("status", "--porcelain", cwd=worker) == ""
            run, output = start(worker, tmp_path / f"clean-{attempt}", repo, "test")
            processes.append(run)
            connection, _ = accepted(server, connections, worker, run, output)
            connection.sendall(b"x")
            assert run.wait(timeout=30) == 0, output.read_text("utf-8")
            assert "exited with status 0" in output.read_text("utf-8")
        assert rows(repo) == []
    finally:
        reap(processes, server, connections)


def check_killing_forge_keeps_the_lane_until_the_test_command_ends(env, tmp_path, release_server):
    server, connections = release_server
    repo = env.repo
    machine_cores(repo, 8)
    configure(env, server)
    _, folder = env.start_fix()
    # Kill the Forge interpreter, including when a venv redirector starts it.
    parent_pid = tmp_path / "forge-parent-pid"
    launcher = repo.bin / "forge"
    launcher.write_text(launcher.read_text("utf-8").replace("from forge.cli import main",
        "import os, pathlib\n"
        f"pathlib.Path({json.dumps(str(parent_pid))}).write_text(str(os.getpid()))\n"
        "from forge.cli import main"), "utf-8")
    redirector = tmp_path / "redirector.py"
    redirector.write_text("import subprocess, sys\n"
        f"raise SystemExit(subprocess.call([sys.executable, {json.dumps(str(launcher))}, *sys.argv[1:]]))\n",
        "utf-8")
    processes = []
    child_pid = None
    try:
        first, output = start(folder, tmp_path / "first", repo, "test", launcher=redirector)
        processes.append(first)
        connection, observed = accepted(server, connections, folder, first, output)
        child_pid = observed["pid"]
        assert observed["cpus"] == observed["xdist"] == "4"
        forge_pid = int(parent_pid.read_text("utf-8"))
        assert forge_pid != first.pid and forge_pid != child_pid
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/PID", str(forge_pid)], check=True, capture_output=True)
        else:
            os.kill(forge_pid, 9)
        _until(lambda: not alive(forge_pid), "the actual Forge interpreter to end")
        first.wait(timeout=30)
        assert alive(child_pid)
        second, waiting = start(folder, tmp_path / "second", repo, "test")
        processes.append(second)
        _until(lambda: "in line." in waiting.read_text("utf-8"), "the orphan's lane to remain taken")
        assert len(rows(repo)) == 2
        connection.sendall(b"x")
        _until(lambda: not alive(child_pid), "the orphaned client test to finish")
        _until(lambda: json.loads((folder / "test-started.json").read_text("utf-8"))["pid"] != child_pid,
               "the next client test to start")
        connection, _ = accepted(server, connections, folder, second, waiting)
        connection.sendall(b"x")
        assert second.wait(timeout=30) == 0, waiting.read_text("utf-8")
        assert rows(repo) == []
    finally:
        reap(processes, server, connections)
        if child_pid:
            _until(lambda: not alive(child_pid), "owned orphan to exit")


def check_stop_removes_waiter_and_ends_worker_and_test(env, tmp_path, release_server, monkeypatch, lane_adapter):
    monkeypatch.delenv("FORGE_WORKER", raising=False)
    server, connections = release_server
    repo = env.repo
    machine_cores(repo, 6)
    configure(env, server)
    item, folder = env.start_fix()
    hold_agents(env)
    provider = repo.bin / ("claude" if lane_adapter == "claude" else "codex-app-server")
    indent = "" if lane_adapter == "claude" else "            "
    marker = 'name = pathlib.Path.cwd().name' if lane_adapter == "claude" else 'name = pathlib.Path(cwd).name'
    provider.write_text(provider.read_text("utf-8").replace(marker,
        marker + f'\n{indent}(here / "model-pid").write_text(str(os.getpid()))'), "utf-8")
    worker_pid = tmp_path / "worker-pid"
    launcher = repo.bin / "forge"
    launcher.write_text(launcher.read_text("utf-8").replace("from forge.cli import main",
        "import os, pathlib\n"
        f"if sys.argv[1:] == ['work', {json.dumps(item)}]:\n"
        f"    pathlib.Path({json.dumps(str(worker_pid))}).write_text(str(os.getpid()))\n"
        "from forge.cli import main"), "utf-8")
    processes = []
    worker_processes = []
    try:
        worker, worker_output = start(repo.path, tmp_path / "worker", repo, "work", item)
        worker_processes.append(worker)
        started = repo.bin / f"started-{folder.name}"
        _until(lambda: started.exists() or worker.poll() is not None, "the actual worker's model to start")
        assert worker.poll() is None, worker_output.read_text("utf-8")
        first, output = start(folder, tmp_path / "first", repo, "test")
        processes.append(first)
        _, observed = accepted(server, connections, folder, first, output)
        second, waiting = start(folder, tmp_path / "waiting", repo, "test")
        processes.append(second)
        _until(lambda: "in line." in waiting.read_text("utf-8"), "a waiting test")
        queued = next(e for e in rows(repo) if e["started_at"] is None)
        stopped = repo.forge("stop", "--id", queued["id"])
        assert stopped.returncode == 0, stopped.stderr
        assert second.wait(timeout=30) != 0
        assert "This run was stopped while waiting; it will not start." in waiting.read_text("utf-8")
        assert json.loads((folder / "test-started.json").read_text("utf-8"))["pid"] == observed["pid"]
        assert alive(observed["pid"])
        board = repo.forge("board", "--json")
        assert board.returncode == 0, board.stderr
        lanes = json.loads(board.stdout)["lanes"]
        agent = next(e for e in lanes["agents"]["entries"] if e["item"] == item)
        assert len(lanes["tests"]["entries"]) == 1
        assert agent["started_at"] and alive(agent["process"]["pid"])
        model_pid = int((repo.bin / "model-pid").read_text("utf-8"))
        assert alive(model_pid) and alive(int(worker_pid.read_text("utf-8")))
        stopped = repo.forge("stop", item)
        assert stopped.returncode == 0, stopped.stderr
        first.wait(timeout=30)
        worker.wait(timeout=30)
        assert not alive(observed["pid"])
        assert not alive(agent["process"]["pid"])
        assert not alive(model_pid)
        assert not alive(int(worker_pid.read_text("utf-8")))
        board = repo.forge("board", "--json")
        assert board.returncode == 0, board.stderr
        assert all(lane["entries"] == [] for lane in json.loads(board.stdout)["lanes"].values())
        # Reuse both admissions with real commands, rather than only inspecting rows.
        next_item, next_name = make_work(repo, "Work after stop")
        replacement, replacement_output = start(repo.path, tmp_path / "replacement-worker", repo, "work", next_item)
        worker_processes.append(replacement)
        _until(lambda: (repo.bin / f"started-{next_name}").exists() or replacement.poll() is not None,
               "a worker to take the freed agent place")
        assert replacement.poll() is None, replacement_output.read_text("utf-8")
        (folder / "test-started.json").unlink()
        next_test, next_output = start(folder, tmp_path / "replacement-test", repo, "test")
        processes.append(next_test)
        connection, _ = accepted(server, connections, folder, next_test, next_output)
        connection.sendall(b"x")
        assert next_test.wait(timeout=30) == 0, next_output.read_text("utf-8")
        (repo.bin / f"go-{next_name}").touch()
        assert replacement.wait(timeout=30) == 0, replacement_output.read_text("utf-8")
        assert rows(repo) == []
    finally:
        release(connections)
        finish(repo, worker_processes)
        reap(processes, server, connections)


def check_test_names_an_absent_command_or_missing_default_reference(env, configured):
    repo = env.repo
    if configured:
        cfg = (repo.path / "forge.toml").read_text("utf-8") + 'test = "echo should-not-run"\n'
        env.commit(repo.path, "forge.toml", cfg)
        repo.git("update-ref", "-d", "refs/remotes/origin/main")
    result = repo.forge("test")
    assert result.returncode == (1 if configured else 0), result.stderr
    if configured:
        assert "fetch" in result.stderr.lower() and "origin/main" in result.stderr
        assert len(result.stderr.strip().splitlines()) == 1
        assert "should-not-run" not in result.stdout
    else:
        assert "forge.toml names no test command" in result.stdout


def check_worker_picker_tests_dirty_code_even_with_only_docs_committed(env, monkeypatch):
    # The lane wrapper must not delegate to a picker that ignores its worker's dirty code.
    repo = env.repo
    machine_cores(repo, 6)
    monkeypatch.setenv("PYTHONPATH", str(repo.path))
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    repo.write("app.py", "VALUE = 1\n")
    repo.write("pyproject.toml", '[project]\nname = "lane-client"\nversion = "0.0.0"\n')
    repo.write("tests/test_app.py", "from app import VALUE\n"
               "def test_current_app():\n    assert VALUE == 1\n")
    repo.write("tests/test_unrelated.py", "def test_unrelated():\n"
               "    assert False, 'unrelated test was selected'\n")
    cfg = (repo.path / "forge.toml").read_text("utf-8")
    cfg += "test = " + json.dumps(shell([sys.executable, "-m", "pytest", "tests", "-q"])) + "\n"
    cfg += 'fast_test = "forge test --pytest {base}"\n'
    repo.write("forge.toml", cfg)
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Configure a pytest client")
    repo.git("push", "-q", "origin", "main")
    _, folder = env.start_fix({"README.md": "Only this doc is committed\n"})
    monkeypatch.setenv("PYTHONPATH", str(folder))
    (folder / "app.py").write_text("VALUE = 2\n", "utf-8")
    result = repo.forge("test", cwd=folder)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "test_current_app" in result.stdout and "1 failed" in result.stdout
    assert "unrelated test was selected" not in result.stdout
    assert "exited with status 1" in result.stdout
    # Dirty shared pytest settings must select the full suite, even with no dirty source.
    (folder / "app.py").write_text("VALUE = 1\n", "utf-8")
    project = folder / "pyproject.toml"
    project.write_text(project.read_text("utf-8") + '\n[tool.pytest.ini_options]\naddopts = "-ra"\n',
                       "utf-8")
    result = repo.forge("test", cwd=folder)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Shared test inputs changed" in result.stdout
    assert "unrelated test was selected" in result.stdout
    assert "1 failed, 1 passed" in result.stdout
