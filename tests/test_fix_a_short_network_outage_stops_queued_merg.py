"""A queued change that meets a short network outage waits, starts again and merges."""
import shutil
import sys

import pytest

from conftest import _install
from test_close import env  # noqa: F401
from test_queue_land_all import _all, _fix, client  # noqa: F401

STORY = "FIX-A-SHORT-NETWORK-OUTAGE-STOPS-QUEUED-MERG"
WAIT = 1.5

# Git: the first fetch of main fails with a DNS error; the clock times of both fetches go to a file.
GIT = '''#!{python}
import pathlib, subprocess, sys, time
log = pathlib.Path({log!r})
if sys.argv[1:] == ["fetch", "-q", "origin", "main"]:
    first = not log.exists()
    with log.open("a") as out:
        out.write(str(time.time()) + "\\n")
    if first:
        sys.stderr.write("fatal: unable to access 'https://github.com/x/y/': Could not resolve host: github.com\\n")
        sys.exit(1)
sys.exit(subprocess.call([{real!r}, *sys.argv[1:]]))
'''

# gh: after the pull request exists, its first four list calls fail with gh's own DNS message, more than the read retries make.
GH = '''#!{python}
import pathlib, subprocess, sys
done = pathlib.Path({done!r})
created = done.with_name("created")
if sys.argv[1:3] == ["pr", "create"]:
    created.write_text("1")
seen = int(done.read_text()) if done.exists() else 0
if sys.argv[1:3] == ["pr", "list"] and seen < 4 and created.exists():
    done.write_text(str(seen + 1))
    sys.stderr.write("error connecting to api.github.com\\ncheck your internet connection\\n")
    sys.exit(1)
sys.exit(subprocess.call([{real!r}, *sys.argv[1:]]))
'''


@pytest.mark.parametrize("client", ["new"], indirect=True)
def test_1_a_change_that_meets_a_network_outage_waits_starts_again_and_merges(client, monkeypatch):
    env = client
    _fix(env, monkeypatch, "aa", 1, {"aa.py": "print('aa')\n"})
    monkeypatch.setenv("FORGE_NETWORK_RETRY_WAIT", str(WAIT))
    log = env.tmp / "fetches.txt"
    gh = env.repo.bin / "gh"
    real = env.repo.bin / "gh-real"
    shutil.copyfile(gh, real)
    real.chmod(0o755)
    _install(env.repo.bin, "gh", GH.format(python=sys.executable, done=(env.tmp / "gh-done").as_posix(),
                                           real=real.as_posix()))
    _install(env.repo.bin, "git", GIT.format(python=sys.executable, log=log.as_posix(),
                                              real=shutil.which("git")))
    done = _all(env)
    lines = done.stdout.splitlines()
    text = done.stdout + done.stderr
    assert done.returncode == 0 and "aa merged." in lines, text
    assert "aa met a short network problem; starting it again." in lines, text
    first, second = map(float, log.read_text().split()[:2])
    assert second - first >= WAIT, text
    assert (env.tmp / "gh-done").read_text() == "4", text
