from __future__ import annotations

import hashlib
import json
import sys
import uuid
from pathlib import Path

import pytest

from test_gates import (  # noqa: F401
    HARNESS, intake, load_factory_lib, repo, run, save_plan, sign_off,
    story_state,
)

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from forge_cli import approval  # noqa: E402


def _event(candidate: approval.ApprovalCandidate, runtime: str = "claude") -> dict:
    common = {
        "session_id": f"session-{uuid.uuid4().hex}",
        "tool_use_id": f"event-{uuid.uuid4().hex}",
    }
    if runtime == "claude":
        return {**common, "tool_name": "ExitPlanMode",
                "tool_input": {"plan": candidate.path.read_text(encoding="utf-8")},
                "tool_response": {"status": "success"}}
    question_id = f"approve_plan_{candidate.digest}"
    question = f"Approve exact plan digest {candidate.digest}?"
    return {
        **common,
        "tool_name": "request_user_input",
        "tool_input": {"questions": [{
            "id": question_id, "header": "Approve plan", "question": question,
            "options": [
                {"label": "Approve plan"},
                {"label": "Request changes"},
                {"label": "Stop"},
            ],
        }]},
        "tool_response": {
            "answers": {question_id: {"answers": ["Approve plan"]}},
        },
    }


def _story_candidate(repo: Path, story: str = "APPROVE-1") -> approval.ApprovalCandidate:
    lib = load_factory_lib(repo)
    plan = repo / "plans" / "active" / f"{story}-plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("---\nstatus: awaiting-approval\n---\n\n# Plan\n", encoding="utf-8")
    lib.dump_json(lib.run_state_path(repo), {
        "issue_key": story, "story": story,
        "plan_status": "awaiting-approval",
        "plan_file": plan.relative_to(repo).as_posix(),
    })
    digest = lib.plan_digest_without_assumptions(plan)
    lib.dump_json(
        lib.evidence_path(
            repo, story, "grills/plan.json", for_write=True,
        ),
        {
            "verdict": "pass", "commit": lib.head_sha(repo),
            "issue": story, "input_sha256": digest,
            "cold_input_sha256": digest,
            "final_artifact_sha256": digest,
            "finding_dispositions": [],
        },
    )
    candidate = approval._story_candidate(repo)
    assert candidate is not None
    return candidate


@pytest.mark.parametrize("body", ["{not json\n", "[]\n"])
def test_native_approval_malformed_run_state_is_a_controlled_refusal(
        repo: Path, body: str):
    lib = load_factory_lib(repo)
    path = lib.run_state_path(repo)
    path.write_text(body, encoding="utf-8")
    with pytest.raises(approval.ApprovalRefused, match="run state"):
        approval.eligible_candidates(repo)


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


def test_native_approval_revalidates_candidate_before_first_mutation(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    candidate = _story_candidate(repo)
    event = _event(candidate)
    calls = 0

    def changing_candidates(_base: Path):
        nonlocal calls
        calls += 1
        return [candidate] if calls == 1 else []

    monkeypatch.setattr(approval, "eligible_candidates", changing_candidates)
    with pytest.raises(approval.ApprovalRefused, match="changed before publication"):
        approval.record_native_approval(repo, event, runtime="claude")
    assert not (candidate.evidence.parent / "approval-events").exists()
    assert "status: awaiting-approval" in candidate.path.read_text(encoding="utf-8")


def test_phase_refuses_approved_status_without_native_approval_authority(
        repo: Path):
    from forge_cli.phase import (
        _approved_plan_authority_state, _approved_plan_changed,
    )

    candidate = _story_candidate(repo)
    approval.record_native_approval(repo, _event(candidate), runtime="claude")
    lib = load_factory_lib(repo)
    state = json.loads(lib.run_state_path(repo).read_text(encoding="utf-8"))
    assert _approved_plan_changed(repo, state) is False
    authority_bytes = candidate.evidence.read_bytes()
    candidate.evidence.unlink()
    assert _approved_plan_changed(repo, state) is False
    assert _approved_plan_authority_state(repo, state) == "repair"
    lib.dump_json(candidate.evidence, {
        "approved_plan_sha256": candidate.digest,
        "approver": "Legacy Human",
        "at": "2026-01-01T00:00:00+00:00",
    })
    assert _approved_plan_authority_state(repo, state) == "upgrade"
    candidate.evidence.write_bytes(authority_bytes)
    candidate.path.write_text(
        candidate.path.read_text(encoding="utf-8") + "\nChanged bytes.\n",
        encoding="utf-8",
    )
    assert _approved_plan_authority_state(repo, state) == "changed"


@pytest.mark.parametrize("body", [b"\xff", b"[]\n"])
def test_forge_next_routes_malformed_plan_approval_to_authority_repair(
        repo: Path, tmp_path: Path, body: bytes):
    sign_off(repo)
    intake(repo)
    code, out = save_plan(repo, tmp_path)
    assert code == 0, out
    (story_state(repo) / "plan-approval.json").write_bytes(body)
    code, out = run(repo, "forge.py", "next")
    assert code == 0, out
    assert "planning authority repair required" in out


def test_story_approval_refuses_unknown_runtime_even_with_matching_replay(
        repo: Path):
    candidate = _story_candidate(repo)
    record = approval.record_native_approval(
        repo, _event(candidate), runtime="claude",
    )
    lib = load_factory_lib(repo)
    old_replay = next(
        path for path in candidate.evidence.parent.glob(
            "approval-events/*.json")
        if json.loads(path.read_text()).get("event_id") == record["event_id"]
    )
    forged = dict(record)
    forged["runtime"] = "unknown"
    forged.pop("approved_by")
    replay_key = hashlib.sha256(
        f"unknown\0{record['session_id']}\0{record['event_id']}".encode()
    ).hexdigest()
    old_replay.unlink()
    replay = old_replay.parent / f"{replay_key}.json"
    lib.dump_json(replay, forged)
    lib.dump_json(candidate.evidence, forged)
    assert not lib._native_story_approval_recorded(repo, candidate.story, forged)
    forged.pop("runtime")
    replay.unlink()
    replay_key = hashlib.sha256(
        f"None\0{record['session_id']}\0{record['event_id']}".encode()
    ).hexdigest()
    replay = old_replay.parent / f"{replay_key}.json"
    lib.dump_json(replay, forged)
    lib.dump_json(candidate.evidence, forged)
    assert not lib._native_story_approval_recorded(repo, candidate.story, forged)

    for runtime in ("claude", "codex"):
        control = _story_candidate(repo, story=f"CONTROL-{runtime}")
        stored = approval.record_native_approval(
            repo, _event(control, runtime), runtime=runtime,
        )
        assert lib._native_story_approval_recorded(
            repo, control.story, stored,
        )


def test_approved_story_edit_is_the_only_candidate_and_rebinds_atomically(
        repo: Path):
    candidate = _story_candidate(repo)
    original = approval.record_native_approval(
        repo, _event(candidate), runtime="claude",
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
    protected = lib.protected_decomposition_state_path(repo)
    authority_before = (
        candidate.path.read_bytes(),
        candidate.evidence.read_bytes(),
        lib.run_state_path(repo).read_bytes(),
        protected.read_bytes() if protected.is_file() else None,
        sorted(
            path.read_bytes()
            for path in (candidate.evidence.parent / "approval-events").glob("*.json")
        ),
    )

    stale = _event(candidates[0])
    stale["tool_input"] = {"plan": "# stale plan\n"}
    with pytest.raises(approval.ApprovalRefused, match="displayed digest is stale"):
        approval.record_native_approval(repo, stale, runtime="claude")
    cancelled = {**_event(candidates[0]), "cancelled": True}
    with pytest.raises(approval.ApprovalRefused, match="unsuccessful"):
        approval.record_native_approval(repo, cancelled, runtime="claude")
    assert (
        candidate.path.read_bytes(),
        candidate.evidence.read_bytes(),
        lib.run_state_path(repo).read_bytes(),
        protected.read_bytes() if protected.is_file() else None,
        sorted(
            path.read_bytes()
            for path in (candidate.evidence.parent / "approval-events").glob("*.json")
        ),
    ) == authority_before
    state = json.loads(lib.run_state_path(repo).read_text())
    assert state["approved_plan_sha256"] == original["approved_plan_sha256"]

    amended = approval.record_native_approval(
        repo, _event(candidates[0]), runtime="claude",
    )
    state = json.loads(lib.run_state_path(repo).read_text())
    assert amended["approved_plan_sha256"] == amended_digest
    assert amended["previous_approved_plan_sha256"] \
        == original["approved_plan_sha256"]
    assert state["approved_plan_sha256"] == amended_digest
    assert "status: approved" in candidate.path.read_text(encoding="utf-8")
    assert json.loads(candidate.evidence.read_text())["approved_plan_sha256"] \
        == amended_digest
    assert lib.approved_story_plan_predecessors(repo, amended_digest) == (
        original["approved_plan_sha256"],
    )

    replay = next(
        path for path in (candidate.evidence.parent / "approval-events").glob("*.json")
        if json.loads(path.read_text()) == amended
    )
    replay_bytes = replay.read_bytes()
    replay.write_text(json.dumps({**amended, "story": "OTHER"}))
    assert lib.approved_story_plan_predecessors(repo, amended_digest) == ()
    replay.write_bytes(replay_bytes)
    approval_bytes = candidate.evidence.read_bytes()
    candidate.evidence.write_text("[]\n", encoding="utf-8")
    assert lib.approved_story_plan_predecessors(repo, amended_digest) == ()
    candidate.evidence.write_bytes(approval_bytes)
    replay.write_text("[]\n", encoding="utf-8")
    assert lib.approved_story_plan_predecessors(repo, amended_digest) == ()
    replay.write_bytes(replay_bytes)


def test_task_approval_waits_for_story_approval_and_decomposition_rebinding(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    story = _story_candidate(repo)
    approval.record_native_approval(repo, _event(story), runtime="claude")
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
        "cold_input_sha256": task_digest,
        "final_artifact_sha256": task_digest,
        "finding_dispositions": [],
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


def test_task_approval_requires_exact_approval_frontier(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    story = _story_candidate(repo)
    approval.record_native_approval(repo, _event(story), runtime="claude")
    lib = load_factory_lib(repo)
    task = {"id": "T1"}
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
        "cold_input_sha256": task_digest,
        "final_artifact_sha256": task_digest,
        "finding_dispositions": [],
    })
    lib.dump_json(lib.protected_decomposition_state_path(repo), {
        "plan_sha256": story.digest, "tasks": [task],
    })
    before = task_grill.read_bytes()

    for action in ("grill", "author-task-plan", "stage-start", "delegate"):
        monkeypatch.setattr(
            approval, "task_frontier_state", lambda _base, value=action: (value, task),
        )
        assert approval._task_candidate(repo) is None
        assert task_grill.read_bytes() == before


def test_native_approval_refuses_zero_multiple_candidates_replay_and_missing_identity(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    candidate = _story_candidate(repo)
    monkeypatch.setattr(approval, "eligible_candidates", lambda _base: [])
    with pytest.raises(approval.ApprovalRefused, match="found 0"):
        approval.record_native_approval(repo, _event(candidate), runtime="claude")

    monkeypatch.setattr(
        approval, "eligible_candidates", lambda _base: [candidate, candidate])
    with pytest.raises(approval.ApprovalRefused, match="found 2"):
        approval.record_native_approval(repo, _event(candidate), runtime="claude")

    monkeypatch.setattr(approval, "eligible_candidates", lambda _base: [candidate])
    missing = _event(candidate)
    missing.pop("tool_use_id")
    with pytest.raises(approval.ApprovalRefused, match="stable session and event"):
        approval.record_native_approval(repo, missing, runtime="claude")

    event = _event(candidate)
    approval.record_native_approval(repo, event, runtime="claude")
    with pytest.raises(approval.ApprovalRefused, match="already consumed"):
        approval.record_native_approval(repo, event, runtime="claude")


@pytest.mark.parametrize("status", ["", "pending", "unknown", "rejected"])
def test_claude_approval_requires_affirmative_success_without_mutation(
        repo: Path, status: str):
    candidate = _story_candidate(repo)
    event = _event(candidate)
    event["tool_response"]["status"] = status
    lib = load_factory_lib(repo)
    before = (candidate.path.read_bytes(), lib.run_state_path(repo).read_bytes())

    with pytest.raises(approval.ApprovalRefused, match="unsuccessful"):
        approval.record_native_approval(repo, event, runtime="claude")

    assert (candidate.path.read_bytes(), lib.run_state_path(repo).read_bytes()) == before
    assert not candidate.evidence.exists()


@pytest.mark.parametrize("status", ["success", "succeeded", "completed"])
def test_claude_approval_accepts_supported_success_statuses(repo: Path, status: str):
    candidate = _story_candidate(repo)
    event = _event(candidate)
    event["tool_response"]["status"] = status

    record = approval.record_native_approval(repo, event, runtime="claude")

    assert record["approved_plan_sha256"] == candidate.digest


@pytest.mark.parametrize("location", ["scoped", "archived", "legacy"])
def test_native_approval_refuses_cross_story_host_event_replay_without_mutation(
        repo: Path, location: str):
    if location != "legacy":
        (repo / ".factory" / "stories" / "APPROVE-1").mkdir(parents=True)
    first = _story_candidate(repo)
    event = _event(first)
    approval.record_native_approval(repo, event, runtime="claude")
    lib = load_factory_lib(repo)
    tombstone = next((first.evidence.parent / "approval-events").glob("*.json"))
    destination = tombstone
    if location in {"archived", "legacy"}:
        destination = (repo / ".factory" / "history" / first.story / "approval-events"
                       if location == "archived" else repo / ".factory" / "approval-events") / tombstone.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        tombstone.rename(destination)
    (repo / ".factory" / "stories" / "APPROVE-2").mkdir(parents=True)
    second = _story_candidate(repo, "APPROVE-2")
    assert second.digest == first.digest
    event["tool_input"]["plan"] = second.path.read_text(encoding="utf-8")
    before = (second.path.read_bytes(), lib.run_state_path(repo).read_bytes(),
              second.evidence.read_bytes() if second.evidence.exists() else None)
    with pytest.raises(approval.ApprovalRefused, match="already consumed"):
        approval.record_native_approval(repo, event, runtime="claude")
    assert (second.path.read_bytes(), lib.run_state_path(repo).read_bytes(),
            second.evidence.read_bytes() if second.evidence.exists() else None) == before
    assert not (repo / ".factory" / "stories" / second.story / "approval-events").exists()
    assert destination.is_file()


@pytest.mark.parametrize("runtime", ["claude", "codex"])
def test_native_approval_records_human_via_runtime_identity_without_display_name(
        repo: Path, monkeypatch: pytest.MonkeyPatch, runtime: str):
    candidate = _story_candidate(repo)
    monkeypatch.setattr(approval, "eligible_candidates", lambda _base: [candidate])
    event = _event(candidate, runtime)
    record = approval.record_native_approval(repo, event, runtime=runtime)
    assert record["approved_by"] == f"human-via-{runtime.capitalize()}"
    assert record["session_id"] == event["session_id"]
    assert record["event_id"] == event["tool_use_id"]
    assert "name" not in record


def test_codex_approval_uses_question_id_and_requires_displayed_digest(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    candidate = _story_candidate(repo)
    monkeypatch.setattr(approval, "eligible_candidates", lambda _base: [candidate])
    question_id = f"approve_plan_{candidate.digest}"
    malformed_answers = [
        {question_id: "Approve plan"},
        {question_id: {}},
        {question_id: {"answers": []}},
        {question_id: {"answers": ["Approve plan", "Approve plan"]}},
        {question_id: {"answers": [1]}},
        {question_id: {"answers": ["Request changes"]}},
        {"wrong-question-id": {"answers": ["Approve plan"]}},
    ]
    for answers in malformed_answers:
        event = _event(candidate, "codex")
        event["tool_response"]["answers"] = answers
        with pytest.raises(approval.ApprovalRefused, match="unsupported"):
            approval.record_native_approval(repo, event, runtime="codex")

    event = _event(candidate, "codex")
    event["tool_input"]["questions"][0]["question"] = "Approve this plan?"
    with pytest.raises(approval.ApprovalRefused, match="unsupported"):
        approval.record_native_approval(repo, event, runtime="codex")

    stale_digest = "0" * 64
    stale_id = f"approve_plan_{stale_digest}"
    event = _event(candidate, "codex")
    event["tool_input"]["questions"][0].update({
        "id": stale_id,
        "question": f"Approve exact plan digest {stale_digest}?",
    })
    event["tool_response"]["answers"] = {
        stale_id: {"answers": ["Approve plan"]},
    }
    with pytest.raises(approval.ApprovalRefused, match="displayed digest is stale"):
        approval.record_native_approval(repo, event, runtime="codex")


@pytest.mark.parametrize("status", ["pending", "unknown", "rejected"])
def test_codex_approval_refuses_noncompleted_explicit_status_without_mutation(
        repo: Path, status: str):
    candidate = _story_candidate(repo)
    event = _event(candidate, "codex")
    event["tool_response"]["status"] = status
    lib = load_factory_lib(repo)
    before = (candidate.path.read_bytes(), lib.run_state_path(repo).read_bytes())

    with pytest.raises(approval.ApprovalRefused, match="unsuccessful"):
        approval.record_native_approval(repo, event, runtime="codex")

    assert (candidate.path.read_bytes(), lib.run_state_path(repo).read_bytes()) == before
    assert not candidate.evidence.exists()


@pytest.mark.parametrize("status", [None, "success", "succeeded", "completed"])
def test_codex_approval_accepts_missing_or_completed_status(
        repo: Path, status: str | None):
    candidate = _story_candidate(repo)
    event = _event(candidate, "codex")
    if status is not None:
        event["tool_response"]["status"] = status

    record = approval.record_native_approval(repo, event, runtime="codex")

    assert record["approved_plan_sha256"] == candidate.digest


def test_native_approval_reuses_existing_story_and_task_approval_storage(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    story = _story_candidate(repo)
    monkeypatch.setattr(approval, "eligible_candidates", lambda _base: [story])
    record = approval.record_native_approval(repo, _event(story), runtime="claude")
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
    task_record = approval.record_native_approval(
        repo, _event(task, "codex"), runtime="codex")
    stored = json.loads(grill.read_text())
    assert stored["approved_task_plan_sha256"] == task_record["approved_plan_sha256"]
    assert stored["approval_event_id"] == task_record["event_id"]
    lib = load_factory_lib(repo)
    task_row = {"id": "T1"}
    assert lib._task_plan_approval_matches_digest(
        repo, task_row, stored, task.digest)

    replay = next(
        path for path in (story.evidence.parent / "approval-events").glob("*.json")
        if json.loads(path.read_text()).get("task") == "T1"
    )
    replay_bytes = replay.read_bytes()
    replay.unlink()
    assert not lib._task_plan_approval_matches_digest(
        repo, task_row, stored, task.digest)
    replay.write_text("{not json\n", encoding="utf-8")
    assert not lib._task_plan_approval_matches_digest(
        repo, task_row, stored, task.digest)
    replay.write_bytes(b"\xff")
    assert not lib._task_plan_approval_matches_digest(
        repo, task_row, stored, task.digest)
    replay.write_bytes(replay_bytes)
    legacy = {
        "approved_task_plan_sha256": task.digest,
        "approved_by": "Legacy Human",
        "approved_at": "2026-01-01T00:00:00+00:00",
        "task_plan_sha256": task.digest,
    }
    assert not lib._task_plan_approval_matches_digest(
        repo, task_row, legacy, task.digest)


def test_story_approval_digest_requires_native_event_proof_without_backfill(
        repo: Path):
    candidate = _story_candidate(repo)
    lib = load_factory_lib(repo)
    state_path = lib.run_state_path(repo)
    state = json.loads(state_path.read_text())
    state.update(
        plan_status="approved", approved_plan_sha256=candidate.digest,
    )
    lib.dump_json(state_path, state)
    before = state_path.read_bytes()

    with pytest.raises(SystemExit, match="binding is missing"):
        lib.require_approved_plan_digest(repo)

    assert state_path.read_bytes() == before
    assert not candidate.evidence.exists()


@pytest.mark.parametrize("kind", ["absolute", "traversal", "symlink", "hardlink", "ancestor"])
def test_native_approval_refuses_unsafe_story_plan_without_external_write(repo, tmp_path, kind):
    import os
    candidate = _story_candidate(repo)
    event = _event(candidate)
    outside = tmp_path / "external-plan.md"
    original = candidate.path.read_bytes()
    outside.write_bytes(original)
    lib = load_factory_lib(repo)
    state_path = lib.run_state_path(repo)
    state = json.loads(state_path.read_text())
    if kind == "absolute":
        state["plan_file"] = str(outside)
    elif kind == "traversal":
        state["plan_file"] = os.path.relpath(outside, repo)
    elif kind == "ancestor":
        parent = repo / "linked-plans"
        parent.symlink_to(tmp_path, target_is_directory=True)
        state["plan_file"] = "linked-plans/external-plan.md"
    else:
        candidate.path.unlink()
        if kind == "symlink":
            candidate.path.symlink_to(outside)
        else:
            os.link(outside, candidate.path)
    lib.dump_json(state_path, state)
    before = state_path.read_bytes()
    with pytest.raises(approval.ApprovalRefused):
        approval.record_native_approval(repo, event, runtime="claude")
    assert outside.read_bytes() == original
    assert state_path.read_bytes() == before
    assert not candidate.evidence.exists()


def test_native_approval_rechecks_replaced_plan_before_publication(repo, tmp_path, monkeypatch):
    candidate = _story_candidate(repo)
    event = _event(candidate)
    outside = tmp_path / "external-plan.md"
    outside.write_bytes(candidate.path.read_bytes())
    before = outside.read_bytes()
    original_approve = approval._approve_story

    def replace_before_write(base, selected, record):
        selected.path.unlink()
        selected.path.symlink_to(outside)
        original_approve(base, selected, record)

    monkeypatch.setattr(approval, "_approve_story", replace_before_write)
    with pytest.raises(approval.ApprovalRefused, match="non-linked"):
        approval.record_native_approval(repo, event, runtime="claude")
    assert outside.read_bytes() == before
    assert not candidate.evidence.exists()
    assert len(list((candidate.evidence.parent / "approval-events").glob("*.json"))) == 1


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "ancestor", "replay-ancestor"])
def test_native_approval_refuses_unsafe_authority_and_replay_destinations(
        repo: Path, tmp_path: Path, kind: str, monkeypatch: pytest.MonkeyPatch):
    import os

    (repo / ".factory" / "stories" / "APPROVE-1").mkdir(parents=True)
    candidate = _story_candidate(repo)
    monkeypatch.setattr(approval, "eligible_candidates", lambda _base: [candidate])
    event = _event(candidate)
    lib = load_factory_lib(repo)
    state_path = lib.run_state_path(repo)
    before = (candidate.path.read_bytes(), state_path.read_bytes())
    outside = tmp_path / "outside"
    outside.mkdir()
    external = outside / "authority.json"
    external.write_text('{"sentinel": true}\n', encoding="utf-8")

    if kind == "symlink":
        candidate.evidence.symlink_to(external)
    elif kind == "hardlink":
        os.link(external, candidate.evidence)
    elif kind == "ancestor":
        story_dir = candidate.evidence.parent
        backup = tmp_path / "story-backup"
        story_dir.rename(backup)
        story_dir.symlink_to(outside, target_is_directory=True)
    else:
        replay_dir = candidate.evidence.parent / "approval-events"
        replay_dir.symlink_to(outside, target_is_directory=True)

    with pytest.raises(approval.ApprovalRefused):
        approval.record_native_approval(repo, event, runtime="claude")

    assert (candidate.path.read_bytes(), state_path.read_bytes()) == before
    assert external.read_text(encoding="utf-8") == '{"sentinel": true}\n'


@pytest.mark.parametrize("kind", ["symlink", "hardlink"])
def test_native_task_approval_refuses_unsafe_grill_destination(
        repo: Path, tmp_path: Path, kind: str, monkeypatch: pytest.MonkeyPatch):
    import os

    plan = repo / ".factory" / "task.md"
    plan.write_text("# task\n", encoding="utf-8")
    grill = repo / ".factory" / "task-grill.json"
    outside = tmp_path / "task-grill.json"
    outside.write_text('{"verdict":"pass"}\n', encoding="utf-8")
    if kind == "symlink":
        grill.symlink_to(outside)
    else:
        os.link(outside, grill)
    task = approval.ApprovalCandidate(
        "task", "APPROVE-1", "T1", plan,
        load_factory_lib(repo).plan_digest_without_assumptions(plan), grill,
    )
    monkeypatch.setattr(approval, "eligible_candidates", lambda _base: [task])
    before = outside.read_bytes()

    with pytest.raises(approval.ApprovalRefused, match="destination"):
        approval.record_native_approval(
            repo, _event(task, "codex"), runtime="codex")

    assert outside.read_bytes() == before


def test_native_story_approval_refuses_unsafe_run_state_without_tombstone(
        repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    candidate = _story_candidate(repo)
    monkeypatch.setattr(approval, "eligible_candidates", lambda _base: [candidate])
    lib = load_factory_lib(repo)
    state = lib.run_state_path(repo)
    saved = state.read_bytes()
    outside = tmp_path / "outside-run.json"
    outside.write_bytes(saved)
    state.unlink()
    state.symlink_to(outside)
    plan_before = candidate.path.read_bytes()

    with pytest.raises(approval.ApprovalRefused, match="destination"):
        approval.record_native_approval(
            repo, _event(candidate), runtime="claude")

    assert candidate.path.read_bytes() == plan_before
    assert outside.read_bytes() == saved
    assert not candidate.evidence.exists()
    assert not list(candidate.evidence.parent.glob("approval-events/*.json"))
