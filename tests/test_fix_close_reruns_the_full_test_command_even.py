"""forge close skips a test command that already passed on the same committed tree on this
machine, and a one-slot machine runs only one close test command at a time."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from conftest import Repo, machine_cores
from test_close import CLEAN, FAILED, Forge, env  # noqa: F401

STORY = "FIX-CLOSE-RERUNS-THE-FULL-TEST-COMMAND-EVEN"

# The repo's test command: it logs each run's start and end, and ends when the test lets it (or at
# once when there is no gate), exiting with the code in the exit file.
SUITE = '''import os, pathlib, sys, time
tmp = pathlib.Path({tmp!r})
with (tmp / "runs.log").open("a") as log:
    log.write("start " + os.path.basename(os.getcwd()) + "\\n")
gate, deadline = tmp / "release", time.monotonic() + 30
while (tmp / "gated").exists() and not gate.exists() and time.monotonic() < deadline:
    time.sleep(0.05)
with (tmp / "runs.log").open("a") as log:
    log.write("end\\n")
code = int((tmp / "exit").read_text()) if (tmp / "exit").exists() else 0
print("1 passed" if code == 0 else "1 failed")
sys.exit(code)
'''


def _with_test_command(env) -> Path:
    script = env.tmp / "suite.py"
    script.write_text(SUITE.format(tmp=str(env.tmp)), "utf-8")
    toml = env.repo.path / "forge.toml"
    command = f'"{Path(sys.executable).as_posix()}" "{script.as_posix()}"'
    env.commit(env.repo.path, "forge.toml", toml.read_text("utf-8")
               + "fast_test = " + json.dumps(command) + "\n")
    env.repo.git("push", "-q", "origin", "main")
    return env.tmp / "runs.log"


def _runs(log: Path) -> list[str]:
    return log.read_text("utf-8").splitlines() if log.exists() else []


def test_1_close_skips_a_test_command_that_passed_on_the_same_committed_tree(env):
    log = _with_test_command(env)
    item, _ = env.start_fix()
    env.reviews(FAILED, FAILED, CLEAN)  # the first close's review doesn't finish; nothing changes
    assert env.close(item).returncode != 0
    assert _runs(log) == ["start fix-tidy-readme", "end"]
    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    assert _runs(log) == ["start fix-tidy-readme", "end"]
    assert "already passed on this machine" in closed.stdout
    result = env.prompt().split("## Tests on the close run", 1)[1].split("\n## ", 1)[0]
    assert "already passed on this machine" in result


def test_2_close_reruns_a_test_command_that_failed_on_the_same_committed_tree(env):
    # A failing test command stops close before the review, so each close here stops on it.
    log = _with_test_command(env)
    (env.tmp / "exit").write_text("1", "utf-8")
    item, _ = env.start_fix()
    assert env.close(item).returncode != 0
    closed = env.close(item)
    assert closed.returncode != 0
    assert _runs(log) == ["start fix-tidy-readme", "end"] * 2
    assert "already passed" not in closed.stdout


def _close(env, item: str) -> subprocess.Popen[str]:
    return subprocess.Popen([sys.executable, str(env.repo.bin / "forge"), "close", item],
                            cwd=env.repo.path, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            stdin=subprocess.DEVNULL, text=True, encoding="utf-8")


def test_3_one_slot_machine_runs_only_one_close_test_command_at_a_time(env):
    # Four usable cores give one slot; larger-machine capacity has its own command test.
    machine_cores(env.repo, 4)
    log = _with_test_command(env)
    (env.tmp / "gated").touch()
    first, _ = env.start_fix()
    # The lane is machine-wide; independent repos also avoid concurrent pushes
    # rewriting the same Git config while another close reads it on Windows.
    other = env.tmp / "other repo"
    env.repo.git("clone", "-q", "--no-hardlinks", str(env.repo.path), str(other))
    env.repo.git("remote", "set-url", "origin", env.repo.git("remote", "get-url", "origin"),
                 cwd=other)
    other_env = Forge(Repo(other, env.repo.bin), env.gh, env.tmp)
    second, _ = other_env.start("other-fix", "fix/other-fix", ".factory/fixes/other-fix.json",
                                {"kind": "fix", "why": "Other", "done_when": "Other is done"},
                                {"other.py": "x = 2\n"})
    one = _close(env, first)
    deadline = time.monotonic() + 30
    while _runs(log) != ["start fix-tidy-readme"]:  # the first close is inside its test run
        assert time.monotonic() < deadline and one.poll() is None, one.communicate()
        time.sleep(0.05)
    two = _close(other_env, second)
    said = ""
    while "waits its turn: it is number 1 in line." not in said:  # the second close says it waits before its run starts
        line = two.stdout.readline()
        assert line, two.communicate()
        said += line
    assert _runs(log) == ["start fix-tidy-readme"]
    (env.tmp / "release").touch()
    out_one, out_two = one.communicate(timeout=60), two.communicate(timeout=60)
    assert one.returncode == 0 and two.returncode == 0, (out_one, out_two)
    assert _runs(log) == ["start fix-tidy-readme", "end", "start fix-other-fix", "end"]
    assert "waits its turn" not in out_one[0]


def test_4_a_repeat_close_that_keeps_its_green_review_says_the_tests_already_passed(env):
    log = _with_test_command(env)
    item, _ = env.start_fix()
    assert env.close(item).returncode == 0
    closed = env.close(item)  # nothing changed, so close keeps the review and its test run
    assert closed.returncode == 0, closed.stderr
    assert len(env.review_calls()) == 1
    assert _runs(log) == ["start fix-tidy-readme", "end"]
    assert "already passed on this machine" in closed.stdout


def test_5_close_runs_the_test_command_when_the_worktree_has_an_untracked_file(env):
    log = _with_test_command(env)
    item, where = env.start_fix()
    env.reviews(FAILED, FAILED, CLEAN)
    assert env.close(item).returncode != 0
    (where / "test_new_case.py").write_text("def test_new():\n    assert True\n", "utf-8")
    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    assert _runs(log) == ["start fix-tidy-readme", "end"] * 2
    assert "already passed" not in closed.stdout
