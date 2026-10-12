"""A reused agent process id does not drop a run whose Forge process still runs."""
import json
import os
from pathlib import Path

from conftest import machine_cores
from test_close import env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _until
from test_lanes_agents import finish, hold_agents, make_work, start, person  # noqa: F401
from test_story import worktree

STORY = "pid-reuse-keeps-run"


def test_1_a_reused_agent_pid_keeps_the_run_while_forge_runs(env, tmp_path, person):
    repo = env.repo
    machine_cores(repo, 2)
    item, name = make_work(repo, "First typo")
    hold_agents(env)
    # A dirty first turn makes the same work round start a second agent, the commit nudge.
    stub = repo.bin / "claude"
    stub.write_text(stub.read_text("utf-8").replace(
        'name = pathlib.Path.cwd().name',
        'name = pathlib.Path.cwd().name\n'
        f'if name == {name!r} and (here / "first-ended").exists():\n'
        '    name += "-nudge"').replace(
        'print("No findings.")',
        f'if name == {name!r}:\n'
        f'    pathlib.Path({str(worktree(repo, "fix/" + item) / "dirty.txt")!r}).write_text("needs committing")\n'
        '    (here / "first-ended").touch()\n'
        'print("No findings.")'), "utf-8")
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
