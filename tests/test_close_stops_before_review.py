"""Close merges before either check and keeps failing output for the next worker round."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from conftest import patient

from test_close import CLEAN, GREEN, env  # noqa: F401
from test_land import ITEM, RUNS, _agent, _fix, _land, _queue, _runs, _steps, _workers, land  # noqa: F401

STORY = "FIX-CLOSE-SPENDS-A-FULL-REVIEW-ABOUT-15-MINU"

# The repo's test command: it logs each run, and fails until a worker round has committed a file.
SUITE = '''import pathlib, sys
with pathlib.Path({log!r}).open("a") as log:
    log.write("run\\n")
if not pathlib.Path("work-1.txt").exists():
    print("test_readme.py::test_greeting FAILED")
    print("AssertionError: the readme has no greeting")
    sys.exit(1)
print("1 passed")
'''


def _with_test_command(env) -> Path:
    log, script = env.tmp / "runs.log", env.tmp / "suite.py"
    script.write_text(SUITE.format(log=str(log)), "utf-8")
    toml = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", toml.read_text("utf-8")
               + f"test = {f'{sys.executable} {script}'!r}\n".replace("'", '"'))
    env.repo.git("push", "-q", "origin", "main")
    return log


# Hold the shared lane through its real command, replacing the old ticket-file lock fixture.
HOLD = '''import pathlib, time
tmp = pathlib.Path({tmp!r})
(tmp / "held").touch()
while not (tmp / "release").exists():
    time.sleep(0.05)
'''


def test_1_a_conflicting_merge_stops_before_the_test_lock_any_test_run_or_review(env):
    log = _with_test_command(env)
    script = env.tmp / "suite.py"
    script.write_text(HOLD.format(tmp=env.tmp.as_posix()), "utf-8")
    # A code change too: a Markdown-only change skips the test command, lock and all.
    item, _ = env.start_fix({"README.md": "# Hello, shoppers\n", "app.py": "print('hello')\n"})
    env.commit(env.repo.path, "README.md", "# Welcome\n")
    env.repo.git("push", "-q", "origin", "main")
    holder = subprocess.Popen([sys.executable, str(env.repo.bin / "forge"), "test"],
                              cwd=env.repo.path, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 30
        while not (env.tmp / "held").exists():
            assert time.monotonic() < deadline and holder.poll() is None
            time.sleep(0.05)
        done = env.close(item)  # it would wait out the test's timeout if it took the lock
    finally:
        patient(lambda: (env.tmp / "release").touch())
        out, err = holder.communicate(timeout=30)
        assert holder.returncode == 0, out + err
    assert done.returncode == 1, done.stdout + done.stderr
    assert "Merging main into fix/tidy-readme conflicts in README.md." in done.stderr
    assert not log.exists()
    assert env.review_calls() == []
    assert "waits its turn" not in done.stdout


def test_2_a_failing_test_command_blocks_the_round_and_the_worker_gets_its_output(land):
    env = land
    log = _with_test_command(env)
    item, where = env.start_fix()
    done = env.close(item)
    assert done.returncode == 1, done.stdout + done.stderr
    command = f"{sys.executable} {env.tmp / 'suite.py'}"
    assert done.stderr.splitlines()[-2:] == [
        f"`{command}` failed on this machine; the next worker round gets its output.",
        f"Next: forge work {item}"]
    # Review now overlaps tests, even when they fail; the failed output still reaches work.
    assert len(env.review_calls()) == 1
    assert log.read_text("utf-8").splitlines() == ["run"]
    record = json.loads((where / f".factory/fixes/{item}.json").read_text("utf-8"))
    assert record["status"] == "fixing"
    assert "AssertionError: the readme has no greeting" in record["tests"]
    assert env.repo.git("status", "--porcelain", cwd=where) == ""  # the record is committed

    worked = env.repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    [worker] = _workers(env)
    assert "### Tests on the close run" in worker["brief"]
    assert "AssertionError: the readme has no greeting" in worker["brief"]


def test_3_land_reviews_each_changed_round_and_fixes_failing_tests(land):
    env = land
    log = _with_test_command(env)
    _agent(env)
    _fix(env, "working", worked=True)
    _queue(env, RUNS, *_runs(GREEN))
    env.reviews(CLEAN)
    done = _land(env)
    assert done.returncode == 0, done.stdout + done.stderr
    assert _steps(done) == [f"Closing {ITEM}.", "Fix round 1 of 3: the worker fixes the failing tests.",
                            f"Closing {ITEM}.", f"Merging {ITEM}."]
    assert log.read_text("utf-8").splitlines() == ["run", "run"]
    # Both rounds review their own changed head, rather than waiting for passing tests.
    assert len(env.review_calls()) == 2
    assert "1 passed" in done.stdout
