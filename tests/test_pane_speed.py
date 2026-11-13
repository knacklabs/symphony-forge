"""The pane's one read of Forge, `forge lanes --json`, stays fast, small and cheap for the processor.

Real commands in a repo with finished work, fix worktrees, other remembered repos and held builds.
Time and processor use come from the operating system, not from a stand-in.
"""
import json
import os
import time
from pathlib import Path

import pytest

from test_close import env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _until
from test_lanes_agents import finish, hold_agents, make_work, start
from test_machine_views_recent_finished_items import finished_fix, landed
from test_machine_views_stay_fast import progress
from test_pane_data import client

try:
    import resource
except ImportError:  # Windows has no resource module: its processor time is not measured
    resource = None

pytestmark = pytest.mark.platform

STORY = "FORGE-PANE-1"


def remembered(env, tmp_path, count):
    """Other Forge repos on this laptop, each with a fix worktree, in the registry that init and next fill."""
    registry = Path(os.environ["APPDATA" if os.name == "nt" else "XDG_CONFIG_HOME"]) / "forge" / "repos"
    registry.parent.mkdir(parents=True, exist_ok=True)
    for number in range(count):
        other = tmp_path / f"other-{number}"
        other.mkdir()
        env.repo.git("init", "-q", "-b", "main", str(other))
        (other / "forge.toml").write_text('version = "v1.0.0"\n', "utf-8")
        env.repo.git("add", "-A", cwd=other)
        env.repo.git("commit", "-qm", "Use Forge", cwd=other)
        env.repo.git("worktree", "add", "-qb", "fix/other", str(tmp_path / f"other-wt-{number}"), cwd=other)
        with registry.open("a", encoding="utf-8") as out:
            out.write(f"{other}\n")


def read_lanes(repo):
    """The fastest of three runs, with its size and the processor time of one run."""
    runs = []
    for _ in range(3):
        before = resource and resource.getrusage(resource.RUSAGE_CHILDREN)
        start_time = time.perf_counter()
        done = repo.forge("lanes", "--json")
        seconds = time.perf_counter() - start_time
        after = resource and resource.getrusage(resource.RUSAGE_CHILDREN)
        assert done.returncode == 0, done.stderr
        runs.append((seconds, len(done.stdout.encode("utf-8")),
                     after and after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime, done.stdout))
    return min(runs, key=lambda run: run[0])


@pytest.mark.parametrize("previous", [False, True], ids=["new", "earlier adopted"])
@pytest.mark.parametrize("case", ["new", "over 1,000 rows"])
def test_4_forge_answers_the_pane_fast_small_and_cheap(env, tmp_path, monkeypatch, case, previous):
    repo = env.repo
    client(env, previous)  # also remembers this repo, so its worktrees are scanned
    processes = []
    if case != "new":
        landed(repo, monkeypatch, "2026-11-12T12:00:00+00:00",
               {f".factory/fixes/done-{n}.json": finished_fix(f"done-{n}") for n in range(1000)})
        progress(repo, tmp_path, [f"busy-{n}" for n in range(50)])
        remembered(env, tmp_path, 10)
        # One of the 50 active worktrees holds a stop that waits for the owner: the scan must reach it.
        stopped = tmp_path / "wt-busy-7/.factory/fixes/busy-7.json"
        stopped.write_text(json.dumps({**finished_fix("busy-7"), "status": "hotspot",
                                       "stop": {"question": "Choose how to go on.", "tool": "claude"}}), "utf-8")
        hold_agents(env)
        for number in range(4):
            item, name = make_work(repo, f"Held build {number}")
            process, _ = start(repo.path, tmp_path / f"run-{number}", repo, "work", item)
            processes.append(process)
            _until(lambda name=name: (repo.bin / f"started-{name}").exists(), "a held build")
    try:
        seconds, size, cpu, out = read_lanes(repo)
        data = json.loads(out)
        assert [row["title"] for row in data["needs_you"]] == (
            ["Finished fix busy-7"] if case != "new" else [])
        assert data["busy"] is False
        assert len(data["agents"]["entries"]) == len(processes)
        assert seconds < 0.3, f"one read took {seconds:.2f} seconds"
        assert size < 20_000, f"one read printed {size} bytes"
        # One read every 3 seconds for 10 minutes: under 10% of one core means under 0.3 s a read.
        assert cpu is None or cpu < 0.3, f"one read used {cpu:.2f} seconds of processor time"
    finally:
        finish(repo, processes)
