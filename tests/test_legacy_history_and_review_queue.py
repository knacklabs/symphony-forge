"""Unknown legacy gaps and observed review work remain honest on the board."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from test_close import STORY_DOC, env  # noqa: F401
from test_item_time_history import row

STORY = "FIX-WHERE-TIME-WENT"


def history(env, monkeypatch, events, timings):
    began = datetime(2026, 1, 1, tzinfo=timezone.utc)
    at = lambda seconds: (began + timedelta(seconds=seconds)).isoformat()
    item, _ = env.start_fix(round=3, steps=[{"step": "start", "at": at(0)}])
    top = env.repo.path / ".git/forge"
    top.mkdir(exist_ok=True)
    for name, rows in (("events", events), ("timings", timings)):
        values = [{"item": item, "id": f"{name}-{index}", **record}
                  for index, record in enumerate(rows(at))]
        (top / f"{name}.jsonl").write_text("".join(json.dumps(record) + "\n" for record in values), "utf-8")
    monkeypatch.setenv("FORGE_NOW", at(70))
    return row(env.repo, item)


def test_12_legacy_internal_gaps_stay_unknown_until_complete_activity_recording(env, monkeypatch):
    # Earlier releases recorded only these timings: neither gap establishes idle or owner time.
    current = history(env, monkeypatch, lambda at: [
        {"event": "work phase", "round": 3, "phase": "building", "at": at(60)},
        {"event": "run start", "kind": "worker", "round": 3, "id": "build", "at": at(60)},
        {"event": "run end", "kind": "worker", "round": 3, "run_id": "build", "at": at(65)},
    ], lambda at: [
        {"step": "review", "start": at(0), "seconds": 10, "outcome": "clean"},
        {"step": "CI wait", "start": at(20), "seconds": 5, "outcome": "failed"},
    ])
    assert current["total_seconds"] == 70
    assert current["time_breakdown"]["reviewing"] == 10
    assert current["time_breakdown"]["waiting_for_ci"] == 5
    assert current["time_breakdown"]["building"] == 5
    assert current["time_breakdown"]["nothing_running"] == 5
    assert current["time_breakdown"]["waiting_for_owner"] is None
    assert sum(value or 0 for value in current["time_breakdown"].values()) == 25


def test_13_mixed_legacy_report_retains_observed_repeat_beside_an_unclassified_finding(env, monkeypatch):
    first = {"priority": "P1", "title": "Basket disappears", "file": "app.py"}
    unseen = {"priority": "P1", "title": "Quantity disappears", "file": "app.py"}
    current = history(env, monkeypatch, lambda at: [
        {"event": "review result", "round": 1, "outcome": "blocked", "at": at(0)},
        {"event": "review result", "round": 2, "outcome": "blocked", "findings": [first], "at": at(10)},
        {"event": "review result", "round": 3, "outcome": "blocked", "findings": [first, unseen], "at": at(20)},
    ], lambda at: [])
    latest = current["rounds"][-1]
    assert latest["new_findings"] is None
    assert latest["repeat_findings"] == 1
    assert "unknown new, 1 repeated" in latest["line"]
    assert latest["findings"] == [first, unseen]


def test_14_review_round_separates_lane_wait_from_review_time(env, monkeypatch):
    current = history(env, monkeypatch, lambda at: [
        {"event": "run start", "kind": "review", "round": 3, "id": "review", "at": at(0)},
        {"event": "lane joined", "kind": "review", "round": 3, "lane_id": "queue", "at": at(0)},
        {"event": "lane admitted", "kind": "review", "round": 3, "lane_id": "queue", "at": at(60)},
        {"event": "run end", "kind": "review", "round": 3, "run_id": "review", "at": at(65)},
        {"event": "review result", "round": 3, "review_round": 1, "outcome": "clean", "findings": [], "at": at(65)},
    ], lambda at: [
        {"step": "review", "round": 3, "start": at(0), "seconds": 65, "outcome": "clean"},
    ])
    assert current["time_breakdown"]["reviewing"] == 5
    assert current["time_breakdown"]["waiting_in_line"] == 60
    assert "review clean (5s)" in current["rounds"][0]["line"]
    assert "in line 60s" in current["rounds"][0]["line"]


def test_15_pre_upgrade_run_records_do_not_establish_complete_activity_history(env, monkeypatch):
    current = history(env, monkeypatch, lambda at: [
        {"event": "run start", "kind": "review", "round": 1, "id": "old-review", "at": at(0)},
        {"event": "run end", "kind": "review", "round": 1, "run_id": "old-review", "at": at(10)},
        {"event": "work phase", "round": 3, "phase": "building", "at": at(60)},
        {"event": "run start", "kind": "worker", "round": 3, "id": "new-work", "at": at(60)},
        {"event": "run end", "kind": "worker", "round": 3, "run_id": "new-work", "at": at(65)},
    ], lambda at: [])
    assert current["total_seconds"] == 70
    assert current["time_breakdown"]["reviewing"] == 10
    assert current["time_breakdown"]["building"] == 5
    assert current["time_breakdown"]["nothing_running"] == 5


@pytest.mark.parametrize("upgraded", [False, True], ids=["historical-only", "after-upgrade"])
def test_16_historical_worker_question_without_end_stays_unknown(env, monkeypatch, upgraded):
    current = history(env, monkeypatch, lambda at: [
        {"event": "worker question", "round": 1, "question": "May I reuse the parser?", "at": at(0)},
        *([
            {"event": "work phase", "round": 3, "phase": "building", "at": at(60)},
            {"event": "run start", "kind": "worker", "round": 3, "id": "new-work", "at": at(60)},
            {"event": "run end", "kind": "worker", "round": 3, "run_id": "new-work", "at": at(65)},
        ] if upgraded else []),
    ], lambda at: [])
    assert current["time_breakdown"]["waiting_for_owner"] is None
    assert current["time_breakdown"]["nothing_running"] == (5 if upgraded else None)
    assert all("waiting for the owner" not in round_["line"] for round_ in current["rounds"])


@pytest.mark.parametrize("kind", ["task", "fix"])
def test_17_item_elapsed_time_uses_real_creation_before_any_activity_logs(env, monkeypatch, kind):
    began = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setenv("FORGE_NOW", began.isoformat())
    if kind == "task":
        item, _ = env.start_approved_task(STORY_DOC)
    else:
        created = env.repo.forge("fix", "start", "Measure idle", "--done", "Idle time is visible")
        assert created.returncode == 0, created.stderr
        item = "measure-idle"
    monkeypatch.setenv("FORGE_NOW", (began + timedelta(seconds=70)).isoformat())
    current = row(env.repo, item)
    assert current["total_seconds"] == 70
    assert all(value is None for value in current["time_breakdown"].values())
    assert current["rounds"] == []
