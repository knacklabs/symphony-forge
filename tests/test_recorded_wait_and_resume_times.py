"""Command proof of dated holds, decisions, repairs and unexplained gaps.

Audit: existing history tests accept inferred idle time and do not inspect a
decision followed by a delayed worker resume. This owns that lifecycle contract.
Only external review and worker services are faked; no production seam is added.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from test_close import CLEAN, blocked, body, env, finding  # noqa: F401
from test_item_time_history import row
from test_worker import install_claude

STORY = "FIX-EXACT-WAIT-TIMES"


def test_1_hold_decision_and_resume_keep_their_times_and_gaps_stay_unmeasured(env, monkeypatch):
    began = datetime(2026, 11, 18, tzinfo=timezone.utc)
    at = lambda seconds: (began + timedelta(seconds=seconds)).isoformat()
    monkeypatch.setenv("FORGE_NOW", at(0))
    item, where = env.start_fix(steps=[{"step": "start", "at": at(0)}])
    install_claude(env.repo)
    env.reviews(blocked(finding("P1", "Basket disappears")))
    monkeypatch.setenv("FORGE_NOW", at(30))
    held = env.close(item)
    assert held.returncode == 1, held.stdout + held.stderr
    monkeypatch.setenv("FORGE_NOW", at(90))
    decided = env.close(item, "--resolve", "more", "--reason", "Keep the basket")
    assert decided.returncode == 0, decided.stdout + decided.stderr
    monkeypatch.setenv("FORGE_NOW", at(120))
    # The external worker consumes a minute on the controlled wall clock.
    clock = env.tmp / "wall-clock"
    clock.write_text(at(120), "utf-8")
    shim = env.repo.bin / "forge"
    original = shim.read_text("utf-8")
    shim.write_text(original.replace("from forge.cli import main",
        "from forge import repo\nfrom pathlib import Path\n"
        f"repo.now = lambda: Path({clock.as_posix()!r}).read_text('utf-8')\n"
        "from forge.cli import main"), "utf-8")
    sdk = env.repo.bin / "claude_agent_sdk/__init__.py"
    sdk.write_text(sdk.read_text("utf-8").replace(
        'yield SystemMessage("init",',
        f'Path({clock.as_posix()!r}).write_text({at(180)!r}, "utf-8")\n    yield SystemMessage("init",'), "utf-8")
    worked = env.repo.forge("work", item)
    shim.write_text(original, "utf-8")
    assert worked.returncode == 0, worked.stdout + worked.stderr
    env.commit(where, "app.py", "print('basket stays')\n")
    monkeypatch.setenv("FORGE_NOW", at(240))
    env.reviews(CLEAN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    current = row(env.repo, item)
    assert not any(span["category"] == "nothing_running" for span in current["intervals"])
    # Monotonic review duration can extend a few seconds beyond the controlled timestamp.
    assert current["time_breakdown"]["waiting_for_owner"] == pytest.approx(60, abs=5)
    assert current["time_breakdown"]["fixing_findings"] == 60
    assert current["unknown_seconds"] >= 90
    published = body(env.gh_calls("pr", "edit")[-1])
    for label, stamp in (("On hold", at(30)), ("Owner decision", at(90)), ("Resumed", at(120))):
        assert f"{label}: {stamp}" in published
    assert "nothing running" not in published
    # Durable steps travel with the branch even when local timing logs disappear.
    state = json.loads((where / f".factory/fixes/{item}.json").read_text("utf-8"))
    assert [(s["step"], s["at"]) for s in state["steps"] if s["step"] in
            ("hold", "owner decision", "resume")] == [
        ("hold", at(30)), ("owner decision", at(90)), ("resume", at(120))]


def test_2_recorded_worker_repairs_belong_to_the_later_review_attempt(env, monkeypatch):
    # These are the public history inputs left by one worker that calls close twice.
    # Existing two-close coverage checks findings, but never accounts for repair time.
    began = datetime(2026, 11, 18, tzinfo=timezone.utc)
    at = lambda seconds: (began + timedelta(seconds=seconds)).isoformat()
    item, _ = env.start_fix(steps=[{"step": "start", "at": at(0)}])
    events = [
        {"event": "work phase", "phase": "building", "at": at(0)},
        {"event": "run start", "kind": "worker", "id": "worker", "at": at(0)},
        {"event": "run start", "kind": "review", "id": "review-one", "at": at(10)},
        {"event": "run end", "kind": "review", "run_id": "review-one", "at": at(20)},
        {"event": "review result", "outcome": "blocked", "review_round": 1, "findings": [], "at": at(20)},
        {"event": "run start", "kind": "review", "id": "review-two", "at": at(80)},
        {"event": "run end", "kind": "review", "run_id": "review-two", "at": at(90)},
        {"event": "review result", "outcome": "clean", "review_round": 2, "findings": [], "at": at(90)},
        {"event": "run end", "kind": "worker", "run_id": "worker", "at": at(90)},
        {"event": "item finished", "at": at(90)},
    ]
    env.repo.write(".git/forge/events.jsonl", "".join(json.dumps(
        {"item": item, "round": 1, "id": f"event-{index}", **event}) + "\n"
        for index, event in enumerate(events)))
    monkeypatch.setenv("FORGE_NOW", at(90))
    current = row(env.repo, item)
    assert current["time_breakdown"]["building"] == 10
    assert current["time_breakdown"]["fixing_findings"] == 60
    assert [r["seconds"]["work"] for r in current["rounds"]] == [20, 70]
