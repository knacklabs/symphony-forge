"""A board read repairs idle time in a compact history from an earlier release.

Test audit: this protects the board's shared pull-request history contract. A
previous release can publish an interval as ``nothing_running`` and count it as
unmeasured, while its round record still assigns that time to person waiting.
The board must preserve the measured totals and remove that false attribution.
Existing interval tests cover histories derived from local logs, not an older
summary read from GitHub. This test uses the real board command and a pull-request
body as the old persisted input; it needs no production seam.
"""
import json
import re
from datetime import datetime, timedelta, timezone

from test_close import body, env  # noqa: F401
from test_item_time_history import row
from test_pull_request_body_limit import publish_snapshot
from test_round_seconds import configured_client

STORY = "FIX-EXACT-WAIT-TIMES"


def test_6_previous_compacted_gaps_stay_unmeasured_on_the_board(env, monkeypatch):
    configured_client(env, previous=True)
    item, _ = env.start_fix(round=0)
    worked = env.repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr

    published = body(env.gh_calls("pr", "edit")[-1])
    match = re.search(r"<!-- forge:time-record (\{.*?\}) -->", published, re.S)
    assert match, "The pull request must hold the shared time record."
    record = json.loads(match[1])
    until = datetime.now(timezone.utc).replace(microsecond=0)
    start = until - timedelta(seconds=95)
    stamp = lambda seconds: (start + timedelta(seconds=seconds)).isoformat()
    categories = ("building", "own_tests", "reviewing", "fixing_findings", "waiting_for_ci",
                  "waiting_in_line", "waiting_for_owner", "nothing_running")
    old_line = "Round 1: own tests passed (20 seconds); nothing running (60 seconds)"
    record.update(events=[], timings=[], clean_reviews=[], summary={
        "round": 1,
        "until": until.isoformat(),
        "time_breakdown": {category: value for category, value in (
            (category, 20 if category == "own_tests" else
             15 if category == "waiting_for_ci" else 60 if category == "nothing_running" else None)
            for category in categories)},
        "working_seconds": 20,
        "waiting_seconds": 15,
        "unknown_seconds": 60,
        "total_seconds": 95,
        "intervals": [
            {"start": stamp(0), "end": stamp(20), "category": "own_tests", "kind": "working"},
            {"start": stamp(20), "end": stamp(35), "category": "waiting_for_ci", "kind": "waiting"},
            {"start": stamp(35), "end": stamp(95), "category": "nothing_running", "kind": "unknown"},
        ],
        "seen": [],
        "known": True,
        "rounds": [{"round": 1, "worker_round": 1, "line": old_line, "findings": [],
                    "new_findings": 0, "repeat_findings": 0,
                    "seconds": {"own_tests": 20, "nothing_running": 60},
                    "seconds_known": True}],
    })
    published = published.replace(match[1], json.dumps(record))
    # GitHub is the persisted source. The peer clone has no local timing logs to mask a bad read.
    publish_snapshot(env, item, published)
    clone = env.tmp / "peer-clone"
    env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(clone))
    env.repo.path = clone
    monkeypatch.setenv("FORGE_NOW", until.isoformat())

    current = row(env.repo, item)

    assert current["total_seconds"] == 95
    assert current["working_seconds"] == 20
    assert current["waiting_seconds"] == 15
    assert current["unknown_seconds"] == 60
    assert current["time_breakdown"]["own_tests"] == 20
    assert current["time_breakdown"]["waiting_for_ci"] == 15
    assert current["time_breakdown"]["waiting_for_owner"] is None
    assert current["time_breakdown"]["nothing_running"] is None
    [gap] = [interval for interval in current["intervals"] if interval["start"] == stamp(35)]
    assert (gap["category"], gap["kind"]) == ("unknown", "unknown")
    [round_] = current["rounds"]
    assert round_["seconds"] is None
    assert "nothing running" not in round_["line"].lower()
    assert "waiting for the owner" not in round_["line"].lower()
    assert "unmeasured time" in round_["line"].lower()
