"""The pane's Board tab and /forge text read as plain lines a person can act on.

The board JSON contract (tests/fixtures/board.json and the older release's
board-previous.json) is fed to the shipped summary.ts through Node.
"""
import copy
import json

import pytest

from conftest import ROOT
from test_mod_plugin import node_run

STORY = "pane-grouped-board"
NOW = "2026-10-13T12:00:00Z"
FIXTURE = json.loads((ROOT / "tests/fixtures/board.json").read_text("utf-8"))
PREVIOUS = json.loads((ROOT / "tests/fixtures/board-previous.json").read_text("utf-8"))


def row(base, **values):
    return {**copy.deepcopy(base), "children": [], **values}


def lines(tmp_path, board, error=None):
    summary = (ROOT / "src/forge/mod/hooks/summary.ts").as_uri()
    return node_run(tmp_path, f"""
const {{ text }} = await import({json.dumps(summary)});
const data = {{ board: {json.dumps(board)}, next: {json.dumps(FIXTURE["next"])}, lanes: null,
  error: {json.dumps(error)}, refreshedAt: 0 }};
console.log(JSON.stringify(text(data, Date.parse({json.dumps(NOW)}))));
""")


def team_board():
    board = copy.deepcopy(FIXTURE["board"])
    ready, story = board["items"]
    stages = copy.deepcopy(ready["stages"])
    stages[2].update(status="running", started_at="2026-10-13T11:48:00Z")
    ask = row(ready, id="ASK/PERIOD", kind="task", title="Ask asks for the comparison period",
              stage="building", state="in progress", findings={"count": 3, "titles": [], "items": [
                  {"title": "Input lost", "priority": "P1"}], "dismissed": 2},
              gates={**ready["gates"], "review": {"status": "blocked", "count": 3}},
              next={"command": "forge close ASK/PERIOD --resolve stop", "line": "Choose how to go on."})
    stuck = row(ready, id="AVB/PERIOD", kind="task", title="Actual-versus-Budget answers ask for the period",
                stage="building", state="in progress", stalled=True, idle_since="2026-10-05T11:02:00+00:00",
                next={"command": "forge work AVB/PERIOD", "line": "Build it."})
    moving = row(ready, id="counts", kind="fix", title="Board counts", stage="building", state="in progress",
                 activity={"status": "running", "action": "review"}, stages=stages, round=None,
                 next={"command": None, "line": "Review is running."})
    green = row(ready, id="trust", title="Codex trust fix", pr={"number": 9, "checks": "pass", "failures": []})
    done = row(ready, id="old", title="An old finished fix", stage="done", state="done")
    board["items"] = [
        row(story, id="ASK", title="Ask story", stage="building", state="building", children=[ask]),
        row(story, id="AVB", title="Budget story", stage="building", state="building", children=[stuck]),
        moving, green, ready, story, done,
    ]
    team = board["team"]
    team["counts"]["parts"]["in progress"] = 2
    team["counts"]["fixes"]["in progress"] = 1
    team["needs_you"] = [{"id": "ASK/PERIOD", "kind": "task", "title": ask["title"], "reason": "review loop",
                          "since": "2026-10-12T12:00:00+00:00", "waited_seconds": 86400}]
    team["go_live"] = {"status": "range", "earliest": "2026-10-18", "latest": "2026-10-20",
                       "remaining_parts": 4, "no_plan": {"count": 0, "titles": []}}
    return board


def groups_in_plain_words(tmp_path):
    shown = lines(tmp_path, team_board())
    assert shown == """\
3 in progress · 1 needs you · 1 stuck · go-live Oct 18 – Oct 20

NEEDS YOU
  Ask asks for the comparison period  ASK
    Review found 3 problems. The builder is stuck.
    → decide: forge close ASK/PERIOD --resolve stop

STUCK (no progress 8 days)
  Actual-versus-Budget answers ask for the period  AVB
    Building · last activity Oct 5
    → forge work AVB/PERIOD

MOVING
  Board counts · Review running · 12 min

READY TO MERGE
  Codex trust fix · checks green
  Polish the guide

WAITING OR NOT STARTED (1) · forge board for all"""
    for hidden in ("unknown", "T11:", "P1", "dismissed", " 0 ", "Build → Tests", "round"):
        assert hidden not in shown


def zero_counts_unknown_go_live_and_failures_stay_hidden(tmp_path):
    board = team_board()
    board["team"]["counts"]["parts"]["in progress"] = 0
    board["team"]["counts"]["fixes"]["in progress"] = 0
    board["team"]["go_live"]["status"] = "not enough history"
    shown = lines(tmp_path, board, error="offline")
    assert shown.splitlines()[0] == "1 needs you · 1 stuck"
    assert shown.endswith("\n\nCouldn't refresh: offline")
    board["items"] = []
    board["team"] = FIXTURE["board"]["team"]
    assert lines(tmp_path, board) == "Nothing in progress."


def an_older_forge_board_draws_rows_and_no_team_line(tmp_path):
    assert lines(tmp_path, PREVIOUS["board"]) == """\
READY TO MERGE
  Polish the guide

WAITING OR NOT STARTED (1) · forge board for all"""


@pytest.mark.parametrize("case", [groups_in_plain_words, zero_counts_unknown_go_live_and_failures_stay_hidden,
                                  an_older_forge_board_draws_rows_and_no_team_line])
def test_1_the_board_tab_and_forge_text_read_in_plain_words(tmp_path, case):
    case(tmp_path)
