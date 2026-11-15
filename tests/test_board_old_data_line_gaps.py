"""Three gaps in the board's old-data line, in real Chrome on `forge board`'s live page: a failed plan read shows
the line, an item's first failed read is asked again at once (once), and the newest failure reason is the one shown.
The browser scenarios live in test_board_says_when_data_is_old.py, which runs them.
"""
from __future__ import annotations

import os
import shutil
import sys

import pytest

from test_board_says_when_data_is_old import BROWSER_SECONDS, look, shop_and_old_fix
from test_board_server import client, live  # noqa: F401

pytestmark = pytest.mark.platform

STORY = "fix-the-old-data-line-is-missing-when-a-plan"


@pytest.mark.timeout(BROWSER_SECONDS + 120)
def test_1_a_failed_plan_read_shows_the_old_data_line_and_it_goes_when_the_plan_reads(client, tmp_path, monkeypatch):
    shop_and_old_fix(client, tmp_path, monkeypatch)
    with live(client) as url:
        look(url, "plan", tmp_path)


@pytest.mark.timeout(BROWSER_SECONDS + 120)
def test_2_an_items_first_failed_read_is_asked_again_at_once_and_only_once(client, tmp_path, monkeypatch):
    shop_and_old_fix(client, tmp_path, monkeypatch)
    with live(client) as url:
        look(url, "retry", tmp_path, item="old")


@pytest.mark.skipif(os.name == "nt", reason="the test hides git with a link on PATH; Windows needs another way")
@pytest.mark.timeout(BROWSER_SECONDS + 120)
def test_3_a_second_failure_with_another_reason_replaces_the_first_on_the_line(client, tmp_path):
    # The server runs with a PATH that finds git only through this link. Removing it makes the next failure a
    # different one: "git is not installed" instead of "could not read the work".
    link = tmp_path / "shim" / "git"
    link.parent.mkdir()
    link.symlink_to(shutil.which("git"))
    path = os.pathsep.join([str(link.parent), str(client.bin), os.path.dirname(sys.executable)])
    with live(client, FORGE_BOARD_REBUILD_WAIT="0.5", PATH=path) as url:
        look(url, "newest", tmp_path, client, item=str(link))
