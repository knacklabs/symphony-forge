"""Dropped fixes leave the board's rows AND counts, and undo restores both.

Exercises src/forge/board.py through the board command.

DROP owns command preservation and row visibility. This test owns the board's
aggregate contract: a hidden fix must not be counted as finished. Real commands
exercise new and upgraded clients and a teammate with a stale local branch;
only GitHub is faked at its edge. No production seam is needed.
"""
import json

from conftest import Repo
from test_board import seen
from test_fix_drop import _github, _pr, _start
from test_started_branches_claim_the_work import client  # noqa: F401

STORY = "FORGE-DROP-1"


def test_7_board_omits_dropped_fixes_and_restores_them_after_fetch(client):
    _start(client)
    _github(client, [_pr()])
    peer = client.path.parent / "board-teammate"
    client.git("clone", "-q", client.git("remote", "get-url", "origin"), str(peer))
    viewer = Repo(peer, client.bin)
    viewer.git("switch", "-q", "fix/unwanted")

    def check(present):
        for observer in (client, viewer):
            shown = observer.forge("board", "--json")
            assert shown.returncode == 0, shown.stdout + shown.stderr
            board = json.loads(shown.stdout)
            assert ("unwanted" in {row["id"] for row in board["items"]}) == present
            assert board["team"]["counts"]["fixes"]["done"] == 0
            assert sum(board["team"]["counts"]["fixes"].values()) == int(present)
            assert board["team"]["counts"]["finished_last_7_days"]["fixes"] == 0
            page = observer.path / ".git" / "drop-board.html"
            made = observer.forge("board", "--out", str(page))
            assert made.returncode == 0, made.stdout + made.stderr
            assert ("Readers can see a greeting" in seen(page)) == present

    check(True)
    dropped = client.forge("fix", "drop", "unwanted", "--because", "Pause the greeting")
    assert dropped.returncode == 0, dropped.stdout + dropped.stderr
    viewer.git("fetch", "-q", "origin")
    check(False)
    restored = client.forge("fix", "drop", "unwanted", "--undo")
    assert restored.returncode == 0, restored.stdout + restored.stderr
    viewer.git("fetch", "-q", "origin")
    check(True)
