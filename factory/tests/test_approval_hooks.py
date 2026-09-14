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
    digest = lib.plan_digest_without_assumptions(plan)
    lib.dump_json(
        lib.evidence_path(
            repo, "APPROVE-1", "grills/plan.json", for_write=True,
        ),
        {
            "verdict": "pass", "commit": lib.head_sha(repo),
            "issue": "APPROVE-1", "input_sha256": digest,
        },
    )
    candidate = approval._story_candidate(repo)
    assert candidate is not None
    return candidate


def test_awaiting_story_edit_is_ineligible_until_its_plan_grill_matches(
        repo: Path):
    candidate = _story_candidate(repo)
    grill = candidate.evidence.parent / "grills" / "plan.json"
    original_grill = grill.read_bytes()
    candidate.path.write_text(
        candidate.path.read_text(encoding="utf-8") + "\nEdited before approval.\n",
        encoding="utf-8",
    )

    assert approval._story_candidate(repo) is None
    assert grill.read_bytes() == original_grill


def test_approved_story_edit_is_the_only_candidate_and_rebinds_atomically(
        repo: Path):
    candidate = _story_candidate(repo)
    original = approval.record_native_approval(
        repo, _event(), runtime="claude",
    )
    candidate.path.write_text(
        candidate.path.read_text(encoding="utf-8") + "\nApproved amendment.\n",
        encoding="utf-8",
    )
    lib = load_factory_lib(repo)
    amended_digest = lib.plan_digest_without_assumptions(candidate.path)
    candidates = approval.eligible_candidates(repo)
    assert [(row.kind, row.digest) for row in candidates] == [
        ("story", amended_digest),
    ]

    stale = {**_event(), "digest": original["approved_plan_sha256"]}
    with pytest.raises(approval.ApprovalRefused, match="digest is stale"):
        approval.record_native_approval(repo, stale, runtime="claude")
    cancelled = {**_event(), "cancelled": True}
    with pytest.raises(approval.ApprovalRefused, match="unsuccessful"):
        approval.record_native_approval(repo, cancelled, runtime="claude")
    state = json.loads(lib.run_state_path(repo).read_text())
    assert state["approved_plan_sha256"] == original["approved_plan_sha256"]

    amended = approval.record_native_approval(
        repo, _event(), runtime="claude",
    )
    state = json.loads(lib.run_state_path(repo).read_text())
    assert amended["approved_plan_sha256"] == amended_digest
    assert state["approved_plan_sha256"] == amended_digest
    assert "status: approved" in candidate.path.read_text(encoding="utf-8")
    assert json.loads(candidate.evidence.read_text())["approved_plan_sha256"] \
        == amended_digest


def test_task_approval_waits_for_story_approval_and_decomposition_rebinding(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    story = _story_candidate(repo)
    approval.record_native_approval(repo, _event(), runtime="claude")
    lib = load_factory_lib(repo)
    task = {"id": "T1"}
    monkeypatch.setattr(
        approval, "task_frontier_state", lambda _base: ("await-approval", task),
    )
    task_plan = lib.evidence_path(
        repo, "APPROVE-1", "task-plans/T1.md", for_write=True,
    )
    task_plan.parent.mkdir(parents=True, exist_ok=True)
    task_plan.write_text("# Task plan\n", encoding="utf-8")
    task_digest = lib.plan_digest_without_assumptions(task_plan)
    task_grill = lib.evidence_path(
        repo, "APPROVE-1", "grills/tasks/T1.json", for_write=True,
    )
    lib.dump_json(task_grill, {
        "verdict": "pass", "task_plan_sha256": task_digest,
    })
    decomposition = lib.protected_decomposition_state_path(repo)
    decomposition.unlink(missing_ok=True)

    assert approval._task_candidate(repo) is None
    story_digest = lib.plan_digest_without_assumptions(story.path)
    lib.dump_json(decomposition, {
        "plan_sha256": story_digest, "tasks": [task],
    })
    assert approval._task_candidate(repo) is not None

    story.path.write_text(
        story.path.read_text(encoding="utf-8") + "\nAnother amendment.\n",
        encoding="utf-8",
    )
    assert approval._task_candidate(repo) is None
    assert [row.kind for row in approval.eligible_candidates(repo)] == ["story"]


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
