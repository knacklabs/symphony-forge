from __future__ import annotations

import difflib
import hashlib
import json
import sys
import uuid
from pathlib import Path

import pytest

from test_gates import (  # noqa: F401
    HARNESS, PLAN_BODY, STAGE_TASK, _seed_cold_launch, _seed_task_cold_launch,
    intake, load_factory_lib,
    native_claude_approval, plan_draft, record_grill, repo, run,
    seed_task_grill_frontier, sign_off, write_stages,
)

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from forge_cli import approval  # noqa: E402
from forge_cli.grill import (  # noqa: E402
    _artifact_digest, _cold_artifact_from_brief, _compose_brief,
)


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


def _plan_metadata(repo: Path) -> dict:
    lib = load_factory_lib(repo)
    state = json.loads(lib.run_state_path(repo).read_text())
    story = state.get("story") or state["issue_key"]
    path = repo / ".factory" / "stories" / story / "plan-meta.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _amended_plan_payload(cold: str, final: str, finding: str) -> dict:
    cold_lines = cold.splitlines(keepends=True)
    final_lines = final.splitlines(keepends=True)
    delta = [{
        "cold_start": left_start, "cold_end": left_end,
        "cold": "".join(cold_lines[left_start:left_end]),
        "final_start": right_start, "final_end": right_end,
        "final": "".join(final_lines[right_start:right_end]),
    } for tag, left_start, left_end, right_start, right_end
        in difflib.SequenceMatcher(
            a=cold_lines, b=final_lines, autojunk=False,
        ).get_opcodes() if tag != "equal"]
    resolution = "Added the fact requested by the cold reader."
    return {
        "generated_by": "griller", "gate": "plan", "verdict": "pass",
        "gaps": [finding], "contradictions": [], "resolutions": [resolution],
        "finding_dispositions": [{
            "finding": finding, "resolution": resolution,
            "source": "factory/scripts/record_grill_from_json.py",
        }],
        "amendments": [{
            "delta_index": index, "findings": [finding],
            "change": "Added the requested plan detail.",
            "reason": "Closes the cold-reader finding.",
            "source": "factory/scripts/record_grill_from_json.py",
        } for index in range(len(delta))],
        "artifact_delta": delta,
    }


def test_saved_plan_routes_directly_to_native_approval_without_second_save(
        repo: Path, tmp_path: Path):
    plan, _ = _awaiting_story(repo, tmp_path)
    code, out = run(repo, "forge.py", "next")
    assert code == 0, out
    assert "PHASE: awaiting native plan approval" in out
    assert f"Display the exact saved plan bytes at {plan.relative_to(repo)}" in out
    assert "plan save" not in out


def test_native_plan_mode_approval_records_exact_digest_for_claude_exit_plan_mode(
        repo: Path, tmp_path: Path):
    _, digest = _awaiting_story(repo, tmp_path)
    event = native_claude_approval(repo)
    displayed = event["tool_input"]["plan"]
    event["tool_response"] = {"plan": displayed, "isAgent": False}
    rejected = {
        **event,
        "tool_response": {**event["tool_response"], "status": "rejected"},
    }
    with pytest.raises(approval.ApprovalRefused, match="unsuccessful"):
        approval.record_native_approval(repo, rejected, runtime="claude")
    pending = {
        **event,
        "tool_response": {**event["tool_response"], "status": "pending"},
    }
    with pytest.raises(approval.ApprovalRefused, match="unsuccessful"):
        approval.record_native_approval(repo, pending, runtime="claude")
    record = approval.record_native_approval(
        repo, event, runtime="claude")
    assert record["approved_plan_sha256"] == digest
    assert _plan_metadata(repo)["status"] == "approved"
    assert json.loads(load_factory_lib(repo).run_state_path(repo).read_text())[
        "approved_plan_sha256"] == digest


def test_review_identity_preserves_nested_domain_metadata_and_refuses_compound_tools(
        repo: Path):
    from forge_cli import stages

    value = {
        "commit": "recorder bookkeeping",
        "automated": {
            "generated_by": "implementer",
            "extension": {"commit": "security source", "at": "scan time"},
        },
    }
    assert stages._canonical_review_envelope(
        value, nested=frozenset({"automated"}),
    ) == {"automated": {"extension": {
        "at": "scan time", "commit": "security source",
    }}}
    canonical = stages._proof_tool_identity(
        repo, "python3 factory/scripts/verify.py",
    )
    assert canonical["reusable"] is False
    assert canonical["canonical_verify_inputs"]
    assert stages._proof_tool_identity(
        repo, "python3 -m pytest factory/tests/test_gates.py && git status",
    )["reusable"] is False


def test_review_identity_binds_task_grill_and_grouped_runner(repo: Path):
    from forge_cli import stages

    lib = load_factory_lib(repo)
    lib.dump_json(lib.run_state_path(repo), {"issue_key": "S1", "story": "S1"})
    plan = lib.evidence_path(repo, "S1", "task-plans/T1.md", for_write=True)
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("# exact task plan\n", encoding="utf-8")
    grill = lib.evidence_path(
        repo, "S1", "grills/tasks/T1.json", for_write=True,
    )
    lib.dump_json(grill, {
        "verdict": "pass", "approved_by": "human-via-Codex",
        "approved_at": "old", "commit": "old",
    })
    task = {"id": "T1", "acceptance_criteria": ["safe"]}
    stage = {"id": "T1"}
    first = stages.reviewed_meaning_identity(repo, stage, task)

    lib.dump_json(grill, {
        "verdict": "pass", "approved_by": "human-via-Codex",
        "approved_at": "new", "commit": "new",
    })
    assert stages.reviewed_meaning_identity(repo, stage, task) == first

    data = json.loads(grill.read_text())
    data["approved_by"] = "human-via-Claude"
    lib.dump_json(grill, data)
    assert stages.reviewed_meaning_identity(repo, stage, task) != first

    lib.dump_json(grill, {
        "verdict": "pass", "approved_by": "human-via-Codex",
    })
    grouped = repo / "factory/scripts/forge_cli/review_groups.py"
    grouped.write_text(grouped.read_text() + "\n# changed runner\n")
    assert stages.reviewed_meaning_identity(repo, stage, task) != first


def test_native_plan_mode_approval_records_exact_digest_for_codex_sync_approval(
        repo: Path, tmp_path: Path):
    _, digest = _awaiting_story(repo, tmp_path)
    record = approval.record_native_approval(
        repo, _codex_event(digest), runtime="codex")
    assert record["approved_plan_sha256"] == digest
    assert record["approved_by"] == "human-via-Codex"
    assert _plan_metadata(repo)["status"] == "approved"


def test_native_approval_refuses_stale_wrong_runtime_canceled_async_and_unsupported_payloads(
        repo: Path, tmp_path: Path):
    plan, digest = _awaiting_story(repo, tmp_path)
    lib = load_factory_lib(repo)
    run_path = lib.run_state_path(repo)
    candidate = approval.eligible_candidates(repo)[0]

    def authority_snapshot() -> tuple[bytes, bytes, tuple[bytes, ...], tuple]:
        approval_events = candidate.evidence.parent / "approval-events"
        frontier = tuple(
            (row.kind, row.story, row.task, row.path, row.digest, row.evidence)
            for row in approval.eligible_candidates(repo)
        )
        return (
            plan.read_bytes(), run_path.read_bytes(),
            tuple(path.read_bytes() for path in sorted(approval_events.glob("*.json"))),
            frontier,
        )

    before = authority_snapshot()
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
        assert authority_snapshot() == before
    assert approval.eligible_candidates(repo) == [candidate]
    assert candidate.digest == digest


def test_normal_flow_no_longer_requires_requirements_grill_manual_approval_or_second_save(
        repo: Path, tmp_path: Path):
    _, digest = _awaiting_story(repo, tmp_path)
    approval.record_native_approval(
        repo, native_claude_approval(repo), runtime="claude")
    state = json.loads(load_factory_lib(repo).run_state_path(repo).read_text())
    assert state["plan_status"] == "approved"
    assert state["approved_plan_sha256"] == digest
    assert not (repo / ".factory/grills/requirements.json").exists()
    code, out = run(repo, "forge.py", "plan", "approve", "--by", "Nobody")
    assert code != 0 and "invalid choice" in out
    assert _plan_metadata(repo)["status"] == "approved"


def test_one_cold_grill_full_disposition_replaces_round_floors_and_frontier_fake(
        repo: Path, tmp_path: Path):
    sign_off(repo)
    intake(repo)
    draft = tmp_path / "amended.md"
    draft.write_text(plan_draft(repo), encoding="utf-8")
    cold = hashlib.sha256(draft.read_text().encode()).hexdigest()
    finding = "The repository fact is not stated."
    cold_artifact = draft.read_text(encoding="utf-8")
    _seed_cold_launch(repo, "plan", cold, artifact_text=cold_artifact, findings={
        "gaps": [finding], "contradictions": [],
    })
    draft.write_text(plan_draft(repo, PLAN_BODY + "\nResolved repository fact.\n"),
                     encoding="utf-8")
    final_artifact = draft.read_text(encoding="utf-8")
    cold_lines = cold_artifact.splitlines(keepends=True)
    final_lines = final_artifact.splitlines(keepends=True)
    delta = [{
        "cold_start": a, "cold_end": b, "cold": "".join(cold_lines[a:b]),
        "final_start": c, "final_end": d, "final": "".join(final_lines[c:d]),
    } for tag, a, b, c, d in difflib.SequenceMatcher(
        a=cold_lines, b=final_lines, autojunk=False).get_opcodes()
        if tag != "equal"]
    payload = {
        "generated_by": "griller", "gate": "plan", "verdict": "pass",
        "gaps": [finding], "contradictions": [],
        "resolutions": ["Added the repository fact."],
        "finding_dispositions": [{
            "finding": finding, "resolution": "Added the repository fact.",
            "source": "factory/scripts/record_grill_from_json.py",
        }],
        "amendments": [{
            "delta_index": 0, "findings": [finding],
            "change": "Added the repository fact.",
            "reason": "Closes the cold-reader finding.",
            "source": "factory/scripts/record_grill_from_json.py",
        }],
        "artifact_delta": delta,
    }
    code, out = run(repo, "record_grill_from_json.py", "--gate", "plan",
                    "--input-digest", str(draft), stdin=json.dumps(payload))
    assert code == 0, out
    stored = json.loads((repo / ".factory/stories/ENG-1/grills/plan.json").read_text())
    assert stored["cold_input_sha256"] == cold
    assert stored["final_artifact_sha256"] != cold
    assert "frontier_empty" not in stored and "rounds" not in stored


def test_cold_to_final_amendment_map_refuses_missing_duplicate_unbound_and_unexplained(
        repo: Path, tmp_path: Path):
    sign_off(repo)
    intake(repo)
    draft = tmp_path / "bridge.md"
    draft.write_text(plan_draft(repo), encoding="utf-8")
    cold_artifact = draft.read_text(encoding="utf-8")
    finding = "State the exact repository fact."
    _seed_cold_launch(
        repo, "plan", hashlib.sha256(cold_artifact.encode()).hexdigest(),
        artifact_text=cold_artifact,
        findings={"gaps": [finding], "contradictions": []},
    )
    draft.write_text(cold_artifact + "Resolved fact.\n", encoding="utf-8")
    final_artifact = draft.read_text(encoding="utf-8")
    cold_lines = cold_artifact.splitlines(keepends=True)
    final_lines = final_artifact.splitlines(keepends=True)
    delta = [{
        "cold_start": a, "cold_end": b, "cold": "".join(cold_lines[a:b]),
        "final_start": c, "final_end": d, "final": "".join(final_lines[c:d]),
    } for tag, a, b, c, d in difflib.SequenceMatcher(
        a=cold_lines, b=final_lines, autojunk=False).get_opcodes()
        if tag != "equal"]
    amendment = {
        "delta_index": 0, "findings": [finding],
        "change": "Added the exact repository fact.",
        "reason": "Closes the authenticated cold finding.",
        "source": "factory/scripts/record_grill_from_json.py",
    }
    base = {
        "generated_by": "griller", "gate": "plan", "verdict": "pass",
        "gaps": [finding], "contradictions": [],
        "resolutions": ["Added the exact repository fact."],
        "finding_dispositions": [{
            "finding": finding, "resolution": "Added the exact repository fact.",
            "source": "factory/scripts/record_grill_from_json.py",
        }],
        "amendments": [amendment], "artifact_delta": delta,
    }
    variants = [
        ({**base, "amendments": []}, "every delta"),
        ({**base, "amendments": [amendment, amendment]}, "every delta"),
        ({**base, "amendments": [{**amendment, "findings": ["substituted"]}]},
         "exact cold finding"),
        ({**base, "artifact_delta": []}, "exactly match"),
    ]
    for payload, message in variants:
        code, out = run(
            repo, "record_grill_from_json.py", "--gate", "plan",
            "--input-digest", str(draft), stdin=json.dumps(payload),
        )
        assert code != 0 and message in out
    code, out = run(
        repo, "record_grill_from_json.py", "--gate", "plan",
        "--input-digest", str(draft), stdin=json.dumps(base),
    )
    assert code == 0, out


def test_recorder_uses_latest_successful_cold_read_with_amendments(
        repo: Path, tmp_path: Path):
    from forge_cli.delegate import delegations_path, load_delegations

    sign_off(repo)
    code, out = intake(repo)
    assert code == 0, out
    draft = tmp_path / "latest-read.md"
    draft.write_text(plan_draft(repo), encoding="utf-8")
    earlier = draft.read_text(encoding="utf-8")
    _seed_cold_launch(
        repo, "plan", hashlib.sha256(earlier.encode()).hexdigest(),
        artifact_text=earlier,
        findings={"gaps": ["Earlier finding."], "contradictions": []},
    )
    earlier_rows = [row for row in load_delegations(repo)
                    if row.get("task") == "grill-plan"]

    latest = earlier + "\nUpdated repository fact for the latest read.\n"
    draft.write_text(latest, encoding="utf-8")
    finding = "State the updated repository fact."
    _seed_cold_launch(
        repo, "plan", hashlib.sha256(latest.encode()).hexdigest(),
        artifact_text=latest,
        findings={"gaps": [finding], "contradictions": []},
    )
    all_rows = load_delegations(repo)
    latest_rows = [row for row in all_rows if row.get("task") == "grill-plan"]
    other_rows = [row for row in all_rows if row.get("task") != "grill-plan"]
    assert earlier_rows[-1]["launch_id"] != latest_rows[-1]["launch_id"]
    ledger = delegations_path(repo)
    ledger.write_text("".join(
        json.dumps(row) + "\n"
        for row in [*other_rows, *earlier_rows, *latest_rows]
    ), encoding="utf-8")

    final = latest + "Resolved the latest finding.\n"
    draft.write_text(final, encoding="utf-8")
    code, out = run(
        repo, "record_grill_from_json.py", "--gate", "plan",
        "--input-digest", str(draft),
        stdin=json.dumps(_amended_plan_payload(latest, final, finding)),
    )

    assert code == 0, out
    recorded = json.loads(
        (repo / ".factory/stories/ENG-1/grills/plan.json").read_text()
    )
    assert recorded["launch_id"] == latest_rows[-1]["launch_id"]
    assert recorded["cold_input_sha256"] == hashlib.sha256(latest.encode()).hexdigest()
    assert recorded["final_artifact_sha256"] == hashlib.sha256(final.encode()).hexdigest()


def test_normal_authority_refuses_coldless_grill_with_upgrade_guidance(repo: Path):
    lib = load_factory_lib(repo)
    lib.dump_json(repo / ".factory" / "grills" / "signoff.json", {
        "verdict": "pass", "commit": lib.head_sha(repo),
    })
    with pytest.raises(SystemExit, match="forge upgrade"):
        lib.require_grill(repo, "signoff", ())


def _write_legacy_inflight_grill(repo: Path, status: str = "active"):
    lib = load_factory_lib(repo)
    task = STAGE_TASK
    seed_task_grill_frontier(repo, task)
    write_stages(repo, {
        "issue": "TEST-1",
        "stages": [{
            "id": "T1", "title": task["title"], "status": status,
            "started_at": "2026-09-14T00:02:00+00:00",
            "task_sha256": lib.task_digest(task),
        }],
    })
    plan = lib.evidence_path(repo, "TEST-1", "task-plans/T1.md")
    digest = lib.plan_digest_without_assumptions(plan)
    grill = {
        "generated_by": "griller", "gate": "task", "verdict": "pass",
        "issue": "TEST-1", "task_id": "T1", "commit": lib.head_sha(repo),
        "recorded_at": "2026-09-14T00:00:00+00:00",
        "input_sha256": lib.grounding_digest(repo, task, in_stage=True),
        "task_plan_sha256": digest,
        "approved_task_plan_sha256": digest,
        "approved_by": "Ravi (pre-Lean approval)",
        "approved_at": "2026-09-14T00:01:00+00:00",
    }
    lib.dump_json(
        lib.evidence_path(repo, "TEST-1", "grills/tasks/T1.json", for_write=True),
        grill,
    )
    return lib, task


@pytest.mark.parametrize("status", ["active", "done"])
def test_exact_inflight_legacy_task_grill_continues_without_second_cold_read(
        repo: Path, status: str):
    lib, task = _write_legacy_inflight_grill(repo, status)

    lib.require_task_grill(repo, "T1", task)
    grill = json.loads(
        lib.evidence_path(repo, "TEST-1", "grills/tasks/T1.json").read_text()
    )
    assert lib._task_grill_fresh(repo, task, grill)
    assert lib._task_plan_state(repo, task, grill) == "approved"


@pytest.mark.parametrize("mutation", [
    "pending", "grounding", "approval", "story", "task", "timing",
    "approval-before-recording", "naive-time", "malformed-time", "producer",
    "gate", "verdict", "stage-digest", "partial-cold", "native-identity",
    "forged-continuity", "post-start-approval", "missing-approval",
])
def test_legacy_task_grill_refuses_frontier_stale_or_unbound_authority(
        repo: Path, mutation: str):
    lib, task = _write_legacy_inflight_grill(repo)
    path = lib.evidence_path(repo, "TEST-1", "grills/tasks/T1.json")
    grill = json.loads(path.read_text())
    if mutation == "pending":
        write_stages(repo, {
            "issue": "TEST-1",
            "stages": [{
                "id": "T1", "title": task["title"], "status": "pending",
                "started_at": "2026-09-14T00:02:00+00:00",
            }],
        })
    elif mutation == "grounding":
        grill["input_sha256"] = "0" * 64
    elif mutation == "approval":
        grill["approved_task_plan_sha256"] = "0" * 64
    elif mutation == "story":
        grill["issue"] = "OTHER"
    elif mutation == "timing":
        grill["recorded_at"] = "2026-09-14T00:03:00+00:00"
    elif mutation == "approval-before-recording":
        grill["approved_at"] = "2026-09-13T23:59:00+00:00"
    elif mutation == "post-start-approval":
        grill["approved_at"] = "2026-09-14T00:03:00+00:00"
    elif mutation == "missing-approval":
        grill["approved_by"] = ""
    elif mutation == "naive-time":
        grill["approved_at"] = "2026-09-14T00:01:00"
    elif mutation == "malformed-time":
        grill["recorded_at"] = "not-a-timestamp"
    elif mutation == "producer":
        grill["generated_by"] = "planner"
    elif mutation == "gate":
        grill["gate"] = "plan"
    elif mutation == "verdict":
        grill["verdict"] = "fail"
    elif mutation == "stage-digest":
        stages = json.loads((repo / ".git/forge/stages.json").read_text())
        stages["stages"][0]["task_sha256"] = "0" * 64
        write_stages(repo, stages)
    elif mutation == "forged-continuity":
        stages = json.loads((repo / ".git/forge/stages.json").read_text())
        stages["stages"][0]["task_sha256"] = "0" * 64
        stages["stages"][0]["measurement_continuity"] = [{}]
        write_stages(repo, stages)
    elif mutation == "partial-cold":
        grill["cold_input_sha256"] = "0" * 64
    elif mutation == "native-identity":
        grill["approval_runtime"] = "codex"
    else:
        grill["task_id"] = "OTHER"
    lib.dump_json(path, grill)

    with pytest.raises(SystemExit, match="forge upgrade"):
        lib.require_task_grill(repo, "T1", task)


@pytest.mark.parametrize("trailing", ["", "\n"])
def test_cold_artifact_frame_recovers_heading_like_exact_bytes(
        repo: Path, trailing: str):
    artifact = (
        "# Plan\n\n## What to return\nThis heading is artifact data.\n"
        "## The artifact under interrogation (nested)\nbody" + trailing
    )
    brief = _compose_brief(repo, "plan", "fixture", artifact).encode("utf-8")
    digest = _artifact_digest(artifact)

    recovered = _cold_artifact_from_brief(brief, digest)

    assert recovered == artifact
    assert hashlib.sha256(recovered.encode("utf-8")).hexdigest() == digest


@pytest.mark.parametrize(("cold_result", "submitted", "message"), [
    ({"gaps": ["Cold finding."], "contradictions": []},
     {"gaps": [], "contradictions": []}, "must match"),
    ({"gaps": ["Cold finding."], "contradictions": []},
     {"gaps": ["Substituted finding."], "contradictions": []}, "must match"),
    ({"gaps": ["Cold finding."], "contradictions": ["Cold contradiction."]},
     {"gaps": ["Cold finding."], "contradictions": []}, "must match"),
    ("not JSON", {"gaps": [], "contradictions": []}, "terminal output hash"),
    ({"gaps": []}, {"gaps": [], "contradictions": []}, "invalid shape"),
    ({"gaps": [""], "contradictions": []},
     {"gaps": [], "contradictions": []}, "invalid shape"),
])
def test_cold_grill_recorder_refuses_substituted_or_malformed_findings(
        repo: Path, tmp_path: Path, cold_result, submitted, message):
    sign_off(repo)
    intake(repo)
    draft = tmp_path / "plan.md"
    draft.write_text(plan_draft(repo), encoding="utf-8")
    _seed_cold_launch(repo, "plan", hashlib.sha256(draft.read_bytes()).hexdigest(),
                      findings=cold_result if isinstance(cold_result, dict) else None,
                      artifact_text=draft.read_text(encoding="utf-8"))
    if isinstance(cold_result, str):
        from forge_cli.delegate import load_delegations
        Path(load_delegations(repo)[-1]["output_path"]).write_text(json.dumps({
            "status": 0, "threadId": "fixture-session",
            "rawOutput": cold_result,
        }), encoding="utf-8")
    submitted_findings = [*submitted["gaps"], *submitted["contradictions"]]
    payload = {
        "generated_by": "griller", "gate": "plan", "verdict": "pass",
        **submitted, "resolutions": ["Resolved in the draft."] * len(submitted_findings),
        "finding_dispositions": [{
            "finding": finding, "resolution": "Resolved in the draft.",
            "source": "factory/scripts/forge_cli/grill.py",
        } for finding in submitted_findings],
    }
    code, output = run(repo, "record_grill_from_json.py", "--gate", "plan",
                       "--input-digest", str(draft), stdin=json.dumps(payload))
    assert code != 0 and message in output
    assert not (repo / ".factory/stories/ENG-1/grills/plan.json").exists()


def test_native_cold_grill_uses_recorded_message_findings(
        repo: Path, tmp_path: Path):
    from forge_cli.codex_runtime import native_argv
    from forge_cli.delegate import argv_digest, delegations_path

    sign_off(repo)
    intake(repo)
    draft = tmp_path / "plan.md"
    draft.write_text(plan_draft(repo), encoding="utf-8")
    _seed_cold_launch(
        repo, "plan", hashlib.sha256(draft.read_bytes()).hexdigest(),
        artifact_text=draft.read_text(encoding="utf-8"),
    )
    ledger = delegations_path(repo)
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    output = tmp_path / "native-result.jsonl"
    output.write_text("\n".join([
        json.dumps({"type": "thread.started", "thread_id": "cold-session"}),
        json.dumps({"type": "item.completed", "item": {
            "type": "agent_message", "text": json.dumps({
                "gaps": ["Native finding."], "contradictions": [],
            }),
        }}),
        json.dumps({"type": "turn.completed"}), "",
    ]), encoding="utf-8")
    for row in rows:
        argv = native_argv("/fixture/codex", repo, row["model"], row["effort"],
                           False, [])
        row.update(transport="native", executable_path="/fixture/codex",
                   argv=argv, argv_sha256=argv_digest(argv),
                   output_path=str(output))
        if row["launch_status"] == "succeeded":
            row["session_id"] = "cold-session"
            row["output_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
    ledger.write_text("".join(json.dumps(row) + "\n" for row in rows),
                      encoding="utf-8")
    payload = {
        "generated_by": "griller", "gate": "plan", "verdict": "pass",
        "gaps": [], "contradictions": [], "resolutions": [],
        "finding_dispositions": [],
    }
    code, out = run(repo, "record_grill_from_json.py", "--gate", "plan",
                    "--input-digest", str(draft), stdin=json.dumps(payload))
    assert code != 0 and "must match the authenticated cold-read result" in out


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
    _seed_cold_launch(
        repo, "plan", hashlib.sha256(draft.read_bytes()).hexdigest(),
        artifact_text=draft.read_text(encoding="utf-8"),
    )
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


@pytest.mark.parametrize("tamper", ["rewrite", "missing_hash"])
def test_cold_grill_refuses_output_changed_after_terminal_publication(repo, tmp_path, tamper):
    from forge_cli.delegate import delegations_path
    sign_off(repo)
    intake(repo)
    draft = tmp_path / "plan.md"
    draft.write_text(plan_draft(repo), encoding="utf-8")
    _seed_cold_launch(
        repo, "plan", hashlib.sha256(draft.read_bytes()).hexdigest(),
        artifact_text=draft.read_text(encoding="utf-8"),
    )
    ledger = delegations_path(repo)
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    if tamper == "rewrite":
        Path(rows[-1]["output_path"]).write_text(json.dumps({
            "status": 0, "threadId": "fixture-session",
            "rawOutput": json.dumps({"gaps": ["replacement"], "contradictions": []}),
        }))
    else:
        rows[-1].pop("output_sha256")
        ledger.write_text("".join(json.dumps(row) + "\n" for row in rows))
    payload = {"generated_by": "griller", "gate": "plan", "verdict": "pass",
               "gaps": [], "contradictions": [], "resolutions": [],
               "finding_dispositions": []}
    code, out = run(repo, "record_grill_from_json.py", "--gate", "plan",
                    "--input-digest", str(draft), stdin=json.dumps(payload))
    assert code != 0 and "terminal output hash" in out
    assert not (repo / ".factory/stories/ENG-1/grills/plan.json").exists()


def test_task_cold_grill_crlf_uses_same_text_digest_as_launch(repo):
    from test_gates import STAGE_TASK, seed_task_grill_frontier, task_grill_payload
    from forge_cli.grill import _artifact_digest, _review_artifact_text
    from grill_gates import get_gate

    seed_task_grill_frontier(repo, STAGE_TASK)
    plan = repo / ".factory/task-plans/T1.md"
    plan.write_bytes(plan.read_bytes().replace(b"\n", b"\r\n"))
    _, task_plan = get_gate("task").locate(repo, "T1", "")
    cold_artifact = _review_artifact_text(repo, "task", "T1", task_plan)
    cold = _artifact_digest(cold_artifact)
    _seed_task_cold_launch(repo, "T1")
    code, out = run(repo, "record_grill_from_json.py", "--gate", "task", "--task", "T1",
                    stdin=json.dumps(task_grill_payload(STAGE_TASK)))
    assert code == 0, out
    lib = load_factory_lib(repo)
    result = json.loads(lib.evidence_path(repo, "TEST-1", "grills/tasks/T1.json").read_text())
    assert result["cold_input_sha256"] == result["final_artifact_sha256"] == cold
    assert result["task_plan_sha256"] == lib.plan_digest_without_assumptions(plan)


def test_native_result_scanner_uses_captured_bytes_after_path_replacement(tmp_path):
    from forge_cli.codex_runtime import scan_native_result
    data = (json.dumps({"type": "thread.started", "thread_id": "captured"}) + "\n"
            + json.dumps({"type": "item.completed", "item": {
                "type": "agent_message", "text": "captured finding"}}) + "\n"
            + json.dumps({"type": "turn.completed"}) + "\n").encode()
    path = tmp_path / "output.jsonl"
    path.write_bytes(b"replacement, not JSON")
    result = scan_native_result(path, data=data)
    assert result.session_id == "captured" and result.message == "captured finding"
    assert not result.error


def test_live_findings_refuse_fixed_proof_for_active_and_inactive_stories(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    from forge_cli import findings

    lib = load_factory_lib(repo)
    lib.dump_json(lib.run_state_path(repo), {"issue_key": "ACTIVE", "story": "ACTIVE"})
    historical = lib.story_dir(repo, "HIST") / "reviews" / "quality.json"
    historical.parent.mkdir(parents=True, exist_ok=True)
    historical.write_text(json.dumps({
        "blocking_findings": ["historical display finding"],
    }), encoding="utf-8")
    monkeypatch.setattr(
        findings, "load_items", lambda _base: [{"key": "HIST"}, {"key": "ACTIVE"}],
    )
    with pytest.raises(SystemExit, match="story HIST.*run forge upgrade"):
        findings.collect(repo)

    historical.unlink()

    active = lib.story_dir(repo, "ACTIVE") / "reviews" / "quality.json"
    active.parent.mkdir(parents=True, exist_ok=True)
    active.write_text(json.dumps({"blocking_findings": []}), encoding="utf-8")
    selected = lib.story_dir(repo, "ACTIVE") / "tasks/T1/reviews/selected.json"
    selected.parent.mkdir(parents=True, exist_ok=True)
    selected.write_text("{}\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="run forge upgrade"):
        findings.collect(repo)

    active.unlink()
    task_fixed = lib.story_dir(repo, "ACTIVE") / "tasks/T1/reviews/quality.json"
    task_fixed.write_text(json.dumps({
        "blocking_findings": ["retired task finding"],
    }), encoding="utf-8")
    with pytest.raises(SystemExit, match="story ACTIVE task T1.*run forge upgrade"):
        findings.collect(repo)
