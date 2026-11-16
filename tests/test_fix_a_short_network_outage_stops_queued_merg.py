"""A change whose fetch meets a short network outage starts again and merges."""
import shutil
import sys

from conftest import _install
from test_close import env  # noqa: F401
from test_queue_land_all import _all, _fix, client  # noqa: F401

STORY = "FIX-A-SHORT-NETWORK-OUTAGE-STOPS-QUEUED-MERG"

# Git, but the first fetch of main fails with a DNS error.
GIT = '''#!{python}
import pathlib, subprocess, sys
count = pathlib.Path({count!r})
if sys.argv[1:] == ["fetch", "-q", "origin", "main"] and not count.exists():
    count.write_text("1")
    sys.stderr.write("fatal: unable to access 'https://github.com/x/y/': Could not resolve host: github.com\\n")
    sys.exit(1)
sys.exit(subprocess.call([{real!r}, *sys.argv[1:]]))
'''


def test_1_a_change_that_meets_a_network_outage_starts_again_and_merges(client, monkeypatch):
    env = client
    _fix(env, monkeypatch, "aa", 1, {"aa.py": "print('aa')\n"})
    _install(env.repo.bin, "git", GIT.format(python=sys.executable, count=(env.tmp / "dns.txt").as_posix(),
                                              real=shutil.which("git")))
    done = _all(env)
    lines = done.stdout.splitlines()
    text = done.stdout + done.stderr
    assert done.returncode == 0 and "aa merged." in lines, text
    assert "aa met a short network problem; starting it again." in lines, text
