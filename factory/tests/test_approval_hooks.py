from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest

from test_gates import HARNESS, load_factory_lib, repo  # noqa: F401

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from forge_cli import approval  # noqa: E402


def _event(runtime: str = "claude") -> dict:
    common = {
        "session_id": f"session-{uuid.uuid4().hex}",
        "tool_use_id": f"event-{uuid.uuid4().hex}",
    }
    if runtime == "claude":
        return {**common, "tool_name": "ExitPlanMode",
                "tool_response": {"status": "success"}}
    question = "Approve this exact plan?"
    return {
        **common,
        "tool_name": "request_user_input",
        "tool_input": {"questions": [{
            "header": "Approve plan", "question": question,
            "options": [
                {"label": "Approve plan"},
                {"label": "Request changes"},
                {"label": "Stop"},
            ],
        }]},
        "tool_response": {"answers": {question: "Approve plan"}},
    }


def _story_candidate(repo: Path) -> approval.ApprovalCandidate:
    lib = load_factory_lib(repo)
    plan = repo / "plans" / "active" / "APPROVE-1-plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("---\nstatus: awaiting-approval\n---\n\n# Plan\n", encoding="utf-8")
    lib.dump_json(lib.run_state_path(repo), {
        "issue_key": "APPROVE-1", "story": "APPROVE-1",
        "plan_status": "awaiting-approval",
        "plan_file": plan.relative_to(repo).as_posix(),
    })
    candidate = approval._story_candidate(repo)
    assert candidate is not None
    return candidate


def test_native_approval_refuses_zero_multiple_candidates_replay_and_missing_identity(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(approval, "eligible_candidates", lambda _base: [])
    with pytest.raises(approval.ApprovalRefused, match="found 0"):
        approval.record_native_approval(repo, _event(), runtime="claude")

    candidate = _story_candidate(repo)
    monkeypatch.setattr(
        approval, "eligible_candidates", lambda _base: [candidate, candidate])
    with pytest.raises(approval.ApprovalRefused, match="found 2"):
        approval.record_native_approval(repo, _event(), runtime="claude")

    monkeypatch.setattr(approval, "eligible_candidates", lambda _base: [candidate])
    missing = _event()
    missing.pop("tool_use_id")
    with pytest.raises(approval.ApprovalRefused, match="stable session and event"):
        approval.record_native_approval(repo, missing, runtime="claude")

    event = _event()
    approval.record_native_approval(repo, event, runtime="claude")
    with pytest.raises(approval.ApprovalRefused, match="already consumed"):
        approval.record_native_approval(repo, event, runtime="claude")


@pytest.mark.parametrize("runtime", ["claude", "codex"])
def test_native_approval_records_human_via_runtime_identity_without_display_name(
        repo: Path, monkeypatch: pytest.MonkeyPatch, runtime: str):
    candidate = _story_candidate(repo)
    monkeypatch.setattr(approval, "eligible_candidates", lambda _base: [candidate])
    event = _event(runtime)
    record = approval.record_native_approval(repo, event, runtime=runtime)
    assert record["approved_by"] == f"human-via-{runtime.capitalize()}"
    assert record["session_id"] == event["session_id"]
    assert record["event_id"] == event["tool_use_id"]
    assert "name" not in record


def test_native_approval_reuses_existing_story_and_task_approval_storage(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    story = _story_candidate(repo)
    monkeypatch.setattr(approval, "eligible_candidates", lambda _base: [story])
    record = approval.record_native_approval(repo, _event(), runtime="claude")
    assert json.loads(story.evidence.read_text())["approved_plan_sha256"] == record[
        "approved_plan_sha256"]

    plan = repo / ".factory" / "task.md"
    plan.write_text("# task\n", encoding="utf-8")
    grill = repo / ".factory" / "task-grill.json"
    grill.write_text('{"verdict":"pass"}\n', encoding="utf-8")
    task = approval.ApprovalCandidate(
        "task", "APPROVE-1", "T1", plan,
        load_factory_lib(repo).plan_digest_without_assumptions(plan), grill,
    )
    monkeypatch.setattr(approval, "eligible_candidates", lambda _base: [task])
    task_record = approval.record_native_approval(repo, _event("codex"), runtime="codex")
    stored = json.loads(grill.read_text())
    assert stored["approved_task_plan_sha256"] == task_record["approved_plan_sha256"]
    assert stored["approval_event_id"] == task_record["event_id"]
