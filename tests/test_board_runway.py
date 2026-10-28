"""The board's facts: every story and fix with its state, finished work older than a week kept by
`forge board --out` and left out of `--json`, and the first-screen team lists.
New plan reads use src/forge/story.py before those plans appear on the board."""
import json
import sys
from datetime import datetime, timedelta, timezone

import pytest

import conftest
from test_board_counts import ONE_PART, board, clock, configure, github, read_story
from test_board_trends import ANA, BEN, NO_NAME, pr
from test_close import approve_story, blocked, env, finding  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_story import READER
from test_board import DOC
from test_board_dependency_timelines import _configured, _land_fixture
from test_story import claude_plan, hook, new_story, ready, worktree

STORY = "FORGE-BOARD-2"


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_8_every_item_and_older_finished_work(repo, gh, tmp_path, claude_payload, monkeypatch, history):
    _configured(repo, gh, tmp_path, history, ("SHOP", "PLAN", "IDEA", "WAIT"))
    now = datetime.now(timezone.utc).replace(microsecond=0)
    monkeypatch.setenv("FORGE_NOW", now.isoformat())

    # A fix merged ten days ago: older than the JSON's seven days, still on the page.
    monkeypatch.setenv("GIT_COMMITTER_DATE", (now - timedelta(days=10)).isoformat())
    old = repo.forge("fix", "start", "Greet returning shoppers", "--done", "Shoppers see a greeting",
                     "--slug", "greet-shoppers")
    assert old.returncode == 0, old.stderr
    tree = worktree(repo, "fix/greet-shoppers")
    (tree / "greeting.txt").write_text("Welcome back\n", "utf-8")
    repo.git("add", "-A", cwd=tree)
    repo.git("commit", "-qm", "Greet returning shoppers", cwd=tree)
    monkeypatch.delenv("GIT_COMMITTER_DATE")
    repo.git("merge", "-q", "--ff-only", "fix/greet-shoppers")
    _land_fixture(repo)

    # A fix nobody has touched for two days: blocked or slow.
    earlier = (now - timedelta(days=2)).isoformat()
    monkeypatch.setenv("FORGE_NOW", earlier)
    monkeypatch.setenv("GIT_COMMITTER_DATE", earlier)
    stale = repo.forge("fix", "start", "Tidy the help page", "--done", "The help page is tidy", "--slug", "tidy-help")
    assert stale.returncode == 0, stale.stderr
    monkeypatch.delenv("GIT_COMMITTER_DATE")
    monkeypatch.setenv("FORGE_NOW", now.isoformat())

    # A plan read and waiting for its approval: it needs a person.
    waiting = new_story(repo, "WAIT", "Wait for a decision")
    (waiting / "plans/WAIT.md").write_text(DOC.replace("# Shoppers can save a basket", "# Wait for a decision", 1)
                                           .replace("come back to it later", "pick it up on another day"), "utf-8")
    read = repo.forge("read", "WAIT")
    assert read.returncode == 0, read.stderr

    # Building (a part started), planning, no plan yet, and an open fix.
    shop = ready(repo, "SHOP", DOC)
    assert hook(repo, claude_plan(claude_payload, DOC, cwd=shop)).returncode == 0
    started = repo.forge("task", "start", "SHOP/SAVE")
    assert started.returncode == 0, started.stderr
    new_story(repo, "PLAN", "Plan the next improvement")
    fixed = repo.forge("fix", "start", "Readme greets new readers", "--done", "Readers see a greeting",
                       "--slug", "readme-greets")
    assert fixed.returncode == 0, fixed.stderr
    # A fix whose review came back clean: ready to merge.
    ready_fix = repo.forge("fix", "start", "Shelf shows prices", "--done", "Prices show", "--slug", "shelf-prices")
    assert ready_fix.returncode == 0, ready_fix.stderr
    receipts = repo.path / ".git/forge/ready"
    receipts.mkdir(parents=True, exist_ok=True)
    (receipts / "shelf-prices.json").write_text(json.dumps({
        "review": "clean", "commit": repo.git("rev-parse", "fix/shelf-prices")}), "utf-8")

    machine = repo.forge("board", "--json")
    assert machine.returncode == 0, machine.stderr
    data = json.loads(machine.stdout)
    out = tmp_path / "board.json"
    made = repo.forge("board", "--out", str(out))
    assert made.returncode == 0, made.stderr
    states = {row["title"]: row["state"] for row in json.loads(out.read_text("utf-8"))["items"]}

    # Every story and fix with its state, including the fix finished ten days ago, which the
    # trimmed JSON leaves out.
    assert {title: states[title] for title in (
        "Shoppers can save a basket", "Readme greets new readers", "Shelf shows prices", "Tidy the help page",
        "Plan the next improvement", "Wait for a decision", "A story with no title yet",
        "Greet returning shoppers")} == {
        "Shoppers can save a basket": "building", "Readme greets new readers": "in progress",
        "Shelf shows prices": "ready to merge", "Tidy the help page": "in progress",
        "Plan the next improvement": "planning", "Wait for a decision": "waiting for approval",
        "A story with no title yet": "no plan yet", "Greet returning shoppers": "done"}
    assert "Greet returning shoppers" not in machine.stdout

    # The in-progress list holds the building story, the open fix and the ready fix; a plan
    # waiting for approval needs a person and the untouched fix is blocked or slow. Both lists
    # stay null until their part lands.
    assert sorted(row["title"] for row in data["team"]["in_progress"]) == [
        "Readme greets new readers", "Shelf shows prices", "Shoppers can save a basket"]
    if data["team"]["needs_you"] is not None:
        assert "WAIT" in {entry["id"] for entry in data["team"]["needs_you"]}
    if data["team"]["blocked"] is not None:
        assert "tidy-help" in {entry["id"] for entry in data["team"]["blocked"]}


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "earlier-adoption"])
def test_7_first_screen(env, monkeypatch, previous):
    client(env, previous)
    conftest._install(env.repo.bin, "claude", READER.format(python=sys.executable))
    configure(env, "human")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    clock(monkeypatch, now)
    # A building story whose part has a blocked review round.
    env.reviews(blocked(finding("P1", "The page still loads every row")))
    approve_story(env.repo, ONE_PART)
    env.repo.git("merge", "-q", "--no-edit", "story/SHOP")
    env.repo.git("push", "-q", "origin", "main")
    started = env.repo.forge("task", "start", "SHOP/T1")
    assert started.returncode == 0, started.stdout + started.stderr
    env.commit(worktree(env.repo, "task/SHOP-T1"), "app.py", "print('saved')\n", "Save a basket")
    env.close("SHOP/T1")
    # Seven plans waiting for their approval: seven waits on a person.
    for n in range(7):
        read_story(env.repo, f"WAIT-{n + 1}", ONE_PART)
    # Two fixes nobody touched for two days: blocked or slow.
    earlier = (now - timedelta(days=2)).isoformat()
    monkeypatch.setenv("GIT_COMMITTER_DATE", earlier)
    clock(monkeypatch, now - timedelta(days=2))
    for n in range(2):
        started = env.repo.forge("fix", "start", f"Tidy help page {n + 1}", "--done", "It is tidy", "--slug", f"tidy-{n}")
        assert started.returncode == 0, started.stderr
    monkeypatch.delenv("GIT_COMMITTER_DATE")
    clock(monkeypatch, now)
    # Six fixes; the owner accepts the first P1 before the human merge wait.
    for n in range(6):
        started = env.repo.forge("fix", "start", f"Speed up page {n + 1}", "--done", "It is fast", "--slug", f"speed-{n}")
        assert started.returncode == 0, started.stderr
    tree = worktree(env.repo, "fix/speed-0")
    env.commit(tree, "speed.txt", "fast\n", "Speed up the page")
    closed = env.repo.forge("close", "speed-0", cwd=tree)
    assert closed.returncode == 1 and "reached the round limit" in closed.stderr, closed.stdout + closed.stderr
    accepted = env.repo.forge("close", "speed-0", "--resolve", "accept", "--reason",
                              "Keep the current page speed for this version", cwd=tree)
    assert accepted.returncode == 0 and "Ready:" in accepted.stdout, accepted.stdout + accepted.stderr
    # Merged pull requests for the trends: one through Forge two weeks ago, one around it today.
    github(env, [pr(1, "task/OLD-T1", BEN, now - timedelta(days=14)),
                 pr(2, "quick-patch", ANA, now - timedelta(hours=1), "Patch the login page"),
                 pr(3, "fix/old-readme", ANA, now - timedelta(days=21)),
                 pr(4, "tidy-config", NO_NAME, now - timedelta(days=28))])
    clock(monkeypatch, now + timedelta(minutes=2))

    data = board(env.repo)
    team = data["team"]
    # Seven plan approvals and one human merge wait, two idle fixes, and the rest building.
    needs = {row["id"] for row in team["needs_you"] or []}
    stuck = {row["id"] for row in team["blocked"] or []}
    building = [row["title"] for row in data["items"] if row["id"] not in needs | stuck
                and row["state"] in ("building", "in progress", "ready to merge")]
    assert len(building) == (6 if team["blocked"] is not None else 8)
    if team["needs_you"] is not None:
        assert len(team["needs_you"]) == 8
        assert ("speed-0", "merge") in {(row["id"], row["reason"]) for row in team["needs_you"]}
    if team["blocked"] is not None:
        assert len(team["blocked"]) == 2

    # Go-live, and a row's round lines and who started it.
    assert team["go_live"]["status"] == "not enough history"
    row = next(r for r in data["items"] if r["id"] == "speed-0")
    assert row["state"] == "ready to merge"
    assert row["rounds"], "The close recorded its round and follow-up"
    assert row["started_by"]
    # A building story holds its parts' round lines.
    story = next(r for r in data["items"] if r["id"] == "SHOP")
    assert story["state"] == "building"
    assert [r["line"] for part in story["children"] for r in part.get("rounds") or []], \
        "The part's blocked close recorded a round"
    assert len(team["trends"]["people"]) == 3 and team["around_forge"]
