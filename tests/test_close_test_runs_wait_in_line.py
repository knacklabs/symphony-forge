"""forge close's test runs on one machine go first come, first served, and a waiting close says
its place in line when it starts waiting and each time the place changes. A close that dies
while waiting leaves no place behind."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import machine_cores
from test_close import env  # noqa: F401
from test_fix_close_reruns_the_full_test_command_even import _close, _runs

STORY = "FIX-ABOUT-TWENTY-CLOSES-SHARE-THE-MACHINE-S"

# The repo's test command: it logs each run's start and end, and ends when the test releases this
# checkout's run. A time limit must never advance the line before the waiters announce their
# places; pytest's timeout bounds a broken test instead.
SUITE = '''import os, pathlib, time
tmp, name = pathlib.Path({tmp!r}), os.path.basename(os.getcwd())
with (tmp / "runs.log").open("a") as log:
    log.write("start " + name + "\\n")
while not (tmp / ("release-" + name)).exists():
    time.sleep(0.05)
with (tmp / "runs.log").open("a") as log:
    log.write("end\\n")
print("1 passed")
'''


def _with_test_command(env) -> Path:
    # Queue ordering needs a one-place lane: four cores keep that contract while
    # eight cores now deliberately admit two test runs (covered by the capacity tests).
    machine_cores(env.repo, 4)
    script = env.tmp / "suite.py"
    script.write_text(SUITE.format(tmp=str(env.tmp)), "utf-8")
    toml = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", toml.read_text("utf-8")
               + f"fast_test = {f'{sys.executable} {script}'!r}\n".replace("'", '"'))
    env.repo.git("push", "-q", "origin", "main")
    return env.tmp / "runs.log"


def _fix(env, name: str) -> str:
    item, _ = env.start(name, f"fix/{name}", f".factory/fixes/{name}.json",
                        {"kind": "fix", "why": name, "done_when": f"{name} is done"},
                        {f"{name}.py": "x = 1\n"})
    return item


def _release(env, name: str) -> None:
    (env.tmp / f"release-fix-{name}").touch()


def _running(env, log: Path, *runs: str) -> None:
    """Wait until the run log reads `runs`: the last named close is inside its test run."""
    deadline = time.monotonic() + 60
    while _runs(log) != list(runs):
        assert time.monotonic() < deadline, _runs(log)
        time.sleep(0.05)


class Close:
    """A forge close running in the background, and what it has printed so far."""

    def __init__(self, env, name: str):
        self.process: subprocess.Popen[str] = _close(env, name)
        self.said = ""

    def until(self, line: str) -> None:
        while not self.said.endswith(line + "\n"):
            got = self.process.stdout.readline()
            assert got, (self.said, self.process.communicate())
            self.said += got

    def end(self) -> None:
        out, err = self.process.communicate(timeout=120)
        self.said += out
        if self.process.returncode != 0:
            pytest.fail(f"forge close exited {self.process.returncode}\n{self.said}\n{err}",
                        pytrace=False)

    def places(self) -> list[str]:
        # With four cores the review lane can also queue. This case owns the
        # test lane's FIFO messages, not admission to the separate agent lane.
        return [line for line in self.said.splitlines() if "Forge test runs" in line and "waits its turn" in line]


# Workers now share close's queue; the message counts places in the shared lane.
ONE = "1 Forge test runs already run on this machine, so this one waits its turn: it is number 1 in line."
TWO = "1 Forge test runs already run on this machine, so this one waits its turn: it is number 2 in line."
THREE = "1 Forge test runs already run on this machine, so this one waits its turn: it is number 3 in line."


def test_1_waiting_closes_run_their_tests_in_arrival_order_and_say_each_place(env):
    log = _with_test_command(env)
    # Prepare the worktrees before holding the line; their setup is not part of queue arrival.
    for name in ("held", "first", "second", "third"):
        _fix(env, name)
    held = Close(env, "held")
    _running(env, log, "start fix-held")
    first = Close(env, "first")
    first.until(ONE)
    second = Close(env, "second")
    second.until(TWO)
    third = Close(env, "third")
    third.until(THREE)
    _release(env, "held")
    second.until(ONE)
    third.until(TWO)
    _running(env, log, "start fix-held", "end", "start fix-first")
    _release(env, "first")
    third.until(ONE)
    _running(env, log, "start fix-held", "end", "start fix-first", "end", "start fix-second")
    _release(env, "second")
    _release(env, "third")
    for close in (held, first, second, third):
        close.end()
    assert _runs(log) == ["start fix-held", "end", "start fix-first", "end",
                          "start fix-second", "end", "start fix-third", "end"]
    assert held.places() == []
    assert first.places() == [ONE]
    assert second.places() == [TWO, ONE]
    assert third.places() == [THREE, TWO, ONE]


def test_2_a_close_that_dies_while_waiting_leaves_no_place(env):
    log = _with_test_command(env)
    for name in ("held", "dies", "lives"):
        _fix(env, name)
    held = Close(env, "held")
    _running(env, log, "start fix-held")
    dies = Close(env, "dies")
    dies.until(ONE)
    lives = Close(env, "lives")
    lives.until(TWO)
    dies.process.kill()
    dies.process.communicate(timeout=30)
    lives.until(ONE)
    _release(env, "held")
    _release(env, "lives")
    held.end()
    lives.end()
    assert _runs(log) == ["start fix-held", "end", "start fix-lives", "end"]
