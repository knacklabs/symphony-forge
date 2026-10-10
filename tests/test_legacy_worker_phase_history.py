"""A legacy worker ordinal alone cannot establish what the worker was doing.

Test-audit: a first worker may fix a blocked manual change. Existing legacy
proofs use unknown worker ordinals, so they miss the round-one building guess.
Historical JSONL is the earlier recorder's input contract; real board and close
commands own classification and publication, with no production seam.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from test_close import body, env  # noqa: F401
from test_close_holds_after_three_blocked_reviews import client_item
from test_item_time_history import row

STORY = "FIX-WHERE-TIME-WENT"


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "earlier-adoption"])
@pytest.mark.parametrize("source", ["timing", "worker-event", "work-event"])
def test_26_legacy_first_worker_phase_stays_unknown_until_recorded(
        env, tmp_path, monkeypatch, previous, source):
    began = datetime(2026, 1, 1, tzinfo=timezone.utc)
    at = lambda seconds: (began + timedelta(seconds=seconds)).isoformat()
    monkeypatch.setenv("FORGE_NOW", at(0))
    item, where = client_item(env, tmp_path, previous)
    if previous:
        allowed = env.repo.forge("fix", "allow-large", "Sync the earlier adoption", cwd=where)
        assert allowed.returncode == 0, allowed.stderr
    # Earlier worker producers recorded ordinals but no activity phase.
    events = []
    if source != "timing":
        kind = "work" if source == "work-event" else "worker"
        events = [
            {"event": "run start", "kind": kind, "round": 1, "id": "legacy-worker", "at": at(0)},
            {"event": "run end", "kind": kind, "round": 1, "id": "legacy-end",
             "run_id": "legacy-worker", "at": at(7)},
        ]
    timings = [{"step": "worker round", "round": 1, "start": at(0),
                "seconds": 7, "outcome": "completed"}] if source == "timing" else []
    diagnostic = env.repo.path / ".git/forge"
    diagnostic.mkdir(exist_ok=True)
    for name, records in (("events", events), ("timings", timings)):
        (diagnostic / f"{name}.jsonl").write_text("".join(
            json.dumps({"item": item, **record}) + "\n" for record in records), "utf-8")
    monkeypatch.setenv("FORGE_NOW", at(10))

    current = row(env.repo, item)
    assert current["time_breakdown"]["building"] is None
    assert current["time_breakdown"]["fixing_findings"] is None
    first = current["rounds"][0]
    assert first["worker_round"] == 1
    if source == "timing":
        assert "unknown completed (unknown)" in first["line"], first["line"]
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    published = body(env.gh_calls("pr", "edit")[-1])
    assert "building: unknown" in published
    assert "fixing findings: unknown" in published
    if source == "timing":
        assert "unknown completed (unknown)" in published
