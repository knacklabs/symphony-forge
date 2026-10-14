"""Blocked or slow lists stalled, looping and most-waited-on work, each with its reason and how long.

Real Forge commands and git build every item; only GitHub, the reviewer and the reader are stubs.
Board output is all the test reads.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import conftest
from test_board_counts import board, configure
from test_close import CLEAN, STORY_DOC, approve_story, blocked, env, finding  # noqa: F401
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


def review_rounds(env, item, where, count, tag):
    env.reviews(blocked(finding("P1", "Basket disappears", "loop.py")))
    for number in range(count):
        env.commit(where, "loop.py", f"x = '{tag}-{number}'\n")
        assert env.close(item).returncode == 1


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
    # A fix closed clean 31 hours ago, then blocked four rounds from 30 hours ago.
    at(monkeypatch, now - timedelta(hours=31))
    env.reviews(CLEAN)
    _, loop = env.start("loop", "fix/loop", ".factory/fixes/loop.json", {**FIX, "why": "Loop"}, {"loop.py": "x\n"})
    assert env.close("loop").returncode == 0
    for hours in (30, 29, 28, 27):
        at(monkeypatch, now - timedelta(hours=hours))
        review_rounds(env, "loop", loop, 1, hours)
    # Another fix has one blocked round on this machine.
    at(monkeypatch, now - timedelta(minutes=10))
    _, other = env.start("other", "fix/other", ".factory/fixes/other.json", {**FIX, "why": "Other"},
                         {"loop.py": "y\n"})
    review_rounds(env, "other", other, 1, "a")

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
    assert rows[("loop", "looping")]["seconds"] == 30 * 3600
    assert rows[("CART/T1", "blocks the most")]["seconds"] == 40 * 3600
    assert "3" in rows[("CART/T1", "blocks the most")]["detail"]
    assert all(row["detail"] for row in rows.values())
    assert not any(key in rows for key in [("old", "stalled"), ("other", "looping")])
    seconds = [row["seconds"] for row in board(env.repo)["team"]["blocked"]]
    assert seconds == sorted(seconds, reverse=True)

    # Machine B pushes three more blocked rounds of the other fix; after a fetch, it loops here too.
    machine_a = env.repo.path
    machine_b = env.tmp / "blocked-machine-b"
    env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(machine_b))
    env.repo.path = machine_b
    resumed = env.tmp / "blocked-other-b"
    env.repo.git("worktree", "add", "-q", "-b", "fix/other", str(resumed), "origin/fix/other")
    at(monkeypatch, now - timedelta(minutes=5))
    review_rounds(env, "other", Path(resumed), 3, "b")
    env.repo.path = machine_a
    env.repo.git("fetch", "-q", "origin")
    at(monkeypatch, now)
    assert ("other", "looping") in blocked_rows(env.repo)
