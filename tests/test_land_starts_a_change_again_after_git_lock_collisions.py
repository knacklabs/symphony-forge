"""A change whose fetch meets another change's git lock more than once still merges."""
import shutil
import sys

from conftest import _install
from test_close import env  # noqa: F401
from test_queue_land_all import _all, _fix, client  # noqa: F401

STORY = "FIX-TRAIN-TESTS-RUN-OUT-OF-TIME"

# Git, but the first two fetches of main fail, as two fetches of one branch at the same moment do.
GIT = '''#!{python}
import pathlib, subprocess, sys
count = pathlib.Path({count!r})
seen = int(count.read_text()) if count.exists() else 0
if sys.argv[1:] == ["fetch", "-q", "origin", "main"] and seen < 2:
    count.write_text(str(seen + 1))
    sys.stderr.write("error: cannot lock ref 'refs/remotes/origin/main': is at b2 but expected a1\\n")
    sys.exit(1)
sys.exit(subprocess.call([{real!r}, *sys.argv[1:]]))
'''


def test_1_a_change_that_meets_git_locks_twice_starts_again_and_merges(client, monkeypatch):
    env = client
    _fix(env, monkeypatch, "aa", 1, {"aa.py": "print('aa')\n"})
    count = env.tmp / "git-locks.txt"
    _install(env.repo.bin, "git", GIT.format(python=sys.executable, count=count.as_posix(),
                                              real=shutil.which("git")))
    done = _all(env)
    lines = done.stdout.splitlines()
    text = done.stdout + done.stderr
    assert done.returncode == 0 and "aa merged." in lines, text
    assert lines.count("aa met another change's git lock; starting it again.") == 2, text
    assert count.read_text() == "2", text
