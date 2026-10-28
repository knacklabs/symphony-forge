"""Worker tests and close share one machine-wide process budget across repos."""
import json
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT, Repo, machine_cores
from test_close import Forge, GREEN, env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _other_repo, _until
from test_lanes_agents import start
from test_lanes_tests import accepted, configure, reap, release_server, rows  # noqa: F401
from test_lanes_tests import shell
from test_machine_shared_test_budget import _run
from test_setup import _fresh_client

STORY = "FORGE-BUDGET-1"


def _test_runs_share_processes_across_repos(
        env, tmp_path, release_server, adopted, cores, budget, cap, monkeypatch):
    # The old policy admitted two runs of four on eight cores. The shared
    # budget permits two runs of two, or one run of four, including close.
    workers = cap or budget
    size = budget // workers
    if cap:
        monkeypatch.setenv("FORGE_TEST_CPUS", str(cap))
    else:
        monkeypatch.delenv("FORGE_TEST_CPUS", raising=False)
    repo = env.repo
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt on the earlier release")
        version = repo.forge("--version").stdout.split()[-1]
        config = repo.path / "forge.toml"
        env.commit(repo.path, "forge.toml", config.read_text("utf-8").replace(
            'version = "v1.2.2"', f'version = "{version}"'), "Upgrade the client")
        repo.git("checkout", "-qb", "fix/upgrade-lanes")
        synced = repo.forge("sync")
    else:
        client, synced = _fresh_client(repo, env.gh, tmp_path)
        env.repo = repo = Repo(client, repo.bin)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    # Fixture commits configure the client, rather than testing its commit gates.
    repo.git("config", "core.hooksPath", str(tmp_path / "fixture-hooks"))
    if adopted:
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Sync the upgraded client")
        repo.git("checkout", "-q", "main")
        repo.git("merge", "-q", "--ff-only", "fix/upgrade-lanes")
    machine_cores(repo, cores, system_count=64)
    server, connections = release_server
    # The old fixture names its own test command. Replace only that setting before
    # configuring the real socket-held client test used by both test and close.
    config = (repo.path / "forge.toml").read_text("utf-8")
    env.commit(repo.path, "forge.toml", 'test_place = "local"\n' + "\n".join(line for line in config.splitlines()
        if line.partition("=")[0].strip() not in ("test", "fast_test", "test_place"))
        + '\n')
    configure(env, server)
    _, first_folder = env.start_fix()
    _, second_folder = env.start("second", "fix/second", ".factory/fixes/second.json",
        {"kind": "fix", "why": "Second client test", "done_when": "The test passes"},
        {"app.py": 'print("second passed")\n'})
    other = _other_repo(tmp_path, repo.bin)
    closing_home = tmp_path / "closing"
    closing_home.mkdir()
    closing = Forge(other, env.gh, closing_home)
    # Fresh init queried branch protection through the same external gh stub.
    # Restore CI answers for the close rather than accepting that setup reply.
    closing.checks(GREEN)
    closing.commit(other.path, "forge.toml", 'test_place = "local"\nchecks = ["tests", "forge-pr-check"]\n' +
                   (other.path / "forge.toml").read_text("utf-8"), "Name the client's checks")
    configure(closing, server)
    item, close_folder = closing.start_fix()
    processes = []
    outputs = []
    folders = [first_folder, second_folder, close_folder]
    try:
        for index, folder in enumerate(folders):
            args = ("close", item) if index == 2 else ("test",)
            process, output = start(other.path if index == 2 else folder,
                                    tmp_path / f"run-{index}", repo, *args)
            processes.append(process)
            outputs.append(output)
            if index < size:
                _, observed = accepted(server, connections, folder, process, output)
                assert observed["cpus"] == observed["xdist"] == str(workers)
            else:
                _until(lambda: "in line." in output.read_text("utf-8") or process.poll() is not None,
                       "the next test run to wait")
                assert process.poll() is None, output.read_text("utf-8")
                assert not (folder / "test-started.json").exists()
        _until(lambda: len(rows(repo)) == 3 and
               sum(row["started_at"] is not None for row in rows(repo)) == size,
               "the running test commands to be registered")
        for command in ("board", "lanes"):
            result = repo.forge(command, "--json")
            assert result.returncode == 0, result.stderr
            payload = json.loads(result.stdout)
            lane = (payload["lanes"] if command == "board" else payload)["tests"]
            assert lane["size"] == budget
            assert sum(row["processes"] for row in lane["entries"] if row.get("admitted")) <= budget
            assert sum(row["started_at"] is not None for row in lane["entries"]) == size
            if command == "lanes":
                assert [row["place"] for row in lane["entries"]] == ([0, 0, 1] if size == 2 else [0, 1, 2])
        assert f"Test lane: {budget} places." in repo.forge("lanes").stdout
        doctor = repo.forge("doctor")
        assert f"{budget} test processes shared by all runs." in doctor.stdout
        for host in (".claude", ".codex"):
            guide = (repo.path / host / "skills/forge/SKILL.md").read_text("utf-8")
            assert "share one process budget" in guide
        # Free exactly one place: the next queued command must start while any
        # other admitted command still owns its place.
        connections[0].sendall(b"x")
        assert processes[0].wait(timeout=30) == 0, outputs[0].read_text("utf-8")
        for index in range(size, 3):
            connection, observed = accepted(server, connections, folders[index], processes[index], outputs[index])
            assert observed["cpus"] == observed["xdist"] == str(workers)
            if size == 2:
                assert processes[1].poll() is None
            connection.sendall(b"x")
            assert processes[index].wait(timeout=60) == 0, outputs[index].read_text("utf-8")
        if size == 2:
            connections[1].sendall(b"x")
            assert processes[1].wait(timeout=30) == 0, outputs[1].read_text("utf-8")
        assert rows(repo) == []
    finally:
        reap(processes, server, connections)


def _small_pytest_runs_use_remaining_processes_and_count_older_entries(
        env, tmp_path, release_server, legacy, picker):
    # Mixed releases must reserve the old four-process default. Current entries
    # reserve their own allocation, so even one picked file gets only the room left.
    repo = env.repo
    machine_cores(repo, 8)
    server, connections = release_server
    cfg = (repo.path / "forge.toml").read_text("utf-8")
    cfg = "\n".join(line for line in cfg.splitlines()
                    if line.partition("=")[0].strip() not in ("test", "fast_test"))
    command = shell([sys.executable, "-m", "pytest", "-q", "-n", "4"])
    env.commit(repo.path, "forge.toml", 'fast_test = "forge test --pytest {base}"\n'
               + "test = " + json.dumps(command) + "\n" + cfg)
    repo.git("push", "-q", "origin", "main")
    probe = '''import json, os, pathlib, socket
def test_allocation(request):
    with socket.create_connection(("127.0.0.1", PORT), timeout=60) as connection:
        marker = pathlib.Path("test-started.json")
        marker.with_suffix(".tmp").write_text(json.dumps({
            "pid": os.getpid(), "cpus": os.environ["FORGE_TEST_CPUS"],
            "xdist": os.environ["PYTEST_XDIST_AUTO_NUM_WORKERS"],
            "workers": request.config.workerinput["workercount"]}), encoding="utf-8")
        marker.with_suffix(".tmp").replace(marker)
        connection.recv(1)
'''.replace("PORT", str(server.getsockname()[1]))
    _, folder = env.start_fix({"test_allocation.py": probe})
    holder = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.buffer.read(1)"],
                              stdin=subprocess.PIPE)
    processes = []
    try:
        version = repo.forge("--version").stdout.split()[-1].removeprefix("v")
        entry = _run(repo, "1.2.2" if legacy else version, "budget-holder", holder.pid, kind="test")
        entry["title"] = "Earlier test run"
        if not legacy:
            entry["processes"] = 3
        registry = tmp_path / "config" / "forge" / "agent-runs.json"
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(json.dumps([entry]), "utf-8")
        base = repo.git("merge-base", "origin/main", "HEAD", cwd=folder)
        args = ("test", "--pytest", base) if picker else ("test",)
        process, output = start(folder, tmp_path / "small-picker", repo, *args)
        processes.append(process)
        if legacy:
            _until(lambda: "number 1 in line." in output.read_text("utf-8")
                   or (folder / "test-started.json").exists() or process.poll() is not None,
                   "the older release to hold the process budget")
            assert process.poll() is None, output.read_text("utf-8")
            assert not (folder / "test-started.json").exists()
            doctor = repo.forge("doctor")
            assert "Test processes in use: 4." in doctor.stdout, doctor.stdout
            assert "Older-release test run: Earlier test run; counts as 4 test processes." in doctor.stdout
            holder.communicate(b"x", timeout=10)
        connection, observed = accepted(server, connections, folder, process, output)
        expected = 4 if legacy else 1
        assert observed["workers"] == expected
        assert observed["cpus"] == observed["xdist"] == str(expected)
        lane = json.loads(repo.forge("lanes", "--json").stdout)["tests"]
        mine = next(row for row in lane["entries"] if row["checkout_root"] == folder.resolve().as_posix())
        assert mine["processes"] == expected
        assert lane["used"] == 4
        connection.sendall(b"x")
        assert process.wait(timeout=30) == 0, output.read_text("utf-8")
    finally:
        if holder.poll() is None:
            holder.communicate(b"x", timeout=10)
        reap(processes, server, connections)


@pytest.mark.parametrize("scenario", [
    pytest.param(("shared", 8, 4, 2, False), id="shared-new"),
    pytest.param(("shared", 8, 4, None, False), id="full-budget"),
    pytest.param(("shared", 4, 2, None, False), id="four-cores"),
    pytest.param(("shared", None, 1, None, False), id="unknown-cores"),
    pytest.param(("shared", 8, 4, 2, True), id="shared-adopted"),
    pytest.param(("small", True, False), id="older-release"),
    pytest.param(("small", False, False), id="small-nested-picker"),
    pytest.param(("small", False, True), id="small-direct-picker"),
])
def test_2_test_runs_share_one_process_budget(env, tmp_path, release_server, monkeypatch, scenario):
    if scenario[0] == "shared":
        _, cores, budget, cap, adopted = scenario
        _test_runs_share_processes_across_repos(
            env, tmp_path, release_server, adopted, cores, budget, cap, monkeypatch)
    else:
        _, legacy, picker = scenario
        _small_pytest_runs_use_remaining_processes_and_count_older_entries(
            env, tmp_path, release_server, legacy, picker)
