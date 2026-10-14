"""The pane's Board tab and /forge text open with the board's first-screen lines.

The board JSON contract (tests/fixtures/board.json and the older release's
board-previous.json) is fed to the shipped summary.ts through Node. The grouped layout
itself is proven in tests/test_fix_pane_grouped_board.py; this file adds the five-row
cap, the older-release rule, parity with `forge board --json`'s team facts through the
mounted Board tab, and time rounding.
"""
import copy
import json
import re
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

STORY = "FORGE-BOARD-2"


def seven_items_need_you_shows_five_and_n_more(_request, tmp_path):
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


def an_older_forge_board_draws_rows_and_no_team_line(_request, tmp_path):
    shown = lines(tmp_path, PREVIOUS["board"])
    assert shown.startswith("READY TO MERGE\n  Polish the guide\n"), shown
    assert "in progress" not in shown and "needs you" not in shown


def the_board_tab_shows_the_boards_team_facts(request, tmp_path, previous):
    """Real forge commands build a repo with six plans waiting for approval, read newest-first by key,
    six stalled fixes, a part other parts wait on, six fixes in progress and enough pace for
    go-live; the mounted Board tab shows the same facts as `forge board --json` and its page."""
    env, monkeypatch = request.getfixturevalue("env"), request.getfixturevalue("monkeypatch")
    client(env, previous)
    conftest._install(env.repo.bin, "claude", READER.format(python=sys.executable))
    configure(env, "agent")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    today = now.date()
    monday = datetime(today.year, today.month, today.day, tzinfo=timezone.utc) - timedelta(days=today.weekday())
    parts_per_week(env, monkeypatch, [monday - timedelta(weeks=n) for n in range(6, 0, -1)], [1] * 6)
    env.commit(env.repo.path, ".factory/stories/OLD/story.json", '{"status": "done"}', "An older story is done")
    env.repo.git("push", "-q", "origin", "main")

    def at(when):
        for name in ("FORGE_NOW", "GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
            monkeypatch.setenv(name, when.isoformat())

    at(now)
    approve_story(env.repo, STORY_DOC)  # its second part waits on its first, which blocks the most
    for n in range(1, 7):  # W1 is read last, so oldest first is not key order
        at(now - timedelta(hours=n))
        read_story(env.repo, f"W{n}", ONE_PART.replace("# Shoppers can save a basket", f"# Shoppers wait {n}", 1))
    for n in range(1, 7):
        at(now - timedelta(hours=30 + n))
        env.start(f"slow{n}", f"fix/slow{n}", f".factory/fixes/slow{n}.json",
                  {"kind": "fix", "why": f"Slow fix {n}", "done_when": "It works"}, {f"slow{n}.py": "x\n"})
        at(now - timedelta(minutes=n))
        env.start(f"busy{n}", f"fix/busy{n}", f".factory/fixes/busy{n}.json",
                  {"kind": "fix", "why": f"Busy fix {n}", "done_when": "It works"}, {f"busy{n}.py": "x\n"})
    at(now)

    team = board(env.repo)["team"]
    assert [len(team[name]) > 5 for name in ("needs_you", "blocked", "in_progress")] == [True] * 3
    assert team["go_live"]["status"] == "about"
    assert [e["id"] for e in team["needs_you"]] != sorted(e["id"] for e in team["needs_you"])
    shown = board_tab(tmp_path, env.repo).splitlines()
    counts = team["counts"]
    due = datetime.fromisoformat(team["go_live"]["earliest"])
    assert " · ".join([
        f"{counts['parts']['in progress'] + counts['fixes']['in progress']} in progress",
        f"{len(team['needs_you'])} needs you", f"{len(team['blocked'])} stuck",
        f"go-live about {due:%b} {due.day}"]) in shown, shown
    # The page's sentence and its labelled totals, word for word.
    assert team["sentence"] in shown, shown
    labels = {"finished_last_7_days": "Finished in the last 7 days"}
    for kind, by in counts.items():
        line = f"{labels.get(kind, kind.capitalize())} — " + "; ".join(f"{name[0].upper()}{name[1:]}: {n}"
                                                                      for name, n in by.items())
        assert line in shown, (line, shown)

    def shown_as(e):
        """A row's first line: its title, with the story key small beside it for a story or part."""
        key = e["id"] if e["kind"] == "story" else e["id"].split("/")[0] if "/" in e["id"] else None
        return f"{e['title']}  {key}" if key else e["title"]

    def group(name, entries):
        """The first five rows under a heading, in order, and its overflow line."""
        start = next(n for n, line in enumerate(shown) if line.startswith(name))
        end = next((n for n, line in enumerate(shown) if n > start and line.isupper()), len(shown))
        lines = shown[start + 1:end]
        assert f"and {len(entries) - 5} more · forge board for all" in lines, (name, lines)
        wanted = {shown_as(e) for e in entries}
        rows = [line.split(" · ")[0] for line in lines if line.split(" · ")[0] in wanted]
        assert rows == [shown_as(e) for e in entries][:5], (name, lines)
        return lines

    # Each wait and block shows the age the page shows, in short units (3 hours reads 3h).
    page = tmp_path / "board.html"
    assert env.repo.forge("board", "--out", str(page)).returncode == 0
    html = page.read_text("utf-8")

    def ages(lane):
        what = re.findall(r'class="what">(.*?)</span>', html[html.index(f'id="{lane}"'):html.index(f"<!-- end {lane} -->")])
        return [re.sub(r"(\d+) ([smhd])\w*", r"\1\2", text.rsplit(" · ", 1)[-1].rsplit("waiting ", 1)[-1])
                for text in what]

    needs = group("NEEDS YOU", team["needs_you"])
    assert [age for age in ages("needs-you")[:5] if any(f"waiting {age}" in line for line in needs)] \
        == ages("needs-you")[:5], (ages("needs-you"), needs)
    stuck = group("STUCK", team["blocked"])
    assert all(any(e["detail"] in line for line in stuck) for e in team["blocked"][:5]), stuck
    assert all(any(line.endswith(f" · {age}") for line in stuck) for age in ages("blocked")[:5]), (ages("blocked"), stuck)
    group("MOVING", [e for e in team["in_progress"] if e["state"] != "ready to merge"])


def pane_times_round_like_the_board(_request, tmp_path):
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


def new_client_board_tab_matches(request, tmp_path):
    the_board_tab_shows_the_boards_team_facts(request, tmp_path, previous=False)


def adopted_client_board_tab_matches(request, tmp_path):
    the_board_tab_shows_the_boards_team_facts(request, tmp_path, previous=True)


@pytest.mark.parametrize("case", [seven_items_need_you_shows_five_and_n_more,
                                  an_older_forge_board_draws_rows_and_no_team_line, pane_times_round_like_the_board,
                                  new_client_board_tab_matches, adopted_client_board_tab_matches])
def test_9_the_pane_opens_with_the_boards_first_screen_lines(request, tmp_path, case):
    case(request, tmp_path)
