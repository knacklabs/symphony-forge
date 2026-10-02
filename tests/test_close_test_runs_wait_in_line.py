"""forge close's test runs on one machine go first come, first served, and a waiting close says
its place in line when it starts waiting and each time the place changes. A close that dies
while waiting leaves no place behind."""
from __future__ import annotations

import re
import subprocess
import time

from test_close import env  # noqa: F401
from test_fix_close_reruns_the_full_test_command_even import _close, _runs, _with_test_command

STORY = "FIX-ABOUT-TWENTY-CLOSES-SHARE-THE-MACHINE-S"

PLACE = re.compile(r"^Waiting for (\d+) other close(?:'s test run|s' test runs) on this machine\.$")


def _fix(env, name: str) -> str:
    item, _ = env.start(name, f"fix/{name}", f".factory/fixes/{name}.json",
                        {"kind": "fix", "why": name, "done_when": f"{name} is done"},
                        {f"{name}.py": "x = 1\n"})
    return item


def _holding(env) -> subprocess.Popen[str]:
    """A close inside its test run, which holds until the test touches the release file."""
    log = _with_test_command(env)
    (env.tmp / "gated").touch()
    held = _close(env, _fix(env, "held"))
    deadline = time.monotonic() + 30
    while _runs(log) != ["start fix-held"]:
        assert time.monotonic() < deadline and held.poll() is None, held.communicate()
        time.sleep(0.05)
    return held


def _until(close: subprocess.Popen[str], line: str) -> str:
    """What the close printed, read up to and including `line`."""
    said = ""
    while not said.endswith(line + "\n"):
        got = close.stdout.readline()
        assert got, (said, close.communicate())
        said += got
    return said


def _places(said: str) -> list[int]:
    return [int(m.group(1)) for line in said.splitlines() if (m := PLACE.match(line))]


def test_1_waiting_closes_run_their_tests_in_arrival_order_and_say_their_places(env):
    held = _holding(env)
    waiting, said = [], []
    for n, name in enumerate(["first", "second", "third"], 1):
        item = _fix(env, name)
        close = _close(env, item)
        noun = "close's test run" if n == 1 else "closes' test runs"
        said.append(_until(close, f"Waiting for {n} other {noun} on this machine."))
        waiting.append(close)
    assert _runs(env.tmp / "runs.log") == ["start fix-held"]
    (env.tmp / "release").touch()
    outs = [close.communicate(timeout=120) for close in [held, *waiting]]
    assert all(close.returncode == 0 for close in [held, *waiting]), outs
    assert _runs(env.tmp / "runs.log") == ["start fix-held", "end", "start fix-first", "end",
                                           "start fix-second", "end", "start fix-third", "end"]
    assert _places(outs[0][0]) == []
    for n, (before, (after, _)) in enumerate(zip(said, outs[1:]), 1):
        places = _places(before + after)
        assert places[0] == n and places == sorted(set(places), reverse=True), places


def test_2_a_close_that_dies_while_waiting_leaves_no_place(env):
    held = _holding(env)
    dies = _close(env, _fix(env, "dies"))
    _until(dies, "Waiting for 1 other close's test run on this machine.")
    lives = _close(env, _fix(env, "lives"))
    _until(lives, "Waiting for 2 other closes' test runs on this machine.")
    dies.kill()
    dies.communicate(timeout=30)
    _until(lives, "Waiting for 1 other close's test run on this machine.")
    (env.tmp / "release").touch()
    outs = [close.communicate(timeout=120) for close in (held, lives)]
    assert held.returncode == 0 and lives.returncode == 0, outs
    assert _runs(env.tmp / "runs.log") == ["start fix-held", "end", "start fix-lives", "end"]
