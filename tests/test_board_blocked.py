"""Blocked or slow lists stalled and most-waited-on work, each with its reason and how long.

Real Forge commands and git build every item; only GitHub, the reviewer and the reader are stubs.
Board output is all the test reads.
"""
import json
import sys
from datetime import datetime, timedelta, timezone

import pytest

import conftest
from test_board_counts import board, configure
from test_close import STORY_DOC, approve_story, env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_story import READER

STORY = "FORGE-BOARD-2"
FIX = {"kind": "fix", "done_when": "It works"}
CART = STORY_DOC.replace("# Shoppers can save a basket", "# Shoppers keep a cart", 1).replace(
    "`app.py` | `tests/test_app.py`", "`cart.py` | `tests/test_cart.py`")
SHOP = STORY_DOC.replace(
    "| T2 | Show a saved basket | A saved basket shows again after sign-in | 2 | `show.py` | `tests/test_show.py` | T1 | yes |",
    "| T2 | Show a saved basket | A saved basket shows again after sign-in | 2 | `show.py` | `tests/test_show.py` | CART/T2 | no |\n"
    "| T3 | Share a basket | A shopper can share a basket | 2 | `share.py` | `tests/test_share.py` | T2 | no |")


def at(monkeypatch, when):
    for name in ("FORGE_NOW", "GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
        monkeypatch.setenv(name, when.isoformat())


def blocked_rows(repo):
    return {(row["id"], row["reason"]): row for row in board(repo)["team"]["blocked"]}


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "earlier-adoption"])
def test_3_blocked_or_slow_names_each_reason_and_how_long(env, monkeypatch, previous):
    client(env, previous)
    conftest._install(env.repo.bin, "claude", READER.format(python=sys.executable))
    configure(env, "agent")
    now = datetime.now(timezone.utc).replace(microsecond=0)

    # CART is approved 40 hours ago and nothing of it has started; three parts wait on its first,
    # one of them in SHOP.
    at(monkeypatch, now - timedelta(hours=40))
    approve_story(env.repo, CART, key="CART")
    env.repo.git("merge", "-q", "--no-edit", "story/CART")
    env.repo.git("push", "-q", "origin", "main")
    approve_story(env.repo, SHOP, key="SHOP")
    env.repo.git("merge", "-q", "--no-edit", "story/SHOP")
    env.repo.git("push", "-q", "origin", "main")
    # A fix merged a month ago is done, never slow.
    at(monkeypatch, now - timedelta(days=30))
    env.start("old", "fix/old", ".factory/fixes/old.json", {**FIX, "why": "Old"}, {"old.py": "x\n"})
    env.repo.git("merge", "-q", "--no-edit", "fix/old")
    env.repo.git("push", "-q", "origin", "main")
    # SHOP's first part started 25 hours ago and nothing has happened since.
    at(monkeypatch, now - timedelta(hours=25))
    started = env.repo.forge("task", "start", "SHOP/T1")
    assert started.returncode == 0, started.stdout + started.stderr
    # A fix started 30 hours ago whose tests are running has no idle time, so it is never slow.
    at(monkeypatch, now - timedelta(hours=30))
    env.start("busy", "fix/busy", ".factory/fixes/busy.json", {**FIX, "why": "Busy"}, {"busy.py": "x\n"})
    with (env.repo.path / ".git/forge/events.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps({"id": "busy-tests", "event": "run start", "kind": "test", "item": "busy",
                              "at": (now - timedelta(hours=30)).isoformat()}) + "\n")

    at(monkeypatch, now)
    shown = board(env.repo)
    busy = next(row for row in shown["items"] if row["id"] == "busy")
    assert busy["state"] == "in progress" and busy["idle_since"] is None
    assert "busy" not in {row["id"] for row in shown["team"]["blocked"]}
    rows = blocked_rows(env.repo)
    assert rows[("SHOP/T1", "stalled")]["seconds"] == pytest.approx(25 * 3600, abs=60)
    assert rows[("CART/T1", "blocks the most")]["seconds"] == 40 * 3600
    assert "3" in rows[("CART/T1", "blocks the most")]["detail"]
    assert all(row["detail"] for row in rows.values())
    assert ("old", "stalled") not in rows
    seconds = [row["seconds"] for row in board(env.repo)["team"]["blocked"]]
    assert seconds == sorted(seconds, reverse=True)
