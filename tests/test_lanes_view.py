"""Machine board data, CPU diagnostics and identity-safe, person-only stop.

Real workers produce the queue; only the model executable is held open.
Stop checks track process start times so a reused PID cannot impersonate the stopped run.
"""
import json
import os
import shutil
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import ROOT, _install, machine_cores
from test_close import env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _other_repo, _until
from test_lanes_agents import alive, finish, hold_agents, make_work, start, person, lane_adapter  # noqa: F401
from test_codex_worker import sdk_data  # noqa: F401
from test_codex_record import _freeze
from test_story import worktree
from test_lanes_tests import release_server  # noqa: F401

STORY = "FORGE-LANES-1"


def lanes(repo):
    done = repo.forge("board", "--json")
    assert done.returncode == 0, done.stderr
    board = json.loads(done.stdout)
    assert "load" in board["machine"]
    assert set(board["machine"]["memory"]) == {"total_bytes", "available_bytes"}
    for value in board["machine"]["memory"].values():
        assert value is None or isinstance(value, int) and value >= 0
    return board["lanes"]


@pytest.mark.parametrize("cores,agents,adopted", [(6, 3, False), (None, 1, True)])
def test_4_doctor_and_board_show_the_machine_split_and_agent_entries(env, tmp_path, cores, agents, adopted, person, lane_adapter):
    repo = env.repo
    machine_cores(repo, cores, system_count=64)
    version = repo.forge("--version").stdout.split()[-1]
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt on the earlier release")
        config = (repo.path / "forge.toml").read_text("utf-8").replace(
            'version = "v1.2.2"', f'version = "{version}"').replace('workers = "codex"', f'workers = "{lane_adapter}"')
    else:
        config = (repo.path / "forge.toml").read_text("utf-8") + 'repo = "client"\n'
    env.commit(repo.path, "forge.toml", config, "Use the current release")
    repo.git("push", "-q", "origin", "main")
    doctor = repo.forge("doctor")
    assert f"This machine: {cores or 2} cores, so {agents} agents at once and test runs on {agents} cores." in doctor.stdout
    # Native OS inputs, not Forge's derived dictionary: changing measurements must
    # reach both commands, so null or constant placeholders cannot satisfy this proof.
    shim = repo.bin / "forge"
    original = shim.read_text("utf-8")
    for total, available, load in [(8192000, 2048000, (1.25, 2.5, 3.75)),
                                   (16384000, 4096000, (4.5, 5.25, 6.0))]:
        native = f"import os\nos.getloadavg = lambda: {load!r}\n"
        if sys.platform == "linux":
            raw = f"MemTotal: {total // 1024} kB\nMemAvailable: {available // 1024} kB\n"
            native += ("from pathlib import Path\n_real_read = Path.read_text\n"
                       f"Path.read_text = lambda self, *a, **kw: {raw!r} "
                       "if str(self) == '/proc/meminfo' else _real_read(self, *a, **kw)\n")
        elif sys.platform == "darwin":
            _install(repo.bin, "sysctl", f"#!{sys.executable}\nprint({total})\n")
            stats = f"Mach Virtual Memory Statistics: (page size of 4096 bytes)\nPages free: {available // 4096}."
            _install(repo.bin, "vm_stat", f"#!{sys.executable}\nprint({stats!r})\n")
        else:
            native += ("import ctypes\ndef memory_status(pointer):\n"
                       f"    pointer._obj.total = {total}\n    pointer._obj.available = {available}\n"
                       "    return 1\nctypes.windll.kernel32.GlobalMemoryStatusEx = memory_status\n")
        shim.write_text(original.replace("from forge.cli import main", native + "from forge.cli import main"), "utf-8")
        for command in ("board", "next"):
            result = repo.forge(command, "--json")
            assert result.returncode == 0, result.stderr
            assert json.loads(result.stdout)["machine"] == {
                "load": list(load), "memory": {"total_bytes": total, "available_bytes": available}}
    shim.write_text(original, "utf-8")
    if sys.platform == "darwin":
        for command in ("sysctl", "vm_stat"):
            (repo.bin / command).unlink()
    first, first_name = make_work(repo, "First typo")
    folder = worktree(repo, "fix/" + first)
    synced = repo.forge("sync", cwd=folder)
    assert synced.returncode == 0, synced.stderr
    assert (folder / "forge.toml").read_text("utf-8") == config
    for host in (".claude", ".codex"):
        guide = (folder / host / "skills/forge/SKILL.md").read_text("utf-8")
        assert "forge board --json" in guide and "forge stop --id <id>" in guide
    repo.git("add", "-A", cwd=folder)
    repo.git("commit", "-qm", "Sync the client guidance", cwd=folder)
    # A process's usable cores can differ from the host total. The pytest picker must
    # forward the same budget that doctor and the agent lane use, not recompute the host half.
    base = repo.git("rev-parse", "HEAD", cwd=folder)
    code = "import os; print('Test budget: ' + os.environ['PYTEST_XDIST_AUTO_NUM_WORKERS'])"
    argv = [sys.executable, "-c", code]
    command = subprocess.list2cmdline(argv) if os.name == "nt" else shlex.join(argv)
    lines = config.splitlines()
    config = "test = " + json.dumps(command) + "\n" + "\n".join(
        line for line in lines if line.partition("=")[0].strip() != "test") + "\n"
    env.commit(folder, "forge.toml", config, "Report the test runner budget")
    env.commit(folder, "conftest.py", "# Shared test setup\n", "Change shared test setup")
    tested = repo.forge("test", "--pytest", base, cwd=folder)
    assert tested.returncode == 0, tested.stderr
    assert f"Test budget: {agents}\n" in tested.stdout
    other = _other_repo(tmp_path, repo.bin)
    other.write("forge.toml", (other.path / "forge.toml").read_text("utf-8") + f'workers = "{lane_adapter}"\n')
    other.git("add", "forge.toml")
    other.git("commit", "-qm", "Use Claude for workers")
    other.git("push", "-q", "origin", "main")
    waiting = [make_work(other, f"Other typo {n}") for n in range(agents)]
    hold_agents(env)
    # A real descendant ignores SIGTERM. The next agent must not inherit its load
    # after the recorded group leader has exited.
    tree = repo.bin / "tree-helper.py"
    tree.write_text('import os, pathlib, signal, time\n'
        'here = pathlib.Path(__file__).resolve().parent\n'
        'if os.name != "nt": signal.signal(signal.SIGTERM, signal.SIG_IGN)\n'
        '(here / "tree-pid").write_text(str(os.getpid()))\n'
        'while not (here / "go-all").exists(): time.sleep(0.05)\n', "utf-8")
    for executable in ("claude", "codex-app-server"):
        path = repo.bin / executable
        source = path.read_text("utf-8")
        indent = "" if executable == "claude" else "            "
        marker = indent + '(here / f"started-'
        spawn = (indent + 'if name.endswith("first-typo"):\n' + indent + '    import subprocess\n'
                 + indent + '    subprocess.Popen([sys.executable, str(here / "tree-helper.py")],\n'
                 + indent + '        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n')
        source = source.replace(marker, spawn + marker)
        path.write_text(source, "utf-8")
    processes = []
    descendant = None
    try:
        for where, item in [(repo.path, first), *[(other.path, item) for item, _ in waiting]]:
            process, _ = start(where, tmp_path / f"run-{len(processes)}", repo, "work", item)
            processes.append(process)
            _until(lambda: len(lanes(repo)["agents"]["entries"]) == len(processes), "visible entry")
        _until(lambda: (repo.bin / f"started-{first_name}").exists(), "first agent")
        _until(lambda: len([r for r in lanes(repo)["agents"]["entries"] if r["started_at"]]) == agents, "running agents")
        view = lanes(repo)
        assert view["agents"]["size"] == agents and view["tests"]["size"] == 1
        rows = view["agents"]["entries"]
        assert len({r["id"] for r in rows}) == agents + 1
        for index, row in enumerate(rows):
            assert row["kind"] == "work"
            assert row["repo_root"] == (repo.path if index == 0 else other.path).resolve().as_posix()
            assert row["repo_name"] == (repo.path if index == 0 else other.path).name
            assert row["item"] == (first if index == 0 else waiting[index - 1][0])
            assert row["model"] and row["effort"]
            assert row["joined_at"] and row["process"]["pid"]
            assert row["process"]["started"]
            # Running workers now publish their existing live log; waiting
            # entries still have no output before their command starts.
            if row["started_at"]:
                assert f"forge work {row['item']}" in Path(row["output_path"]).read_text("utf-8")
            else:
                assert row["output_path"] is None
            assert row["progress"] is None
        assert rows[-1]["started_at"] is None and rows[0]["started_at"]
        _until(lambda: (repo.bin / "tree-pid").exists(), "the model's descendant")
        descendant = int((repo.bin / "tree-pid").read_text("utf-8"))
        assert alive(descendant)
        if adopted:
            # Killing Forge alone must leave the live model holding its admission.
            # Codex normally handles closed stdin by ending its model; freeze its
            # driver first to model a crash where that cleanup cannot run.
            if lane_adapter == "codex":
                _freeze(rows[0]["process"]["pid"])
            processes[0].kill()
            processes[0].wait(timeout=30)
            assert alive(rows[0]["process"]["pid"])
            assert any(r["id"] == rows[0]["id"] for r in lanes(repo)["agents"]["entries"])
            assert not (repo.bin / f"started-{waiting[-1][1]}").exists()
        stopped = repo.forge("stop", "--id", rows[0]["id"])
        assert stopped.returncode == 0, stopped.stderr
        assert not alive(descendant), "stop freed admission while a group member still ran"
        _until(lambda: (repo.bin / f"started-{waiting[-1][1]}").exists(), "freed place")
        assert all(r["id"] != rows[0]["id"] for r in lanes(repo)["agents"]["entries"])
        stopped = repo.forge("stop", "--repo", str(other.path), waiting[-1][0])
        assert stopped.returncode == 0, stopped.stderr
        assert all(r["item"] != waiting[-1][0] for r in lanes(repo)["agents"]["entries"])
        assert lanes(repo)["tests"]["entries"] == []
        assert repo.forge("stop", "missing-item").returncode == 0
    finally:
        finish(repo, processes)
        if descendant is not None:
            _until(lambda: not alive(descendant), "the descendant to end")
    assert lanes(repo)["agents"]["entries"] == []


@pytest.mark.parametrize("scenario,older_queue", [
    ("identity", False), ("identity", True), ("worker-and-test", False),
], ids=["current-queue", "existing-queue", "worker-and-test"])
def test_5_stop_ends_named_runs_and_preserves_unverified_processes(
        env, tmp_path, monkeypatch, person, scenario, older_queue, lane_adapter, release_server):
    if scenario == "worker-and-test":
        from test_lanes_tests import check_stop_removes_waiter_and_ends_worker_and_test
        check_stop_removes_waiter_and_ends_worker_and_test(
            env, tmp_path, release_server, monkeypatch, lane_adapter)
    else:
        check_stop_refuses_workers_and_unverified_processes(
            env, tmp_path, monkeypatch, older_queue, lane_adapter)


def check_stop_refuses_workers_and_unverified_processes(env, tmp_path, monkeypatch, older_queue, lane_adapter):
    repo = env.repo
    machine_cores(repo, 2)
    item, name = make_work(repo, "First typo")
    hold_agents(env)
    # Check the recorded process and the actual model. Windows records a .cmd
    # launcher, so a fresh reply comes from the model's own pid, not the launcher's.
    child = repo.bin / "claude"
    child.write_text(child.read_text("utf-8").replace('name = pathlib.Path.cwd().name',
        'name = pathlib.Path.cwd().name\n(here / "model-pid").write_text(str(os.getpid()))').replace("    time.sleep(0.05)",
        '    challenge = here / "challenge"\n'
        '    if challenge.exists():\n'
        '        (here / "reply").write_text(str(os.getpid()) + ":" + challenge.read_text())\n'
        '    time.sleep(0.05)'), "utf-8")
    if lane_adapter == "claude" and older_queue and os.name != "nt":
        # Match Windows' .cmd launcher: Forge records the launcher, while the
        # actual model replying to our challenge has another pid.
        model = child.with_name("held-claude")
        child.rename(model)
        _install(repo.bin, "claude", f'''#!{sys.executable}
import subprocess, sys
sys.exit(subprocess.call([sys.executable, {model.as_posix()!r}, *sys.argv[1:]]))
''')
    process, _ = start(repo.path, tmp_path, repo, "work", item)
    try:
        _until(lambda: (repo.bin / f"started-{name}").exists(), "running worker")
        queue = Path(os.environ["APPDATA" if os.name == "nt" else "XDG_CONFIG_HOME"]) / "forge/agent-runs.json"
        if older_queue:
            # Existing releases recorded just the Forge parent and agent identities. Those
            # live processes must retain their place when the machine reader is upgraded.
            old = json.loads(queue.read_text("utf-8"))[0]
            queue.write_text(json.dumps([{"forge": old["forge"], "agent": old["process"],
                "repo": repo.path.as_posix(), "kind": "work"}]), "utf-8")
        row = lanes(repo)["agents"]["entries"][0]
        assert row["process"]["pid"] != process.pid
        model_pid = int((repo.bin / "model-pid").read_text("utf-8")) if lane_adapter == "claude" else None
        if lane_adapter == "claude" and older_queue and os.name != "nt":
            assert model_pid != row["process"]["pid"]

        def child_survives(challenge):
            assert alive(row["process"]["pid"]), "the recorded agent process was terminated"
            if lane_adapter == "codex":
                return
            (repo.bin / "challenge").write_text(challenge, "utf-8")
            reply = repo.bin / "reply"
            _until(lambda: reply.exists() and reply.read_text("utf-8") ==
                   f'{model_pid}:{challenge}', "the actual model child's reply")

        assert lanes(repo)["agents"]["entries"][0]["id"] == row["id"]
        for arguments in ((), (item, "--id", row["id"]), ("--id", row["id"], "--repo", str(repo.path))):
            refused = repo.forge("stop", *arguments)
            assert refused.returncode == 1
            assert refused.stderr == "Name an item with optional --repo, or use --id alone.\n"
            assert process.poll() is None
        monkeypatch.setenv("FORGE_WORKER", "1")
        refused = repo.forge("stop", item)
        assert refused.returncode == 1
        assert refused.stderr == "Only a person can run forge stop; ask the person to stop the run.\n"
        monkeypatch.delenv("FORGE_WORKER")
        # An unreadable identity retains its place but grants no right to signal it.
        saved = json.loads(queue.read_text("utf-8"))
        identity = saved[0]["agent" if older_queue else "process"]
        identity.pop("started")
        queue.write_text(json.dumps(saved), "utf-8")
        refused = repo.forge("stop", "--id", row["id"])
        assert refused.returncode == 1
        assert refused.stderr == "Forge cannot verify this run's process; nothing was stopped.\n"
        assert process.poll() is None
        child_survives("unverified")
        # Reused pid: the recorded start differs. Never terminate its new owner.
        identity["started"] = "not this process's start"
        queue.write_text(json.dumps(saved), "utf-8")
        assert repo.forge("stop", "--id", row["id"]).returncode == 0
        assert process.poll() is None
        child_survives("reused")
    finally:
        finish(repo, [process])
