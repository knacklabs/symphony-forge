"""Observed legacy reviews and a first close's lane wait survive board and PR history.

Test-audit: missing round metadata must not erase observed review intervals; the
existing legacy tests assert totals only. Real first-close queueing must retain
its interval in the same attempt; existing queue coverage asserts the total only.
Only GitHub and reviewer edges are faked, with no production test seam.
"""
import re
from datetime import datetime

from test_close import body, env  # noqa: F401
from test_close_test_runs_wait_in_line import Close, ONE, _fix, _release, _running, _with_test_command
from test_item_time_history import records, row
from test_legacy_history_and_review_queue import history

STORY = "FIX-WHERE-TIME-WENT"


def test_20_legacy_reviews_without_rounds_keep_each_observed_attempt_in_board_and_pr(env, monkeypatch):
    # The earlier recorder's plain JSONL has no round or result event at all.
    current = history(env, monkeypatch, lambda at: [], lambda at: [
        {"step": "review", "start": at(0), "seconds": 10, "outcome": "blocked"},
        {"step": "CI wait", "start": at(10), "seconds": 3, "outcome": "failed"},
        {"step": "review", "start": at(20), "seconds": 5, "outcome": "clean"},
    ])
    assert len(current["rounds"]) == 2
    first, second = current["rounds"]
    assert first["round"] is None and first["worker_round"] is None
    assert "review blocked (10 seconds)" in first["line"]
    assert "CI unknown (3 seconds)" in first["line"]
    assert "review clean (5 seconds)" in second["line"]
    assert second["round"] is None and second["findings"] is None
    closed = env.close("tidy-readme")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    published = body(env.gh_calls("pr", "edit")[-1])
    assert first["line"] in published
    assert second["line"] in published


def test_21_first_close_without_a_worker_round_keeps_its_real_lane_wait_in_round_and_pr(env):
    log = _with_test_command(env)
    for name in ("held", "waiting"):
        _fix(env, name)
    held, waiting = Close(env, "held"), None
    try:
        _running(env, log, "start fix-held")
        waiting = Close(env, "waiting")
        waiting.until(ONE)
    finally:
        _release(env, "held")
        _release(env, "waiting")
        try:
            held.end()
        finally:
            if waiting:
                waiting.end()
    current = row(env.repo, "waiting")
    attempt = next(attempt for attempt in current["rounds"] if "review clean" in attempt["line"])
    queued = re.search(r"in line \d+ (?:seconds?|minutes?|hours?|days?)", attempt["line"])
    assert queued, attempt["line"]
    observed = records(env.repo, "events.jsonl")
    at = lambda e: datetime.fromisoformat(e["at"])  # noqa: E731
    mine = [e for e in observed if e.get("item") == "waiting"]
    # Close runs its tests and its review side by side, so the test lane and review lane waits
    # can overlap each other and the item's own test run. Each instant counts once, and own
    # tests take precedence over waiting in line.
    waits = [(at(joined), at(next(e for e in observed if e["event"] == "lane admitted"
                                  and e.get("lane_id") == joined["lane_id"])))
             for joined in mine if joined["event"] == "lane joined"]
    tests = [(at(start), at(next(e for e in mine if e["event"] == "run end" and e.get("run_id") == start["id"])))
             for start in mine if start["event"] == "run start" and start.get("kind") == "test"]
    points = sorted({point for span in waits + tests for point in span})
    seconds = sum((b - a).total_seconds() for a, b in zip(points, points[1:])
                  if any(x <= a and b <= y for x, y in waits) and not any(x <= a and b <= y for x, y in tests))
    assert seconds > 0
    assert current["time_breakdown"]["waiting_in_line"] == round(seconds, 3)
    # Publication and board derive from the same recorded attempt rather than reclassifying it.
    edits = env.gh_calls("pr", "edit")
    published = next(body(edit) for edit in reversed(edits) if "waiting is done" in body(edit))
    assert attempt["line"] in published
