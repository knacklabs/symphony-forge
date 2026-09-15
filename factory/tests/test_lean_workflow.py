from __future__ import annotations

import hashlib
import json
import sys
import uuid
from pathlib import Path

import pytest

from test_gates import (  # noqa: F401
    HARNESS, PLAN_BODY, _seed_cold_launch, intake, load_factory_lib,
    native_claude_approval, plan_draft, record_grill, repo, run, sign_off,
)

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from forge_cli import approval  # noqa: E402


def _codex_event(
    digest: str, choice: str = "Approve plan", *, async_: bool = False,
) -> dict:
    question_id = f"approve_plan_{digest}"
    question = f"Approve exact plan digest {digest}?"
    return {
        "tool_name": "request_user_input", "session_id": f"s-{uuid.uuid4().hex}",
        "tool_use_id": f"e-{uuid.uuid4().hex}", "async": async_,
        "tool_input": {"questions": [{
            "id": question_id, "header": "Approve plan", "question": question,
            "options": [{"label": value} for value in
                        ("Approve plan", "Request changes", "Stop")],
        }]},
        "tool_response": {"answers": {
            question_id: {"answers": [choice]},
        }},
    }


def _awaiting_story(repo: Path, tmp_path: Path) -> tuple[Path, str]:
    sign_off(repo)
    code, out = intake(repo)
    assert code == 0, out
    source = tmp_path / "lean-plan.md"
    source.write_text(plan_draft(repo), encoding="utf-8")
    code, out = record_grill(repo, "plan", digest_of=source)
    assert code == 0, out
    code, out = run(repo, "forge.py", "plan", "save", "--from", str(source),
                    "--story", "ENG-1")
    assert code == 0 and "awaiting-approval" in out, out
    lib = load_factory_lib(repo)
    state = json.loads(lib.run_state_path(repo).read_text())
    plan = repo / state["plan_file"]
    return plan, lib.plan_digest_without_assumptions(plan)


def test_native_plan_mode_approval_records_exact_digest_for_claude_exit_plan_mode(
        repo: Path, tmp_path: Path):
    plan, digest = _awaiting_story(repo, tmp_path)
    record = approval.record_native_approval(
        repo, native_claude_approval(repo), runtime="claude")
    assert record["approved_plan_sha256"] == digest
    assert "status: approved" in plan.read_text()
    assert json.loads(load_factory_lib(repo).run_state_path(repo).read_text())[
        "approved_plan_sha256"] == digest


def test_native_plan_mode_approval_records_exact_digest_for_codex_sync_approval(
        repo: Path, tmp_path: Path):
    plan, digest = _awaiting_story(repo, tmp_path)
    record = approval.record_native_approval(
        repo, _codex_event(digest), runtime="codex")
    assert record["approved_plan_sha256"] == digest
    assert record["approved_by"] == "human-via-Codex"
    assert "status: approved" in plan.read_text()


def test_native_approval_refuses_stale_wrong_runtime_canceled_async_and_unsupported_payloads(
        repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _plan, digest = _awaiting_story(repo, tmp_path)
    candidate = approval.eligible_candidates(repo)[0]
    monkeypatch.setattr(approval, "eligible_candidates", lambda _base: [candidate])
    cancelled = _codex_event(digest)
    cancelled["tool_response"]["cancelled"] = True
    failed = _codex_event(digest)
    failed["tool_response"]["is_error"] = True
    cases = [
        ({**native_claude_approval(repo),
          "tool_input": {"plan": "# stale plan\n"}}, "claude"),
        (native_claude_approval(repo), "codex"),
        ({**native_claude_approval(repo), "cancelled": True}, "claude"),
        (_codex_event(digest, async_=True), "codex"),
        ({**_codex_event(digest), "cancelled": True}, "codex"),
        (cancelled, "codex"),
        (failed, "codex"),
        ({**_codex_event(digest), "tool_name": "optional_question"}, "codex"),
    ]
    for event, runtime in cases:
        with pytest.raises(approval.ApprovalRefused):
            approval.record_native_approval(repo, event, runtime=runtime)
    assert approval.eligible_candidates(repo)[0].digest == digest


def test_normal_flow_no_longer_requires_requirements_grill_manual_approval_or_second_save(
        repo: Path, tmp_path: Path):
    plan, digest = _awaiting_story(repo, tmp_path)
    approval.record_native_approval(
        repo, native_claude_approval(repo), runtime="claude")
    state = json.loads(load_factory_lib(repo).run_state_path(repo).read_text())
    assert state["plan_status"] == "approved"
    assert state["approved_plan_sha256"] == digest
    assert not (repo / ".factory/grills/requirements.json").exists()
    code, out = run(repo, "forge.py", "plan", "approve", "--by", "Nobody")
    assert code != 0 and "invalid choice" in out
    assert "status: approved" in plan.read_text()


def test_one_cold_grill_full_disposition_replaces_round_floors_and_frontier_fake(
        repo: Path, tmp_path: Path):
    sign_off(repo)
    intake(repo)
    draft = tmp_path / "amended.md"
    draft.write_text(plan_draft(repo), encoding="utf-8")
    cold = hashlib.sha256(draft.read_text().encode()).hexdigest()
    _seed_cold_launch(repo, "plan", cold)
    draft.write_text(plan_draft(repo, PLAN_BODY + "\nResolved repository fact.\n"),
                     encoding="utf-8")
    finding = "The repository fact is not stated."
    payload = {
        "generated_by": "griller", "gate": "plan", "verdict": "pass",
        "gaps": [finding], "contradictions": [],
        "resolutions": ["Added the repository fact."],
        "finding_dispositions": [{
            "finding": finding, "resolution": "Added the repository fact.",
            "source": "factory/scripts/record_grill_from_json.py",
        }],
        "amendments": [{
            "change": "Added the repository fact.",
            "reason": "Closes the cold-reader finding.",
            "source": "factory/scripts/record_grill_from_json.py",
        }],
    }
    code, out = run(repo, "record_grill_from_json.py", "--gate", "plan",
                    "--input-digest", str(draft), stdin=json.dumps(payload))
    assert code == 0, out
    stored = json.loads((repo / ".factory/stories/ENG-1/grills/plan.json").read_text())
    assert stored["cold_input_sha256"] == cold
    assert stored["final_artifact_sha256"] != cold
    assert "frontier_empty" not in stored and "rounds" not in stored


@pytest.mark.parametrize(("tamper", "message"), [
    ("process", "lifecycle is not authentic"),
    ("write", "lifecycle is not authentic"),
    ("argv", "argv identity is invalid"),
    ("result", "result is unavailable"),
])
def test_cold_grill_requires_an_authentic_read_only_launch(
        repo: Path, tmp_path: Path, tamper: str, message: str):
    sign_off(repo)
    intake(repo)
    draft = tmp_path / "plan.md"
    draft.write_text(plan_draft(repo), encoding="utf-8")
    _seed_cold_launch(repo, "plan", hashlib.sha256(draft.read_bytes()).hexdigest())
    from forge_cli.delegate import delegations_path
    ledger = delegations_path(repo)
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    if tamper == "process":
        rows[-1]["pid"] += 1
    elif tamper == "write":
        for row in rows:
            row["write"] = True
    elif tamper == "argv":
        for row in rows:
            row["argv"].append("--unexpected")
    else:
        for row in rows:
            row["output_path"] = str(tmp_path / "missing-result.log")
    ledger.write_text("".join(json.dumps(row) + "\n" for row in rows),
                      encoding="utf-8")
    payload = {
        "generated_by": "griller", "gate": "plan", "verdict": "pass",
        "gaps": [], "contradictions": [], "resolutions": [],
        "finding_dispositions": [],
    }
    code, output = run(
        repo, "record_grill_from_json.py", "--gate", "plan",
        "--input-digest", str(draft), stdin=json.dumps(payload),
    )
    assert code != 0 and message in output


def test_recovery_override_removes_round_ledgers_without_losing_cold_read_proof(
        repo: Path):
    assert not (repo / "factory/schemas/grill-round.json").exists()
    assert not (repo / "factory/schemas/plan-mode-marker.json").exists()
    assert not (repo / "factory/scripts/forge_cli/ceremony.py").exists()
    schema = json.loads((repo / "factory/schemas/grill.json").read_text())
    assert "cold_input_sha256" in schema["optional"]
    assert "finding_dispositions" in schema["required"]
