"""Work rounds share the machine's agent places across repos; reads and reviews skip the line."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from conftest import Repo, machine_cores
from test_close import env  # noqa: F401 (pytest fixture)
from test_story import DOC, GRILL, worktree

STORY = "forge-runs-on-several-repos-at-once-can"
WAITING = ("2 Forge agents already run on this machine, so this one waits its turn: it is number 1 "
           "in line.")
# Each stub agent writes started-<name> beside it, then runs until go-<name> appears there; claude
# is named for its folder. claude answers like a reader with no findings, which a worker ignores.
HOLDING_CLAUDE = """#!{python}
import os, pathlib, sys, time
here = pathlib.Path(__file__).resolve().parent
sys.stdin.read()
if "--output-format" in sys.argv:  # like claude: stream-json ends with a result event of its answer
    import atexit, io, json
    sys.stdout, real = io.StringIO(), sys.stdout
    atexit.register(lambda: real.write(json.dumps({{"type": "result", "result": sys.stdout.getvalue().strip()}}) + "\\n"))
name = pathlib.Path.cwd().name
(here / f"started-{{name}}").touch()
while not (here / f"go-{{name}}").exists():
    time.sleep(0.05)
print("No findings.")
"""
# Autoreview, held the same way as "review", then the stub Autoreview the env fixture installed.
HOLDING_AUTOREVIEW = """import pathlib, runpy, sys, time
(pathlib.Path({bin!r}) / "started-review").touch()
while not (pathlib.Path({bin!r}) / "go-review").exists():
    time.sleep(0.05)
sys.argv[0] = {real!r}
runpy.run_path({real!r}, run_name="__main__")
"""


def _other_repo(tmp_path: Path, bin_dir: Path) -> Repo:
    """A second repo on Forge, with its own remote, and story SHOP's doc written for a read."""
    remote, path = tmp_path / "other.git", tmp_path / "other"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    other = Repo(path, bin_dir)
    version = other.forge("--version").stdout.split()[-1]
    other.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n{GRILL}')
    other.write("plans/roadmap.json", '{"items": [{"key": "SHOP"}]}')
    other.git("add", "-A")
    other.git("commit", "-q", "-m", "Set up Forge")
    other.git("remote", "add", "origin", str(remote))
    other.git("push", "-q", "-u", "origin", "main")
    other.git("remote", "set-head", "origin", "main")
    made = other.forge("story", "new", "SHOP", "Shoppers can save a basket")
    assert made.returncode == 0, made.stderr
    (worktree(other, "story/SHOP") / "plans" / "SHOP.md").write_text(DOC, encoding="utf-8")
    return other


def _until(check, what: str) -> None:
    """Wait for real state: a stub agent's marker or a run's output."""
    deadline = time.monotonic() + 60
    while not check():
        assert time.monotonic() < deadline, f"timed out waiting for {what}"
        time.sleep(0.05)


def test_1_a_third_work_round_from_another_repo_waits_while_reads_and_reviews_start(env, tmp_path):
    from test_lanes_agents import finish, hold_agents, make_work, start

    # The old fixed-two contract is now half of the reported four-core machine.
    machine_cores(env.repo, 4)
    bin_dir = env.repo.bin
    hold_agents(env)
    started = lambda name: (bin_dir / f"started-{name}").exists()  # noqa: E731
    running = lambda: len(list(bin_dir.glob("started-*"))) - len(list(bin_dir.glob("go-*")))  # noqa: E731

    # Previously the reader occupied a place and the review waited. Now two workers hold the
    # places, a third worker waits across repos, and both model-only operations still start.
    workers = [make_work(env.repo, name) for name in ("First typo", "Second typo")]
    closing, _ = env.start_fix()
    other = _other_repo(tmp_path, bin_dir)
    read_folder = worktree(other, "story/SHOP").name
    env.commit(other.path, "forge.toml", (other.path / "forge.toml").read_text("utf-8") +
               'workers = "claude"\n', "Use Claude workers")
    other.git("push", "-q", "origin", "main")
    third, third_name = make_work(other, "Third typo")
    processes = []
    try:
        for item, name in workers:
            process, _ = start(env.repo.path, tmp_path / item, env.repo, "work", item)
            processes.append(process)
            _until(lambda: started(name), "the work round's agent to start")
        waiting, out = start(other.path, tmp_path / "waiting", env.repo, "work", third)
        processes.append(waiting)
        _until(lambda: WAITING in out.read_text("utf-8"), "the third worker to say its place")
        for where, command, item, marker in ((other.path, "read", "SHOP", read_folder),
                                             (env.repo.path, "close", closing, "review")):
            process, output = start(where, tmp_path / command, env.repo, command, item)
            processes.append(process)
            _until(lambda: started(marker), f"the {command} agent to start")
            assert "in line." not in output.read_text("utf-8")
        assert running() == 4 and not started(third_name) and waiting.poll() is None
        (bin_dir / f"go-{workers[0][1]}").touch()
        assert processes[0].wait(timeout=60) == 0
        _until(lambda: started(third_name), "the third worker's agent to start")
        assert running() == 4
        assert out.read_text("utf-8").count("in line.") == 1
    finally:
        finish(env.repo, processes)
    assert all(process.returncode == 0 for process in processes)
