from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from test_gates import HARNESS, load_factory_lib, repo  # noqa: F401

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from forge_cli import stages  # noqa: E402


def _task() -> dict:
    return {
        "id": "T1", "objective": "secure migration",
        "acceptance_criteria": ["secure", "migrate"],
        "plan_contracts": [
            {"id": "A", "statement": "secure"},
            {"id": "B", "statement": "migrate"},
        ],
        "reviewer_focus": ["security", "migration"],
        "write_scope": ["src/a.py"],
        "required_tests": [{"id": "test_a", "path": "tests/a.py",
                            "command": "python tests/a.py --case test_a"}],
        "verify_commands": ["python -m compileall src"],
    }


def _seed_review(repo: Path, monkeypatch, task: dict) -> tuple[dict, dict]:
    lib = load_factory_lib(repo)
    lib.dump_json(lib.run_state_path(repo), {"issue_key": "S1", "story": "S1"})
    plan = lib.evidence_path(repo, "S1", "task-plans/T1.md", for_write=True)
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("# exact task plan\n", encoding="utf-8")
    proof = lib.proof_path(repo, "S1", "tests.json", task_id="T1", for_write=True)
    proof.parent.mkdir(parents=True, exist_ok=True)
    proof.write_text(json.dumps({
        "automated": {"status": "passed", "cases": ["a"]},
        "recorded_at": "old", "generated_by": "implementer",
    }), encoding="utf-8")
    stage = {"id": "T1"}
    monkeypatch.setattr(stages, "stage_review_binding",
                        lambda *_args: {"stage_id": "T1", "base_sha": "b",
                                       "delta_id": "d" * 64})
    return stage, {"path": sys.executable, "version": "3.11",
                   "sha256": "a" * 64}


def test_unchanged_test_verify_and_selected_review_inputs_reuse_success_without_rerun(
        repo: Path, monkeypatch):
    task = _task()
    assert stages.proof_identity(repo, task, "tests") == stages.proof_identity(
        repo, task, "tests")
    assert stages.proof_identity(repo, task, "verify") == stages.proof_identity(
        repo, task, "verify")
    stage, helper = _seed_review(repo, monkeypatch, task)
    assert stages.reviewed_meaning_identity(
        repo, stage, task, helper) == stages.reviewed_meaning_identity(
            repo, stage, task, helper)


def test_changed_unknown_partial_or_generated_output_identity_forces_fresh_run(
        repo: Path):
    task = _task()
    before = stages.proof_identity(repo, task, "tests")["identity"]
    changed = copy.deepcopy(task)
    changed["required_tests"][0]["command"] += " --strict"
    assert stages.proof_identity(repo, changed, "tests")["identity"] != before
    changed["required_tests"][0]["command"] = "missing-tool --strict"
    identity = stages.proof_identity(repo, changed, "tests")
    assert identity["inputs"]["tools"][0]["reusable"] is False
    assert identity["reusable"] is False

    generated = repo / "generated.json"
    generated.write_text("one\n", encoding="utf-8")
    with_generated = {**task, "generated_semantic_inputs": ["generated.json"]}
    before_generated = stages.proof_identity(repo, with_generated, "verify")
    generated.write_text("two\n", encoding="utf-8")
    after_generated = stages.proof_identity(repo, with_generated, "verify")
    assert before_generated["identity"] != after_generated["identity"]
    assert before_generated["inputs"]["generated_inputs"]["generated.json"][
        "sha256"] != after_generated["inputs"]["generated_inputs"][
            "generated.json"]["sha256"]


def test_reuse_identity_is_proof_type_specific_and_reviewed_meaning_bound(
        repo: Path, monkeypatch):
    task = _task()
    tests_before = stages.proof_identity(repo, task, "tests")["identity"]
    verify_before = stages.proof_identity(repo, task, "verify")["identity"]
    changed = copy.deepcopy(task)
    changed["required_tests"][0]["command"] += " --one"
    assert stages.proof_identity(repo, changed, "tests")["identity"] != tests_before
    assert stages.proof_identity(repo, changed, "verify")["identity"] == verify_before
    stage, helper = _seed_review(repo, monkeypatch, task)
    meaning = stages.reviewed_meaning_identity(
        repo, stage, task, helper)["semantic_identity"]
    changed["acceptance_criteria"] = ["different"]
    assert stages.reviewed_meaning_identity(
        repo, stage, changed, helper)["semantic_identity"] != meaning


def test_selected_review_reuses_for_bookkeeping_only_changes_and_preserves_original_provenance(
        repo: Path, monkeypatch):
    task = _task()
    stage, helper = _seed_review(repo, monkeypatch, task)
    before = stages.reviewed_meaning_identity(repo, stage, task, helper)
    lib = load_factory_lib(repo)
    proof = lib.proof_path(repo, "S1", "tests.json", task_id="T1")
    data = json.loads(proof.read_text())
    data["recorded_at"] = "new"
    data["generated_by"] = "recorder-v2"
    proof.write_text(json.dumps(data), encoding="utf-8")
    after = stages.reviewed_meaning_identity(repo, stage, task, helper)
    assert after["identity"] == before["identity"]
    assert before["inputs"]["automated_evidence"]["automated"] == {
        "status": "passed", "cases": ["a"]}


def test_selected_review_reruns_for_changed_acceptance_security_migration_or_evidence(
        repo: Path, monkeypatch):
    task = _task()
    stage, helper = _seed_review(repo, monkeypatch, task)
    before = stages.reviewed_meaning_identity(
        repo, stage, task, helper)["semantic_identity"]
    for field, value in (
        ("acceptance_criteria", ["changed"]),
        ("reviewer_focus", ["changed security"]),
        ("objective", "changed migration"),
    ):
        changed = copy.deepcopy(task)
        changed[field] = value
        assert stages.reviewed_meaning_identity(
            repo, stage, changed, helper)["semantic_identity"] != before
    lib = load_factory_lib(repo)
    proof = lib.proof_path(repo, "S1", "tests.json", task_id="T1")
    data = json.loads(proof.read_text())
    data["automated"]["cases"].append("substantive")
    proof.write_text(json.dumps(data), encoding="utf-8")
    assert stages.reviewed_meaning_identity(
        repo, stage, task, helper)["semantic_identity"] != before
