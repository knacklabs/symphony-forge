"""Four gaps in the board's old-data line, in real Chrome on `forge board`'s live page: a failed plan read shows
the line, an item's first failed read is asked again at once (once), an item the snapshot leaves out is read again when
the server can read it, and the newest failure reason is the one shown.
The server really fails: it runs with a PATH that finds git only through a link, and a scenario removes the link, so
every read that needs git is refused with the server's own answer. The browser scenarios live in
test_board_says_when_data_is_old.py, which runs them.
"""
from __future__ import annotations

import os
import shutil
import sys

import pytest

from test_board_says_when_data_is_old import BROWSER_SECONDS, look, shop_and_old_fix
from test_board_server import client, live  # noqa: F401

pytestmark = [pytest.mark.platform, pytest.mark.timeout(BROWSER_SECONDS + 120),
              pytest.mark.skipif(os.name == "nt", reason="the tests take git from the server with a link on PATH; Windows needs another way")]

STORY = "fix-the-old-data-line-is-missing-when-a-plan"


@pytest.fixture
def git_link(client, tmp_path):
    """The one link that gives the board server its git, and the PATH it runs with."""
    link = tmp_path / "shim" / "git"
    link.parent.mkdir()
    link.symlink_to(shutil.which("git"))
    path = os.pathsep.join([str(link.parent), str(client.bin), os.path.dirname(sys.executable)])
    return link, {"FORGE_BOARD_REBUILD_WAIT": "0.5", "PATH": path}


def test_1_a_failed_plan_read_shows_the_old_data_line_and_it_goes_when_the_plan_reads(client, tmp_path, monkeypatch, git_link):
    shop_and_old_fix(client, tmp_path, monkeypatch)
    link, env = git_link
    with live(client, **env) as url:
        look(url, "plan", tmp_path, link=link)


def test_2_an_items_first_failed_read_is_asked_again_at_once_and_only_once(client, tmp_path, monkeypatch, git_link):
    shop_and_old_fix(client, tmp_path, monkeypatch)
    link, env = git_link
    with live(client, **env) as url:
        look(url, "retry", tmp_path, link=link)


def test_3_a_second_failure_with_another_reason_replaces_the_first_on_the_line(client, git_link, tmp_path):
    link, env = git_link
    with live(client, **env) as url:
        look(url, "newest", tmp_path, client, link=link)


def test_4_an_item_left_out_of_the_snapshot_that_could_not_be_read_opens_when_the_server_can_read_it(client, tmp_path, monkeypatch, git_link):
    shop_and_old_fix(client, tmp_path, monkeypatch)
    link, env = git_link
    with live(client, **env) as url:
        look(url, "recover", tmp_path, link=link)
