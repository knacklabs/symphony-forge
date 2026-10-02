"""forge close's review removes its forge-review-* folder in the system temp folder however the
review ends, and first removes leftovers no running review owns."""
from __future__ import annotations

import os
import signal
import stat
import subprocess
import sys
import time

import pytest

from test_close import CLEAN, FAILED, env  # noqa: F401

STORY = "FIX-REVIEWS-LEAVE-THEIR-FORGE-REVIEW-TEMPORA"

# Answers as the stub Autoreview does, after what $REVIEW_DO says: "hang" records its id and
# waits to be stopped; "lock" leaves a folder in the review tree that nobody may write to.
HELPER = '''#!{python}
import os, subprocess, sys, time
do = os.environ.get("REVIEW_DO", "")
if do == "hang":
    with open(os.environ["AUTOREVIEW_STUB"] + ".hanging", "w", encoding="utf-8") as out:
        out.write(str(os.getpid()))
    time.sleep(600)
if do == "lock":
    os.makedirs("locked/inner")
    open("locked/inner/file", "w").close()
    os.chmod("locked/inner", 0o500)
    os.chmod("locked", 0o500)
sys.exit(subprocess.run([sys.executable, {stub!r}, *sys.argv[1:]]).returncode)
'''


@pytest.fixture
def temp(env, tmp_path, monkeypatch):
    """The system temp folder forge sees, empty, with the helper above in place."""
    folder = tmp_path / "systemp"
    folder.mkdir()
    monkeypatch.setenv("TMPDIR", str(folder))
    monkeypatch.setenv("TEMP", str(folder))
    monkeypatch.setenv("TMP", str(folder))
    helper = os.environ["AUTOREVIEW"]
    os.rename(helper, helper + "-stub")
    with open(helper, "w", encoding="utf-8") as out:
        out.write(HELPER.format(python=sys.executable, stub=helper + "-stub"))
    os.chmod(helper, os.stat(helper).st_mode | stat.S_IEXEC)
    return folder


def _leftovers(folder):
    return sorted(path.name for path in folder.iterdir() if path.name.startswith("forge-review-"))


def _hanging_close(env, item, monkeypatch):
    """forge close, started in its own process group and left once its review is running."""
    monkeypatch.setenv("REVIEW_DO", "hang")
    marker = env.tmp / "reviews.json.hanging"
    close = subprocess.Popen([sys.executable, str(env.repo.bin / "forge"), "close", item],
                             cwd=env.repo.path, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
    deadline = time.monotonic() + 60
    while not (marker.exists() and marker.read_text("utf-8")):
        assert close.poll() is None and time.monotonic() < deadline, "the review never started"
        time.sleep(0.05)
    monkeypatch.delenv("REVIEW_DO")
    return close, int(marker.read_text("utf-8"))


@pytest.mark.skipif(os.name == "nt", reason="Ctrl-C there reaches a console, not a process group")
def test_1_a_review_stopped_with_ctrl_c_leaves_no_folder(env, temp, monkeypatch):
    item, _ = env.start_fix()
    close, _ = _hanging_close(env, item, monkeypatch)
    assert _leftovers(temp)
    os.killpg(close.pid, signal.SIGINT)  # what Ctrl-C sends the terminal's foreground group
    assert close.wait(timeout=60) != 0

    assert _leftovers(temp) == []


def test_2_a_killed_review_s_fresh_folder_is_left_alone_until_it_is_a_day_old(
        env, temp, monkeypatch):
    item, where = env.start_fix()
    close, helper = _hanging_close(env, item, monkeypatch)
    killed = _leftovers(temp)
    close.kill()
    close.wait(timeout=60)
    os.kill(helper, signal.SIGKILL if os.name != "nt" else signal.SIGTERM)
    assert _leftovers(temp) == killed  # the killed review could not remove it

    # Fresh, it could be a running review's, so the next review leaves it.
    assert env.close(item).returncode == 0
    assert _leftovers(temp) == killed

    two_days_ago = time.time() - 2 * 24 * 3600
    os.utime(temp / killed[0], (two_days_ago, two_days_ago))
    env.commit(where, "app.py", "print('hello again')\n")  # so the next close reviews again
    assert env.close(item).returncode == 0
    assert len(env.review_calls()) == 2  # the killed one never answered
    assert _leftovers(temp) == []
def test_3_a_failed_review_and_one_whose_folder_resists_removal_leave_no_folder(
        env, temp, monkeypatch):
    env.reviews(FAILED)
    item, _ = env.start_fix()
    assert env.close(item).returncode != 0
    assert len(env.review_calls()) == 2
    assert _leftovers(temp) == []

    if os.name != "nt":  # a read-only folder there still lets its files be deleted
        env.reviews(CLEAN)
        monkeypatch.setenv("REVIEW_DO", "lock")
        assert env.close(item).returncode == 0
        assert _leftovers(temp) == []


def test_4_the_next_review_removes_a_leftover_folder_older_than_a_day(env, temp):
    old, recent = temp / "forge-review-old", temp / "forge-review-recent"
    for folder in (old, recent):
        (folder / "tree").mkdir(parents=True)
        (folder / "tree" / "file").write_text("left behind\n", "utf-8")
    two_days_ago = time.time() - 2 * 24 * 3600
    os.utime(old, (two_days_ago, two_days_ago))

    item, _ = env.start_fix()
    assert env.close(item).returncode == 0
    # A folder under a day old may belong to a review just starting, so it stays.
    assert _leftovers(temp) == ["forge-review-recent"]
