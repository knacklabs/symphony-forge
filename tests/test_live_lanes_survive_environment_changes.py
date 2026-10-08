"""Live admissions survive callers with different time zones and locales.

Test-audit: real work/test waiters and OS processes own the assertions; only the
model provider waits at its edge. Existing lane tests use one inherited environment.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import ROOT, machine_cores
from test_close import env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _until
from test_lanes_agents import finish, hold_agents, make_work, start
from test_lanes_tests import accepted, configure, reap, release_server  # noqa: F401
from test_story import worktree

STORY = "lane-identity-env"
pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX ps timezone and locale contract")


def environment(monkeypatch, zone, locale):
    monkeypatch.setenv("TZ", zone)
    monkeypatch.setenv("LANG", locale)
    monkeypatch.setenv("LC_ALL", locale)


def client(env, history):
    repo = env.repo
    if history == "new":
        path, remote = env.tmp / "new-client", env.tmp / "new-client.git"
        repo.git("init", "-q", "--bare", "-b", "main", str(remote))
        repo.git("init", "-q", "-b", "main", str(path))
        repo.git("remote", "add", "origin", str(remote), cwd=path)
        env.gh.respond("api", stdout="{}")
        initialized = repo.forge("init", cwd=path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        checkout = env.tmp / "new-checkout"
        repo.git("clone", "-q", str(remote), str(checkout))
        repo.path = checkout
    else:
        made = repo.forge("fix", "start", "Upgrade client", "--done", "The client uses this release")
        assert made.returncode == 0, made.stdout + made.stderr
        upgrade = worktree(repo, "fix/upgrade-client")
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", upgrade,
                        dirs_exist_ok=True)
        repo.git("add", "-A", cwd=upgrade)
        repo.git("commit", "-qm", "Client adopted on the earlier release", cwd=upgrade)
        config = upgrade / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        config.write_text(config.read_text("utf-8").replace('version = "v1.2.2"',
                          f'version = "{version}"').replace('workers = "codex"',
                          'workers = "claude"'), "utf-8")
        synced = repo.forge("sync", cwd=upgrade)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        repo.git("add", "-A", cwd=upgrade)
        repo.git("commit", "-qm", "Upgrade the earlier adopted client", cwd=upgrade)
        checkout = env.tmp / "upgraded-checkout"
        remote = repo.git("remote", "get-url", "origin")
        repo.git("clone", "-q", "--branch", "fix/upgrade-client", str(repo.path), str(checkout))
        repo.git("remote", "set-url", "origin", remote, cwd=checkout)
        repo.git("switch", "-qc", "main", cwd=checkout)
        repo.path = checkout
        repo.git("push", "-q", "origin", "main")
        repo.git("fetch", "-q", "origin")
        repo.git("remote", "set-head", "origin", "main")
    version = repo.forge("--version").stdout.split()[-1]
    env.commit(repo.path, "forge.toml", f'version = "{version}"\nworkers = "claude"\n'
               'models.build = { model = "opus", effort = "high" }\n')
    repo.git("push", "-q", "origin", "main")
    machine_cores(repo, 2)
    return repo


def lanes(repo):
    result = repo.forge("lanes", "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("history", ["new", "earlier"])
@pytest.mark.parametrize("kind", ["agents", "tests"])
def test_waiting_run_keeps_its_place_across_timezone_and_locale(
        env, tmp_path, monkeypatch, release_server, history, kind):
    repo = client(env, history)
    server, connections = release_server
    processes = []
    if kind == "agents":
        hold_agents(env)
        first, first_name = make_work(repo, "First typo")
        second, second_name = make_work(repo, "Second typo")
    else:
        configure(env, server)
    try:
        with monkeypatch.context() as launch:
            environment(launch, "Asia/Kolkata", "en_US.UTF-8")
            active, active_output = start(repo.path, tmp_path / "active", repo,
                                          *(('work', first) if kind == "agents" else ('test',)))
            processes.append(active)
            if kind == "agents":
                _until(lambda: (repo.bin / f"started-{first_name}").exists(), "the first model")
            else:
                accepted(server, connections, repo.path, active, active_output)
            waiter, output = start(repo.path, tmp_path / "waiter", repo,
                                    *(('work', second) if kind == "agents" else ('test',)))
            processes.append(waiter)
            _until(lambda: "in line." in output.read_text("utf-8"), "the waiting admission")
            before = lanes(repo)[kind]["entries"]
        assert len(before) == 2 and before[1]["started_at"] is None
        environment(monkeypatch, "UTC", "C")
        after = lanes(repo)[kind]["entries"]
        assert [(r["id"], r["joined_at"], r["started_at"]) for r in after] == [
            (r["id"], r["joined_at"], r["started_at"]) for r in before]
        assert waiter.poll() is None, output.read_text("utf-8")
        if kind == "agents":
            (repo.bin / f"go-{first_name}").touch()
            assert active.wait(timeout=30) == 0, active_output.read_text("utf-8")
            _until(lambda: (repo.bin / f"started-{second_name}").exists(), "the waiting model to start")
            (repo.bin / f"go-{second_name}").touch()
        else:
            connections[0].sendall(b"x")
            assert active.wait(timeout=30) == 0, active_output.read_text("utf-8")
            connection, _ = accepted(server, connections, repo.path, waiter, output)
            connection.sendall(b"x")
        assert waiter.wait(timeout=30) == 0, output.read_text("utf-8")
        assert lanes(repo)[kind]["entries"] == []
    finally:
        if kind == "agents":
            finish(repo, processes)
        else:
            reap(processes, server, connections)


@pytest.mark.parametrize("legacy", [None, "en_US.UTF-8",
    pytest.param("ko_KR.UTF-8", marks=pytest.mark.skipif(
        sys.platform != "darwin", reason="Apple ps locale output requires macOS"))],
                         ids=["canonical-stop", "previous-release", "previous-release-ko"])
def test_stop_verifies_the_same_identity_and_preserves_unverifiable_old_runs(
        env, tmp_path, monkeypatch, release_server, legacy):
    repo = client(env, "new")
    server, connections = release_server
    configure(env, server)
    processes = []
    try:
        environment(monkeypatch, "Asia/Kolkata", legacy or "en_US.UTF-8")
        active, output = start(repo.path, tmp_path / "active", repo, "test")
        processes.append(active)
        connection, observed = accepted(server, connections, repo.path, active, output)
        entry = lanes(repo)["tests"]["entries"][0]
        if legacy:
            # Previous releases persisted unqualified local ps text. Build that
            # record from the actual running process, rather than faking liveness.
            ps = subprocess.run(["ps", "-ww", "-o", "lstart=,command=", "-p", str(observed["pid"])],
                                check=True, capture_output=True, text=True)
            *start_text, command = ps.stdout.split(None, 5)
            started = " ".join(start_text)
            if legacy == "ko_KR.UTF-8":
                assert ":" not in started, "Korean lstart must exercise a time without colons"
            queue = Path(os.environ["XDG_CONFIG_HOME"]) / "forge/agent-runs.json"
            saved = json.loads(queue.read_text("utf-8"))
            saved[0]["process"].update(started=started, command=command.strip())
            queue.write_text(json.dumps(saved), "utf-8")
        environment(monkeypatch, "UTC", "C")
        retained = lanes(repo)["tests"]["entries"]
        assert len(retained) == 1 and retained[0]["id"] == entry["id"]
        # This disposable client's command represents its person, not this worker.
        stopped = repo.forge("stop", "--id", entry["id"])
        if legacy:
            assert stopped.returncode == 1
            assert "Forge cannot verify this run's process; nothing was stopped." in stopped.stderr
            assert active.poll() is None
            assert lanes(repo)["tests"]["entries"][0]["id"] == entry["id"]
            connection.sendall(b"x")
            assert active.wait(timeout=30) == 0, output.read_text("utf-8")
        else:
            assert stopped.returncode == 0, stopped.stderr
            active.wait(timeout=30)
            assert subprocess.run(["ps", "-p", str(observed["pid"])], capture_output=True).returncode == 1
        assert lanes(repo)["tests"]["entries"] == []
    finally:
        reap(processes, server, connections)
