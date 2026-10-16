"""A reused agent process id does not drop a run whose Forge process still runs."""
import json
import os
import shutil
from pathlib import Path

import pytest

from conftest import ROOT, machine_cores
from test_close import env  # noqa: F401
from test_conflicting_pull_requests_stop_check_waits import _publish_default
from test_codex_worker import sdk_data  # noqa: F401
from test_fix_agent_runs_wait_in_line import _until
from test_lanes_agents import finish, hold_agents, make_work, start, person, lane_adapter  # noqa: F401
from test_setup import _fresh_client
from test_story import worktree

STORY = "pid-reuse-keeps-run"


@pytest.fixture(params=["new", "adopted"])
def client(env, lane_adapter, request):
    """A repo made by forge init, or one adopted on an earlier release, on this release's settings."""
    repo = env.repo
    config = (repo.path / "forge.toml").read_text(encoding="utf-8")
    if request.param == "new":
        path, made = _fresh_client(repo, env.gh, env.tmp)
        assert made.returncode == 0, made.stderr
        repo.path = path
        home = os.environ.get("CODEX_HOME")
        if home:
            with (Path(home) / "config.toml").open("a", encoding="utf-8") as trusted:
                trusted.write(f'\n[projects.{json.dumps(str(path))}]\ntrust_level = "trusted"\n')
        repo.git("switch", "-qc", "fix/upgrade-client")
    else:
        repo.git("switch", "-qc", "fix/upgrade-client")
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt the earlier release")
    repo.write(".factory/fixes/upgrade-client.json", json.dumps({
        "kind": "fix", "branch": "fix/upgrade-client", "status": "working",
        "why": "Refresh client guidance", "done_when": "Guidance uses this release"}))
    env.commit(repo.path, "forge.toml", config)
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Refresh client guidance", "--allow-empty")
    _publish_default(repo, Path(repo.git("remote", "get-url", "origin")).as_posix())
    repo.git("switch", "main")
    repo.git("merge", "-q", "--ff-only", "fix/upgrade-client")
    return lane_adapter


def test_1_a_reused_agent_pid_keeps_the_run_while_forge_runs(env, tmp_path, person, client):
    repo = env.repo
    machine_cores(repo, 2)
    item, name = make_work(repo, "First typo")
    hold_agents(env)
    # A dirty first turn makes the same work round start a second agent, the commit nudge.
    dirty = json.dumps((worktree(repo, "fix/" + item) / "dirty.txt").as_posix())
    for provider, indent, named, marker, path_type in (
            ("claude_agent_sdk/__init__.py", "    ", 'name = Path.cwd().name',
             '    yield AssistantMessage([TextBlock("SDK worker output")], options.model)', "Path"),
            ("codex-app-server", "            ", 'name = pathlib.Path(cwd).name',
             '            turns += 1', "pathlib.Path")):
        stub = repo.bin / provider
        stub.write_text(stub.read_text("utf-8").replace(named,
            f'{named}\n{indent}if name == {name!r} and (here / "first-ended").exists():\n'
            f'{indent}    name += "-nudge"').replace(marker,
            f'{indent}if name == {name!r}:\n'
            f'{indent}    {path_type}({dirty}).write_text("needs committing")\n'
            f'{indent}    (here / "first-ended").touch()\n' + marker), "utf-8")
    queue = Path(os.environ["APPDATA" if os.name == "nt" else "XDG_CONFIG_HOME"]) / "forge/agent-runs.json"

    def entries():
        board = repo.forge("board", "--json")
        assert board.returncode == 0, board.stderr
        return json.loads(board.stdout)["lanes"]["agents"]["entries"]

    process, output = start(repo.path, tmp_path, repo, "work", item)
    try:
        _until(lambda: (repo.bin / f"started-{name}").exists(), "the first agent")
        # The agent's pid now belongs to another live process: this test, with its own start time.
        runs = json.loads(queue.read_text("utf-8"))
        runs[0]["process"] = {"pid": os.getpid(), "started": "not this process's start", "command": "other"}
        queue.write_text(json.dumps(runs), "utf-8")
        assert [e["item"] for e in entries()] == [item]
        (repo.bin / f"go-{name}").touch()
        _until(lambda: (repo.bin / f"started-{name}-nudge").exists() or process.poll() is not None,
               "the commit nudge")
        assert process.poll() is None, output.read_text("utf-8")
        (repo.bin / f"go-{name}-nudge").touch()
        assert process.wait(timeout=30) == 0, output.read_text("utf-8")
        assert "This run was stopped" not in output.read_text("utf-8")
    finally:
        finish(repo, [process])
    # Once its Forge process has ended, the same record is dropped.
    queue.write_text(json.dumps(runs), "utf-8")
    assert entries() == []
