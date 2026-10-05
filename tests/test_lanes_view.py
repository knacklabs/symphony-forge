"""Machine board data, CPU diagnostics and identity-safe, person-only stop.

Real workers produce the queue; only the model executable is held open.
"""
import json
import os
import shutil
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import ROOT, machine_cores
from test_close import env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _other_repo, _until
from test_lanes_agents import finish, hold_agents, make_work, start, person  # noqa: F401
from test_story import worktree

STORY = "FORGE-LANES-1"


def lanes(repo):
    done = repo.forge("board", "--json")
    assert done.returncode == 0, done.stderr
    board = json.loads(done.stdout)
    assert "load" in board["machine"]
    assert set(board["machine"]["memory"]) == {"total_bytes", "available_bytes"}
    return board["lanes"]


@pytest.mark.parametrize("cores,agents,adopted", [(6, 3, False), (None, 1, True)])
def test_4_doctor_and_board_show_the_machine_split_and_agent_entries(env, tmp_path, cores, agents, adopted, person):
    repo = env.repo
    machine_cores(repo, cores, system_count=64)
    version = repo.forge("--version").stdout.split()[-1]
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt on the earlier release")
        config = (repo.path / "forge.toml").read_text("utf-8").replace(
            'version = "v1.2.2"', f'version = "{version}"').replace('workers = "codex"', 'workers = "claude"')
    else:
        config = (repo.path / "forge.toml").read_text("utf-8") + 'repo = "client"\n'
    env.commit(repo.path, "forge.toml", config, "Use the current release")
    repo.git("push", "-q", "origin", "main")
    doctor = repo.forge("doctor")
    assert f"This machine: {cores or 2} cores, so {agents} agents at once and test runs on {agents} cores." in doctor.stdout
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
    other.write("forge.toml", (other.path / "forge.toml").read_text("utf-8") + 'workers = "claude"\n')
    other.git("add", "forge.toml")
    other.git("commit", "-qm", "Use Claude for workers")
    other.git("push", "-q", "origin", "main")
    waiting = [make_work(other, f"Other typo {n}") for n in range(agents)]
    hold_agents(env)
    processes = []
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
            assert row["output_path"] is None and row["progress"] is None
        assert rows[-1]["started_at"] is None and rows[0]["started_at"]
        stopped = repo.forge("stop", "--id", rows[0]["id"])
        assert stopped.returncode == 0, stopped.stderr
        _until(lambda: (repo.bin / f"started-{waiting[-1][1]}").exists(), "freed place")
        assert all(r["id"] != rows[0]["id"] for r in lanes(repo)["agents"]["entries"])
        stopped = repo.forge("stop", "--repo", str(other.path), waiting[-1][0])
        assert stopped.returncode == 0, stopped.stderr
        assert all(r["item"] != waiting[-1][0] for r in lanes(repo)["agents"]["entries"])
        assert lanes(repo)["tests"]["entries"] == []
        assert repo.forge("stop", "missing-item").returncode == 0
    finally:
        finish(repo, processes)
    assert lanes(repo)["agents"]["entries"] == []


@pytest.mark.parametrize("older_queue", [False, True], ids=["current-queue", "existing-queue"])
def test_5_stop_refuses_workers_and_unverified_processes_without_killing_them(env, tmp_path, monkeypatch, person, older_queue):
    repo = env.repo
    machine_cores(repo, 2)
    item, name = make_work(repo, "First typo")
    hold_agents(env)
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
        assert lanes(repo)["agents"]["entries"][0]["id"] == row["id"]
        for arguments in ((), (item, "--id", row["id"]), ("--id", row["id"], "--repo", str(repo.path))):
            refused = repo.forge("stop", *arguments)
            assert refused.returncode != 0 and "Name an item" in refused.stderr
            assert process.poll() is None
        monkeypatch.setenv("FORGE_WORKER", "1")
        refused = repo.forge("stop", item)
        assert refused.returncode != 0 and "Only a person" in refused.stderr
        monkeypatch.delenv("FORGE_WORKER")
        # An unreadable identity retains its place but grants no right to signal it.
        saved = json.loads(queue.read_text("utf-8"))
        identity = saved[0]["agent" if older_queue else "process"]
        identity.pop("started")
        queue.write_text(json.dumps(saved), "utf-8")
        refused = repo.forge("stop", "--id", row["id"])
        assert refused.returncode != 0 and "cannot verify" in refused.stderr
        assert process.poll() is None
        # Reused pid: the recorded start differs. Never terminate its new owner.
        identity["started"] = "not this process's start"
        queue.write_text(json.dumps(saved), "utf-8")
        assert repo.forge("stop", "--id", row["id"]).returncode == 0
        assert process.poll() is None
    finally:
        finish(repo, [process])
