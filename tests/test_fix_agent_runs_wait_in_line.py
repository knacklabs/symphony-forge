"""At most two Forge agent runs go at once on one machine, whatever the repo and whatever the run: a
forge work round, a plan read or a close review. The rest wait in line and say their place."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from conftest import Repo, _install
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


def _start(where: Path, tmp_path: Path, *args: str) -> tuple[subprocess.Popen, Path]:
    out = tmp_path / f"{args[0]}.out"
    with out.open("w", encoding="utf-8") as sink:
        run = subprocess.Popen([sys.executable, str(tmp_path / "bin" / "forge"), *args], cwd=where,
                               stdin=subprocess.DEVNULL, stdout=sink, stderr=subprocess.STDOUT)
    return run, out


def _until(check, what: str) -> None:
    """Wait for real state: a stub agent's marker or a run's output."""
    deadline = time.monotonic() + 60
    while not check():
        assert time.monotonic() < deadline, f"timed out waiting for {what}"
        time.sleep(0.05)


def test_1_a_third_run_from_another_repo_waits_until_one_of_two_ends_then_runs(env, tmp_path):
    bin_dir = env.repo.bin
    _install(bin_dir, "claude", HOLDING_CLAUDE.format(python=sys.executable))
    helper = Path(os.environ["AUTOREVIEW"])
    real = helper.with_name("autoreview-real")
    helper.rename(real)
    helper.write_text(HOLDING_AUTOREVIEW.format(bin=str(bin_dir), real=str(real)), encoding="utf-8")
    started = lambda name: (bin_dir / f"started-{name}").exists()  # noqa: E731
    running = lambda: len(list(bin_dir.glob("started-*"))) - len(list(bin_dir.glob("go-*")))  # noqa: E731

    # This repo: a fix for forge work, and another with work done, for close. The other repo: a
    # story doc for forge read.
    fix = env.repo.forge("fix", "start", "Fix the login typo", "--done", "The login page says Log in")
    assert fix.returncode == 0, fix.stderr
    work_folder = worktree(env.repo, "fix/fix-the-login-typo").name
    closing, _ = env.start_fix()
    other = _other_repo(tmp_path, bin_dir)
    read_folder = worktree(other, "story/SHOP").name

    work, _ = _start(env.repo.path, tmp_path, "work", "fix-the-login-typo")
    _until(lambda: started(work_folder), "the work round's agent to start")
    read, _ = _start(other.path, tmp_path, "read", "SHOP")
    _until(lambda: started(read_folder), "the plan read's agent to start")
    review, out = _start(env.repo.path, tmp_path, "close", closing)
    _until(lambda: WAITING in out.read_text("utf-8"), "the close review to say its place")

    # Two agents run, from two repos; the review waits, says its place once and starts no agent.
    assert running() == 2 and not started("review") and review.poll() is None

    (bin_dir / f"go-{work_folder}").touch()
    assert work.wait(timeout=60) == 0
    _until(lambda: started("review"), "the close review's agent to start")
    assert running() == 2
    for name, run in ((read_folder, read), ("review", review)):
        (bin_dir / f"go-{name}").touch()
        assert run.wait(timeout=60) == 0, Path(tmp_path / f"{run.args[2]}.out").read_text("utf-8")
    assert out.read_text("utf-8").count("in line.") == 1
