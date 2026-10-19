"""Stop releases an abandoned session lock without signalling its surviving host.

The real command creates the lock. Dropping the machine entry models a stopped
round whose coordinator stays open, which existing queued-stop tests cannot reach.
"""
import json
import os
import shutil
from pathlib import Path

import pytest

from conftest import ROOT
from test_conflicting_pull_requests_stop_check_waits import _publish_default
from test_close import env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _until
from test_lanes_agents import finish, hold_agents, make_work, person, start  # noqa: F401
from test_setup import _fresh_client
from test_tools_session_hold import Session

STORY = "FIX-STOP-CLEARS-LOCK"


@pytest.mark.parametrize("history", ["new", "adopted"])
@pytest.mark.parametrize("identity", ["session", "reused", "unverified"])
def test_1_stop_releases_an_item_whose_run_ended(repo, gh, monkeypatch, tmp_path, person, history, identity):
    if history == "new":
        folder, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
        repo.path = folder
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    version = repo.forge("--version").stdout.split()[-1]
    repo.git("switch", "-qc", "fix/settings")
    repo.write("forge.toml", f'version = "{version}"\nrepo = "client"\n'
                             'tools = "codex"\nworkers = "codex"\ntest = "pytest -q"\n')
    repo.write(".factory/fixes/settings.json", json.dumps({
        "kind": "fix", "branch": "fix/settings", "status": "working",
        "why": "Choose the tools", "done_when": "The client uses Codex"}))
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Set the client tools")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/settings")
    _publish_default(repo, repo.git("remote", "get-url", "origin"))
    item, name = make_work(repo, "Repair the typo")
    checkout = repo.path.parent / name
    home = tmp_path / "trusted-home"
    home.mkdir()
    (home / "config.toml").write_text(
        f'[projects.{json.dumps(str(checkout))}]\ntrust_level = "trusted"\n', "utf-8")
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("CODEX_THREAD_ID", "coordinator")
    host = Session(repo, tmp_path / "host", "codex-session")
    try:
        first = host.forge("work", item)
        assert first.returncode == 0, first.stdout + first.stderr
        lock = repo.path / ".git/forge/threads/fix" / (item + ".lock")
        owner = json.loads(lock.read_text("utf-8"))
        assert owner["pid"] == host.pid, "the session, rather than the finished command, owns the lock"
        assert owner["started"]
        busy = host.forge("work", item)
        assert busy.returncode == 1 and "already running" in busy.stderr
        # Fault injection: the run is gone but its session and item lock survive.
        queue = Path(os.environ["APPDATA" if os.name == "nt" else "XDG_CONFIG_HOME"]) / "forge/agent-runs.json"
        queue.write_text("[]", "utf-8")
        if identity == "unverified":
            lock.write_text(json.dumps({"pid": host.pid}), "utf-8")
            refused = host.forge("stop", item)
            assert refused.returncode == 1
            # Session reads text with universal newlines, including Windows refusals.
            assert refused.stderr == "Forge cannot verify this run's process; nothing was stopped.\n"
            assert lock.exists()
            lock.write_text(json.dumps(owner), "utf-8")
        elif identity == "reused":
            lock.write_text(json.dumps({**owner, "started": "another process's start"}), "utf-8")
        stopped = host.forge("stop", item)
        assert stopped.returncode == 0, stopped.stdout + stopped.stderr
        assert not lock.exists(), stopped.stdout
        assert "There is nothing to stop." not in stopped.stdout
        assert host.forge("--version").returncode == 0, "stop must preserve the coordinator"
        again = host.forge("work", item)
        assert again.returncode == 0, again.stdout + again.stderr
        assert "Start a new fixer subagent" in again.stdout
        assert host.forge("stop", item).returncode == 0
    finally:
        host.close()


def test_2_stop_keeps_a_live_older_work_lock_without_a_queue_entry(env, tmp_path, person):
    repo = env.repo
    item, name = make_work(repo, "Correct the words")
    hold_agents(env)
    process, _ = start(repo.path, tmp_path / "run", repo, "work", item)
    try:
        _until(lambda: (repo.bin / f"started-{name}").exists(), "the launched worker")
        lock = repo.path / ".git/forge/threads/fix" / (item + ".lock")
        owner = json.loads(lock.read_text("utf-8"))
        # Earlier releases have no saves_chat flag. The real work process is still live.
        owner.pop("saves_chat", None)
        lock.write_text(json.dumps(owner), "utf-8")
        queue = Path(os.environ["APPDATA" if os.name == "nt" else "XDG_CONFIG_HOME"]) / "forge/agent-runs.json"
        queue.write_text("[]", "utf-8")
        stopped = repo.forge("stop", item)
        assert stopped.returncode == 0, stopped.stdout + stopped.stderr
        assert lock.exists(), "a live work command still owns the item"
        busy = repo.forge("work", item)
        assert busy.returncode == 1 and "already running" in busy.stderr
        assert process.poll() is None
    finally:
        finish(repo, [process])


def test_3_stop_handles_a_queued_run_before_its_abandoned_lock(env, tmp_path, person):
    repo = env.repo
    item, name = make_work(repo, "Correct the spelling")
    hold_agents(env)
    process, _ = start(repo.path, tmp_path / "run", repo, "work", item)
    try:
        _until(lambda: (repo.bin / f"started-{name}").exists(), "the launched worker")
        # As in the adopted-client lane test, the model outlives its Forge parent.
        process.kill()
        process.wait(timeout=30)
        lock = repo.path / ".git/forge/threads/fix" / (item + ".lock")
        owner = json.loads(lock.read_text("utf-8"))
        owner.pop("started")
        lock.write_text(json.dumps(owner), "utf-8")
        stopped = repo.forge("stop", "--repo", str(repo.path), item)
        assert stopped.returncode == 0, stopped.stdout + stopped.stderr
        assert stopped.stdout == "Stopped the run.\n"
    finally:
        finish(repo, [process])
