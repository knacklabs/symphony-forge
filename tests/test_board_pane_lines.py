"""The pane's Board tab and /forge text open with the board's first-screen lines.

The board JSON contract (tests/fixtures/board.json and the older release's
board-previous.json) is fed to the shipped summary.ts through Node. The grouped layout
itself is proven in tests/test_fix_pane_grouped_board.py; this file adds the five-row
cap, the older-release rule, parity with `forge board --json`'s team facts through the
mounted Board tab, and time rounding.
"""
import copy
import json
import sys
from datetime import datetime, timedelta, timezone

import pytest

import conftest
from conftest import ROOT
from test_board_counts import ONE_PART, board, configure, read_story
from test_board_pace import parts_per_week
from test_close import STORY_DOC, approve_story, env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_fix_pane_grouped_board import FIXTURE, PREVIOUS, board_tab, lines, row
from test_mod_plugin import node_run
from test_story import READER


def seven_items_need_you_shows_five_and_n_more(tmp_path):
    board = copy.deepcopy(FIXTURE["board"])
    ready = board["items"][0]
    asks = [row(ready, id=f"fix-{n}", title=f"Fix number {n}", stage="building", state="in progress",
                needs_person=True, next={"command": None, "line": "Answer it.", "step": f"forge work fix-{n}"})
            for n in range(1, 8)]
    board["items"] = asks
    board["team"]["counts"]["fixes"]["in progress"] = 7
    board["team"]["needs_you"] = [{"id": a["id"], "kind": "fix", "title": a["title"], "reason": "worker question",
                                   "since": "2026-10-12T12:00:00+00:00", "waited_seconds": 86400} for a in asks]
    shown = lines(tmp_path, board).splitlines()
    assert shown[0] == "7 in progress · 7 needs you"
    titles = [line.strip() for line in shown if line.strip().startswith("Fix number")]
    assert titles == [f"Fix number {n}" for n in range(1, 6)]
    assert shown[-1] == "  and 2 more · forge board for all"


def an_older_forge_board_draws_rows_and_no_team_line(tmp_path):
    shown = lines(tmp_path, PREVIOUS["board"])
    assert shown.startswith("READY TO MERGE\n  Polish the guide\n"), shown
    assert "in progress" not in shown and "needs you" not in shown


@pytest.mark.parametrize("case", [seven_items_need_you_shows_five_and_n_more,
                                  an_older_forge_board_draws_rows_and_no_team_line])
def test_9_the_pane_opens_with_the_boards_first_screen_lines(tmp_path, case):
    case(tmp_path)


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "earlier-adoption"])
def test_9_the_board_tab_shows_the_boards_team_facts(env, monkeypatch, tmp_path, previous):
    """Real forge commands build a repo with a plan waiting for approval, a stalled fix, a part
    other parts wait on and enough pace for go-live; the mounted Board tab shows the same facts as `forge board --json`."""
    client(env, previous)
    conftest._install(env.repo.bin, "claude", READER.format(python=sys.executable))
    configure(env, "agent")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    today = now.date()
    monday = datetime(today.year, today.month, today.day, tzinfo=timezone.utc) - timedelta(days=today.weekday())
    parts_per_week(env, monkeypatch, [monday - timedelta(weeks=n) for n in range(6, 0, -1)], [1] * 6)
    env.commit(env.repo.path, ".factory/stories/OLD/story.json", '{"status": "done"}', "An older story is done")
    env.repo.git("push", "-q", "origin", "main")
    monkeypatch.setenv("FORGE_NOW", now.isoformat())
    approve_story(env.repo, STORY_DOC)  # its second part waits on its first, which blocks the most
    read_story(env.repo, "WAIT", ONE_PART.replace("# Shoppers can save a basket", "# Shoppers can wait", 1))
    for name in ("FORGE_NOW", "GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
        monkeypatch.setenv(name, (now - timedelta(hours=30)).isoformat())
    env.start("slow", "fix/slow", ".factory/fixes/slow.json",
              {"kind": "fix", "why": "Slow fix", "done_when": "It works"}, {"slow.py": "x\n"})
    for name in ("FORGE_NOW", "GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
        monkeypatch.setenv(name, now.isoformat())

    team = board(env.repo)["team"]
    assert team["needs_you"] and team["blocked"] and team["go_live"]["status"] == "about"
    shown = board_tab(tmp_path, env.repo).splitlines()
    counts = team["counts"]
    due = datetime.fromisoformat(team["go_live"]["earliest"])
    assert " · ".join([
        f"{counts['parts']['in progress'] + counts['fixes']['in progress']} in progress",
        f"{len(team['needs_you'])} needs you", f"{len(team['blocked'])} stuck",
        f"go-live about {due:%b} {due.day}"]) in shown, shown

    def titles(name, entries):
        """The row titles under a group heading, the story key beside each set aside."""
        start = next(n for n, line in enumerate(shown) if line.startswith(name))
        end = next((n for n, line in enumerate(shown) if n > start and line.isupper()), len(shown))
        wanted = {e["title"] for e in entries}
        return shown[start + 1:end], [line.split("  ")[0] for line in shown[start + 1:end]
                                      if line.split("  ")[0] in wanted]

    assert titles("NEEDS YOU", team["needs_you"])[1] == [e["title"] for e in team["needs_you"]]
    stuck, found = titles("STUCK", team["blocked"])
    assert found == [e["title"] for e in team["blocked"]], stuck
    assert all(any(e["detail"] in line for line in stuck) for e in team["blocked"]), stuck


def test_9_pane_times_round_like_the_board(tmp_path):
    """A 150-second review reads 2m, as the board's 2 minutes, not 2m 30s or 3m."""
    item = row(FIXTURE["board"]["items"][0], stages=[{"name": "Review", "status": "pass", "seconds": 150},
                                                     {"name": "CI", "status": "running",
                                                      "started_at": "2026-10-13T11:59:00Z"}])
    shown = node_run(tmp_path, f"""
const {{ summary }} = await import({json.dumps((ROOT / "src/forge/mod/hooks/summary.ts").as_uri())});
const data = {{ board: {json.dumps({**FIXTURE["board"], "items": [item]})}, next: null, lanes: null, error: null, refreshedAt: 0 }};
console.log(JSON.stringify(summary(data, Date.parse("2026-10-13T12:00:00Z")).join("\\n")));
""")
    assert "Review ✓ 2m →" in shown and "CI ● 1m" in shown, shown
