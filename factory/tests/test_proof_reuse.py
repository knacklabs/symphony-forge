from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_gates import HARNESS, git, load_factory_lib, repo  # noqa: F401

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
                            "command": "python -m pytest tests/a.py -k test_a"}],
        "verify_commands": ["python -m compileall factory/scripts"],
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
    source = repo / "tests" / "a.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("def test_a():\n    pass\n", encoding="utf-8")
    task = _task()
    tests = stages.proof_identity(repo, task, "tests")
    verify = stages.proof_identity(repo, task, "verify")
    assert tests["reusable"] is True
    assert verify["reusable"] is True
    assert tests == stages.proof_identity(repo, task, "tests")
    assert verify == stages.proof_identity(repo, task, "verify")
    stage, helper = _seed_review(repo, monkeypatch, task)
    assert stages.reviewed_meaning_identity(
        repo, stage, task, helper) == stages.reviewed_meaning_identity(
            repo, stage, task, helper)


def test_run_stage_proof_reuses_matching_receipts_by_proof_type(repo: Path, monkeypatch):
    task = _task()
    test_file = repo / "tests" / "a.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("pass\n", encoding="utf-8")
    receipts = {
        kind: {**stages.proof_identity(repo, task, kind), "status": "passed"}
        for kind in ("verify", "tests")
    }
    assert all(stages.proof_identity(repo, task, kind)["reusable"] is True
               for kind in receipts)
    calls = []
    monkeypatch.setattr(stages, "_proof_receipt", lambda _base, _id, kind:
                        receipts[kind])
    monkeypatch.setattr(stages, "_run_verify_commands", lambda *_args:
                        calls.append("verify"))
    monkeypatch.setattr(stages, "_run_required_tests", lambda *_args:
                        calls.append("tests") or ([], []))
    monkeypatch.setattr(stages, "_store_proof_receipt", lambda *_args: None)
    monkeypatch.setattr(stages, "protected_authority_snapshot",
                        lambda _base: {"stage": "unchanged"})
    before = stages.product_tree_snapshot(repo)
    stages.run_stage_proof(repo, "T1", task)
    assert calls == []
    assert stages.product_tree_snapshot(repo) == before

    changed = copy.deepcopy(task)
    changed["required_tests"][0]["command"] += " --strict"
    stages.run_stage_proof(repo, "T1", changed)
    assert calls == ["tests"]
    assert stages.product_tree_snapshot(repo) == before

    monkeypatch.setenv("PYTEST_ADDOPTS", "--strict-markers")
    stages.run_stage_proof(repo, "T1", task)
    assert calls == ["tests", "verify", "tests"]


def test_review_preflight_requires_current_test_and_verify_receipt_identities(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    from forge_cli.review import pre_review_proof_problems
    from factory_lib import (
        dump_json, proof_path, protected_decomposition_state_path, run_state_path,
    )

    source = repo / "tests" / "a.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("def test_a():\n    pass\n", encoding="utf-8")
    task = _task()
    dump_json(run_state_path(repo), {"story": "S1", "issue_key": "S1"})
    dump_json(protected_decomposition_state_path(repo), {"tasks": [task]})
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    proof_root = proof_path(repo, "S1", "tests.json", task_id="T1").parent
    proof_root.mkdir(parents=True, exist_ok=True)
    dump_json(proof_root / "verify.json", {"ok": True, "commit": commit})
    dump_json(proof_root / "tests.json", {
        "commit": commit,
        "automated": {"status": "passed", "blocking_findings": []},
    })
    receipts = {
        kind: {**stages.proof_identity(repo, task, kind), "status": "passed"}
        for kind in ("verify", "tests")
    }
    stages.write_stages(repo, {"issue": "S1", "stages": [{
        "id": "T1", "status": "active", "proof_receipts": receipts,
    }]})

    assert pre_review_proof_problems(repo, "S1", "T1", commit, commit) == []

    current_identity = stages.proof_identity

    def changed_identity(*args, **kwargs):
        value = current_identity(*args, **kwargs)
        return {**value, "identity": "0" * 64}

    monkeypatch.setattr(stages, "proof_identity", changed_identity)
    problems = pre_review_proof_problems(repo, "S1", "T1", commit, commit)
    assert any("tests proof receipt identity is stale" in problem
               for problem in problems), problems


def test_close_context_allows_one_fresh_nonreusable_proof_then_refuses_drift(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    """Close may review a successful unknown-runner proof once; direct review cannot."""
    from forge_cli.review import pre_review_proof_problems
    from factory_lib import (
        dump_json, proof_path, protected_decomposition_state_path, run_state_path,
    )

    task = {
        **_task(),
        "required_tests": [],
        "verify_commands": ["python3 factory/scripts/check_dual_runtime.py"],
        "generated_semantic_inputs": ["generated.json"],
    }
    generated = repo / "generated.json"
    generated.write_text("one\n", encoding="utf-8")
    dump_json(run_state_path(repo), {"story": "S1", "issue_key": "S1"})
    dump_json(protected_decomposition_state_path(repo), {"tasks": [task]})
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    proof_root = proof_path(repo, "S1", "tests.json", task_id="T1").parent
    proof_root.mkdir(parents=True, exist_ok=True)
    dump_json(proof_root / "verify.json", {"ok": True, "commit": commit})
    dump_json(proof_root / "tests.json", {
        "commit": commit,
        "automated": {"status": "passed", "blocking_findings": []},
    })
    stages.write_stages(repo, {"issue": "S1", "stages": [{
        "id": "T1", "status": "active", "proof_receipts": {},
    }]})
    monkeypatch.setattr(
        stages, "_run_verify_commands",
        lambda _base, _stage_id, current_task, *_args: [
            {"command": command, "exit_code": 0, "output_tail": ""}
            for command in current_task["verify_commands"]
        ],
    )

    context: dict[str, object] = {}
    stages.run_stage_proof(repo, "T1", task, proof_context=context)
    verify_receipt = stages._proof_receipt(repo, "T1", "verify")
    original_stages = copy.deepcopy(stages.load_stages(repo))
    assert verify_receipt["status"] == "passed"
    assert verify_receipt["reusable"] is False
    assert context["proofs"]["verify"]["executed"] is True
    direct_problems = pre_review_proof_problems(repo, "S1", "T1", commit, commit)
    assert any("verify proof receipt identity is stale" in problem
               for problem in direct_problems)
    assert pre_review_proof_problems(
        repo, "S1", "T1", commit, commit, proof_context=context,
    ) == []
    metadata_context = copy.deepcopy(context)
    metadata_context["product_tree"]["head"] = "metadata-only-commit"
    assert pre_review_proof_problems(
        repo, "S1", "T1", commit, commit, proof_context=metadata_context,
    ) == []
    assert metadata_context["product_tree"] == stages.product_tree_snapshot(repo)

    tampered = stages.load_stages(repo)
    tampered["stages"][0]["proof_receipts"]["verify"]["identity"] = "0" * 64
    stages.write_stages(repo, tampered)
    assert any("verify proof receipt identity is stale" in problem
               for problem in pre_review_proof_problems(
                   repo, "S1", "T1", commit, commit, proof_context=context
               )), "tampered receipt must refuse review"

    # Restore the exact receipt, then prove environment, product and protected-
    # authority drift are rejected even with the fresh in-memory context.
    stages.write_stages(repo, original_stages)
    monkeypatch.setenv("LEAN_CONTEXT_DRIFT", "changed")
    assert any("verify proof receipt identity is stale" in problem
               for problem in pre_review_proof_problems(
                   repo, "S1", "T1", commit, commit, proof_context=context
               )), "environment drift must refuse review"
    monkeypatch.delenv("LEAN_CONTEXT_DRIFT")
    (repo / "src").mkdir()
    (repo / "src" / "a.py").write_text("drift\n", encoding="utf-8")
    assert any("product tree changed" in problem
               for problem in pre_review_proof_problems(
                   repo, "S1", "T1", commit, commit, proof_context=context
               )), "product drift must refuse review"
    (repo / "src" / "a.py").unlink()

    lib = load_factory_lib(repo)
    authority_drift = lib.git_control_dir(repo) / "context-drift"
    authority_drift.write_text("drift\n", encoding="utf-8")
    try:
        assert any("protected authority changed" in problem
                   for problem in pre_review_proof_problems(
                       repo, "S1", "T1", commit, commit,
                       proof_context=context,
                   )), "protected-authority drift must refuse review"
    finally:
        authority_drift.unlink()


@pytest.mark.parametrize("missing_artifact", ["verify.json", "tests.json", "tests_changed"])
def test_close_reuse_reruns_only_proof_with_missing_or_changed_evidence(
        repo: Path, monkeypatch: pytest.MonkeyPatch, missing_artifact: str):
    from factory_lib import dump_json, proof_path, run_state_path

    test_file = repo / "tests" / "a.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("def test_a():\n    pass\n", encoding="utf-8")
    task = {
        **_task(),
        "required_tests": [{
            "id": "test_a", "path": "tests/a.py",
            "command": "python -m pytest {path}::{id} -q",
        }],
        "verify_commands": ["python3 factory/scripts/check_dual_runtime.py"],
    }
    dump_json(run_state_path(repo), {"issue_key": "S1", "story": "S1"})
    root = proof_path(repo, "S1", "tests.json", task_id="T1").parent
    root.mkdir(parents=True, exist_ok=True)
    key = "proof-key"
    prior_verify = [{
        "command": task["verify_commands"][0], "exit_code": 0,
        "output_tail": "prior pass",
    }]
    prior_tests = [{"id": "test_a", "path": "tests/a.py", "status": "passed"}]
    if missing_artifact != "verify.json":
        dump_json(root / "verify.json", {
            "recorded_by": stages.STAGE_PROOF, "task_id": "T1",
            "proof_key": "old-key" if missing_artifact == "tests_changed" else key,
            "results": prior_verify, "required_tests": prior_tests,
            "ok": True,
        })
    if missing_artifact != "tests.json":
        dump_json(root / "tests.json", {"commit": "prior"})
    verify_runs: list[list[dict]] = []
    test_runs: list[list[dict]] = []
    recorded: list[dict] = []
    identities = {
        kind: {"identity": kind, "inputs": {"kind": kind}, "reusable": True}
        for kind in ("verify", "tests")
    }
    monkeypatch.setattr(
        stages, "_require_test_input", lambda *_args: None,
    )
    monkeypatch.setattr(
        stages, "proof_identity",
        lambda _base, _task, kind, **_kwargs: identities[kind],
    )
    monkeypatch.setattr(stages, "proof_key", lambda *_args, **_kwargs: key)
    monkeypatch.setattr(
        stages, "_proof_receipt",
        lambda _base, _stage, kind: {
            **identities[kind], "status": "passed",
            "identity": "old-tests" if missing_artifact == "tests_changed"
            and kind == "tests" else identities[kind]["identity"],
        },
    )
    monkeypatch.setattr(stages, "_store_proof_receipt", lambda *_args: None)
    monkeypatch.setattr(stages, "product_tree_snapshot", lambda _base: {"dirty": False})
    monkeypatch.setattr(stages, "protected_authority_snapshot", lambda _base: {})
    monkeypatch.setattr(
        stages, "_run_verify_commands",
        lambda _base, _stage, current_task, *_args: verify_runs.append([
            {"command": command, "exit_code": 0, "output_tail": "fresh pass"}
            for command in current_task["verify_commands"]
        ]) or verify_runs[-1],
    )
    monkeypatch.setattr(
        stages, "_run_required_tests",
        lambda *_args: ([], test_runs.append([{
            "id": "test_a", "path": "tests/a.py", "status": "passed",
        }]) or test_runs[-1]),
    )
    monkeypatch.setattr(
        stages, "record_stage_proof",
        lambda *_args, **kwargs: recorded.append(kwargs),
    )

    stages.run_stage_proof(repo, "T1", task, proof_context={})

    assert len(verify_runs) == (0 if missing_artifact == "tests_changed" else 1)
    assert len(test_runs) == 1
    assert recorded[0]["verify_results"] == (
        prior_verify if missing_artifact == "tests_changed" else verify_runs[0]
    )
    assert recorded[0]["test_results"] == test_runs[0]


def test_board_proof_inputs_round_trip_through_fresh_review_and_drift(
        repo: Path):
    """Board archive inputs keep their shape through receipt persistence."""
    from forge_cli.review import pre_review_proof_problems
    from factory_lib import (
        dump_json, proof_path, protected_decomposition_state_path, run_state_path,
    )

    task = {
        **_task(),
        "required_tests": [],
        "verify_commands": ["python3 factory/scripts/check_board_complete.py"],
    }
    dump_json(repo / "plans" / "roadmap.json", {"items": [{
        "key": "DONE-1", "title": "completed story", "status": "done",
        "outcome": "shipped",
    }]})
    (repo / ".factory" / "history" / "DONE-1").mkdir(
        parents=True, exist_ok=True,
    )
    events = repo / ".factory" / "events"
    events.mkdir(parents=True, exist_ok=True)
    (events / "done-story.json").write_text(
        json.dumps({"event": "pr-linked", "story": "DONE-1"}),
        encoding="utf-8",
    )
    board_inputs = stages._board_proof_inputs(repo)
    assert board_inputs["archives"] == {"DONE-1": [False, True]}
    legacy_inputs = copy.deepcopy(board_inputs)
    legacy_inputs["archives"] = {
        key: tuple(flags) for key, flags in legacy_inputs["archives"].items()
    }
    assert json.loads(json.dumps(legacy_inputs)) != legacy_inputs

    dump_json(run_state_path(repo), {"story": "S1", "issue_key": "S1"})
    dump_json(protected_decomposition_state_path(repo), {"tasks": [task]})
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    proof_root = proof_path(repo, "S1", "tests.json", task_id="T1").parent
    proof_root.mkdir(parents=True, exist_ok=True)
    stages.write_stages(repo, {"issue": "S1", "stages": [{
        "id": "T1", "status": "active", "proof_receipts": {},
    }]})

    context: dict[str, object] = {}
    stages.run_stage_proof(repo, "T1", task, proof_context=context)
    receipt = stages._proof_receipt(repo, "T1", "verify")
    assert receipt["inputs"] == context["proofs"]["verify"]["inputs"]
    assert pre_review_proof_problems(
        repo, "S1", "T1", commit, commit, proof_context=context,
    ) == []

    event = repo / ".factory" / "events" / "pr-link.json"
    event.parent.mkdir(parents=True, exist_ok=True)
    event.write_text(json.dumps({"event": "pr-linked", "story": "S1"}),
                     encoding="utf-8")
    assert any("verify proof receipt identity is stale" in problem
               for problem in pre_review_proof_problems(
                   repo, "S1", "T1", commit, commit, proof_context=context
               )), "board input drift must refuse review"


def test_authoritative_proof_reads_refuse_without_recording_passing_evidence(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    """Unreadable lifecycle authority must abort proof recording loudly."""
    from factory_lib import task_evidence_path

    task = {**_task(), "verify_commands": [], "required_tests": []}
    verify_path = task_evidence_path(
        repo, "S1", "T1", "verify.json", for_write=True,
    )
    monkeypatch.setattr(stages, "product_tree_snapshot", lambda _base: {})
    monkeypatch.setattr(stages, "protected_authority_snapshot", lambda _base: {})
    monkeypatch.setattr(stages, "_proof_receipt", lambda *_args: {})
    monkeypatch.setattr(stages, "_store_proof_receipt", lambda *_args: None)

    def refuse_run_state(_base):
        raise OSError("protected run pointer unreadable")

    monkeypatch.setattr(stages, "raw_run_state", refuse_run_state)
    with pytest.raises(OSError, match="protected run pointer unreadable"):
        stages.run_stage_proof(repo, "T1", task)
    assert not verify_path.exists()

    monkeypatch.setattr(stages, "raw_run_state", lambda _base: {"issue_key": "S1"})

    def refuse_story(_base):
        raise ValueError("active story authority unreadable")

    monkeypatch.setattr(stages, "active_story_key", refuse_story)
    with pytest.raises(ValueError, match="active story authority unreadable"):
        stages.run_stage_proof(repo, "T1", task)
    assert not verify_path.exists()


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


def test_explicit_external_pytest_config_bytes_bind_reusable_proof(
        repo: Path, tmp_path: Path):
    source = repo / "tests" / "a.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("def test_a():\n    pass\n", encoding="utf-8")
    config = tmp_path / "shared-pytest.ini"
    config.write_text("[pytest]\naddopts = -q\n", encoding="utf-8")
    task = _task()
    task["required_tests"][0]["command"] = (
        f"python -m pytest -c {config} tests/a.py -k test_a"
    )
    before = stages.proof_identity(repo, task, "tests")
    # Config can inject collection paths and has no small complete parser here;
    # dedicated selectors are the safe fallback.
    assert before["reusable"] is False
    config.write_text("[pytest]\naddopts = -q --strict-markers\n", encoding="utf-8")
    after = stages.proof_identity(repo, task, "tests")
    assert after["reusable"] is False
    config.unlink()
    assert stages.proof_identity(repo, task, "tests")["reusable"] is False


def test_ignored_pytest_collection_source_is_never_reusable_after_mutation(
        repo: Path):
    ignored = repo / "local-only" / "test_ignored.py"
    ignored.parent.mkdir(parents=True, exist_ok=True)
    (repo / ".gitignore").write_text("local-only/\n", encoding="utf-8")
    ignored.write_text("def test_local_only():\n    pass\n", encoding="utf-8")
    command = "python3 -m pytest local-only/test_ignored.py -q"
    task = {**_task(), "verify_commands": [command]}

    before = stages.proof_identity(repo, task, "verify")
    assert before["reusable"] is False
    ignored.write_text("def test_local_only():\n    assert False\n", encoding="utf-8")
    after = stages.proof_identity(repo, task, "verify")
    assert after["reusable"] is False


def test_pytest_addopts_external_collection_is_conservative_after_mutation(
        repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    external = tmp_path / "test_external.py"
    external.write_text("def test_external():\n    pass\n", encoding="utf-8")
    monkeypatch.setenv("PYTEST_ADDOPTS", str(external))
    task = {**_task(), "verify_commands": ["python3 -m pytest tests/a.py"]}

    before = stages.proof_identity(repo, task, "verify")
    assert before["reusable"] is False
    external.write_text("def test_external():\n    assert False\n", encoding="utf-8")
    after = stages.proof_identity(repo, task, "verify")
    assert after["reusable"] is False


def test_pytest_nested_config_external_collection_is_conservative_after_mutation(
        repo: Path, tmp_path: Path):
    source = repo / "tests" / "sub" / "test_a.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("def test_a():\n    pass\n", encoding="utf-8")
    external = tmp_path / "test_external.py"
    external.write_text("def test_external():\n    pass\n", encoding="utf-8")
    (source.parent / "pytest.ini").write_text(
        f"[pytest]\naddopts = {external}\n", encoding="utf-8",
    )
    task = {**_task(), "verify_commands": [
        "python3 -m pytest tests/sub/test_a.py",
    ]}

    before = stages.proof_identity(repo, task, "verify")
    assert before["reusable"] is False
    external.write_text("def test_external():\n    assert False\n",
                        encoding="utf-8")
    after = stages.proof_identity(repo, task, "verify")
    assert after["reusable"] is False


@pytest.mark.parametrize("override", [
    "-o addopts={external}",
    "--override-ini addopts={external}",
    "-o=addopts={external}",
    "--override-ini=addopts={external}",
])
def test_pytest_collection_override_is_conservative_after_mutation(
        repo: Path, tmp_path: Path, override: str):
    source = repo / "tests" / "test_a.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("def test_a():\n    pass\n", encoding="utf-8")
    external = tmp_path / "test_external.py"
    external.write_text("def test_external():\n    pass\n", encoding="utf-8")
    task = {**_task(), "verify_commands": [
        f"python3 -m pytest tests/test_a.py {override.format(external=external)}",
    ]}

    before = stages.proof_identity(repo, task, "verify")
    assert before["reusable"] is False
    external.write_text("def test_external():\n    assert False\n",
                        encoding="utf-8")
    after = stages.proof_identity(repo, task, "verify")
    assert after["reusable"] is False


def test_pytest_directory_collection_refuses_external_symlink_but_regular_tree(
        repo: Path, tmp_path: Path):
    source = repo / "tests" / "test_regular.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("def test_regular():\n    pass\n", encoding="utf-8")
    task = {**_task(), "verify_commands": ["python3 -m pytest tests"]}
    assert stages.proof_identity(repo, task, "verify")["reusable"] is True

    external = tmp_path / "test_external.py"
    external.write_text("def test_external():\n    pass\n", encoding="utf-8")
    linked = repo / "tests" / "test_external.py"
    linked.symlink_to(external)
    try:
        before = stages.proof_identity(repo, task, "verify")
        assert before["reusable"] is False
        external.write_text("def test_external():\n    assert False\n",
                            encoding="utf-8")
        after = stages.proof_identity(repo, task, "verify")
        assert after["reusable"] is False
    finally:
        linked.unlink()


@pytest.mark.parametrize("collection_path", ["sibling-tests", "."])
def test_ignored_pytest_sibling_blocks_directory_collection_reuse(
        repo: Path, collection_path: str):
    directory = repo / "sibling-tests" if collection_path != "." else repo
    directory.mkdir(parents=True, exist_ok=True)
    tracked = directory / "test_tracked.py"
    ignored = (directory / "test_ignored.py" if collection_path != "."
               else repo / "local-only" / "test_ignored.py")
    ignored.parent.mkdir(parents=True, exist_ok=True)
    tracked.write_text("def test_tracked():\n    pass\n", encoding="utf-8")
    ignored.write_text("def test_ignored():\n    pass\n", encoding="utf-8")
    (repo / ".gitignore").write_text(
        ("sibling-tests/test_ignored.py\n" if collection_path != "."
         else "local-only/\n"), encoding="utf-8",
    )
    task = {
        **_task(),
        "verify_commands": [f"python3 -m pytest {collection_path} -q"],
    }

    before = stages.proof_identity(repo, task, "verify")
    assert before["reusable"] is False
    ignored.write_text("def test_ignored():\n    assert False\n", encoding="utf-8")
    after = stages.proof_identity(repo, task, "verify")
    assert after["reusable"] is False


def test_canonical_junit_requires_matching_pytest_semantics_and_environment(
        repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source = repo / "tests" / "a.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("def test_a():\n    pass\n", encoding="utf-8")
    report = tmp_path / "canonical.xml"
    report.write_text(
        '<testsuite><testcase name="test_a" file="tests/a.py"/></testsuite>',
        encoding="utf-8",
    )
    task = {
        "verify_commands": ["python3 factory/scripts/verify.py"],
        "required_tests": [{
            "id": "test_a", "path": "tests/a.py",
            "command": "python3 -m pytest {path}::{id} --junitxml={report}",
        }],
    }

    def identify(_base, command, *, fixed_after_assignments=False,
                 environment_overrides=None, **_kwargs):
        _tokens, _environment, environment_identity = stages._proof_environment(
            command, fixed_after_assignments=fixed_after_assignments,
            environment_overrides=environment_overrides,
        )
        return {
            "reusable": True, "environment": environment_identity,
            "interpreter": "test-python", "python_version": "test-version",
            "dependencies": {"pytest": "test-version"},
            "uv_bootstrap": {}, "uv_overlay_sha256": "a" * 64,
            "pytest_config": [],
            "pytest_semantics": stages._pytest_semantic_args(command),
        }

    monkeypatch.setattr(stages, "_proof_tool_identity", identify)
    monkeypatch.setenv("FACTORY_TEST_CMD", "python3 -m pytest tests")
    assert stages._canonical_junit_satisfies_required_tests(
        report, task, base=repo,
        canonical_command="python3 -m pytest tests",
    )

    monkeypatch.setenv(
        "FACTORY_TEST_CMD", "python3 -m pytest tests -p custom_plugin",
    )
    assert not stages._canonical_junit_satisfies_required_tests(
        report, task, base=repo,
        canonical_command="python3 -m pytest tests -p custom_plugin",
    )

    monkeypatch.setenv(
        "FACTORY_TEST_CMD", "python3 -m pytest tests -o strict_markers=true",
    )
    assert not stages._canonical_junit_satisfies_required_tests(
        report, task, base=repo,
        canonical_command="python3 -m pytest tests -o strict_markers=true",
    )

    monkeypatch.setenv("FACTORY_TEST_CMD", "PYTHONUTF8=0 python3 -m pytest tests")
    assert not stages._canonical_junit_satisfies_required_tests(
        report, task, base=repo,
        canonical_command="PYTHONUTF8=0 python3 -m pytest tests",
    )


def test_canonical_junit_matches_envrc_factory_commands_for_selectors(
        repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source = repo / "tests" / "a.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("def test_a():\n    pass\n", encoding="utf-8")
    (repo / ".envrc").write_text(
        'export FACTORY_TEST_CMD="python3 -m pytest tests"\n', encoding="utf-8",
    )
    monkeypatch.delenv("FACTORY_TEST_CMD", raising=False)
    report = tmp_path / "canonical.xml"
    report.write_text(
        '<testsuite><testcase name="test_a" file="tests/a.py"/></testsuite>',
        encoding="utf-8",
    )
    task = {
        "verify_commands": ["python3 factory/scripts/verify.py"],
        "required_tests": [{
            "id": "test_a", "path": "tests/a.py",
            "command": "python3 -m pytest {path}::{id} --junitxml={report}",
        }],
    }

    def identify(_base, command, *, fixed_after_assignments=False,
                 environment_overrides=None, **_kwargs):
        _tokens, _environment, identity = stages._proof_environment(
            command, fixed_after_assignments=fixed_after_assignments,
            environment_overrides=environment_overrides,
        )
        return {
            "reusable": True, "environment": identity,
            "interpreter": "test-python", "python_version": "test-version",
            "dependencies": {"pytest": "test-version"},
            "uv_bootstrap": {}, "uv_overlay_sha256": "a" * 64,
            "pytest_config": [],
            "pytest_semantics": stages._pytest_semantic_args(command),
        }

    monkeypatch.setattr(stages, "_proof_tool_identity", identify)
    assert stages._canonical_junit_satisfies_required_tests(
        report, task, base=repo,
        canonical_command="python3 -m pytest tests",
    )


def test_reuse_identity_is_proof_type_specific_and_reviewed_meaning_bound(
        repo: Path, monkeypatch):
    task = _task()
    tests_before = stages.proof_identity(repo, task, "tests")["identity"]
    verify_before = stages.proof_identity(repo, task, "verify")["identity"]
    changed = copy.deepcopy(task)
    changed["required_tests"][0]["command"] += " --one"
    assert stages.proof_identity(repo, changed, "tests")["identity"] != tests_before
    assert stages.proof_identity(repo, changed, "verify")["identity"] == verify_before
    changed = copy.deepcopy(task)
    changed["acceptance_criteria"] = ["different security contract"]
    assert stages.proof_identity(repo, changed, "tests")["identity"] == tests_before
    assert stages.proof_identity(repo, changed, "verify")["identity"] == verify_before
    stage, helper = _seed_review(repo, monkeypatch, task)
    meaning = stages.reviewed_meaning_identity(
        repo, stage, task, helper)["semantic_identity"]
    changed["acceptance_criteria"] = ["different"]
    assert stages.reviewed_meaning_identity(
        repo, stage, changed, helper)["semantic_identity"] != meaning


def test_authoritative_rendered_review_dataset_is_bound_into_meaning(
        repo: Path, monkeypatch):
    task = _task()
    stage, helper = _seed_review(repo, monkeypatch, task)
    dataset = repo / ".factory" / "review-briefs" / "all.md"
    dataset.parent.mkdir(parents=True, exist_ok=True)
    dataset.write_text("first authoritative dataset\n", encoding="utf-8")
    before = stages.reviewed_meaning_identity(
        repo, stage, task, helper)["semantic_identity"]
    dataset.write_text("changed authoritative dataset\n", encoding="utf-8")
    assert stages.reviewed_meaning_identity(
        repo, stage, task, helper)["semantic_identity"] != before


def test_selected_review_reuses_for_bookkeeping_only_changes_and_preserves_original_provenance(
        repo: Path, monkeypatch):
    task = _task()
    stage, helper = _seed_review(repo, monkeypatch, task)
    dataset = repo / ".factory" / "review-briefs" / "all.md"
    dataset.parent.mkdir(parents=True, exist_ok=True)
    dataset.write_text(
        "#### Full task-owned automated report (implementer-authored evidence)\n\n"
        "```json\n{\n  \"cases\": [\"a\"],\n  \"generated_by\": \"implementer\",\n"
        "  \"recorded_at\": \"old\",\n  \"status\": \"passed\"\n}\n```\n",
        encoding="utf-8",
    )
    before = stages.reviewed_meaning_identity(repo, stage, task, helper)
    lib = load_factory_lib(repo)
    proof = lib.proof_path(repo, "S1", "tests.json", task_id="T1")
    data = json.loads(proof.read_text())
    data["recorded_at"] = "new"
    data["generated_by"] = "recorder-v2"
    proof.write_text(json.dumps(data), encoding="utf-8")
    dataset.write_text(
        dataset.read_text(encoding="utf-8")
        .replace('"implementer"', '"recorder-v2"')
        .replace('"old"', '"new"'),
        encoding="utf-8",
    )
    after = stages.reviewed_meaning_identity(repo, stage, task, helper)
    assert after["identity"] == before["identity"]
    assert before["inputs"]["automated_evidence"]["automated"] == {
        "status": "passed", "cases": ["a"]}


def test_functional_continuation_does_not_stale_automated_review_meaning(
        repo: Path, monkeypatch):
    task = _task()
    stage, helper = _seed_review(repo, monkeypatch, task)
    lib = load_factory_lib(repo)
    proof = lib.proof_path(repo, "S1", "tests.json", task_id="T1")
    data = json.loads(proof.read_text(encoding="utf-8"))
    data["functional"] = {
        "generated_by": "functional-checker", "status": "passed", "score": 9,
    }
    proof.write_text(json.dumps(data), encoding="utf-8")
    before = stages.reviewed_meaning_identity(repo, stage, task, helper)
    data["functional"]["score"] = 8
    proof.write_text(json.dumps(data), encoding="utf-8")
    after_functional = stages.reviewed_meaning_identity(repo, stage, task, helper)
    assert after_functional["identity"] == before["identity"]
    data["automated"]["cases"].append("substantive-change")
    proof.write_text(json.dumps(data), encoding="utf-8")
    after_automated = stages.reviewed_meaning_identity(repo, stage, task, helper)
    assert after_automated["identity"] != before["identity"]


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


def _fake_uv_probe(repo: Path, monkeypatch) -> tuple[dict, Path]:
    runner = repo / "fake-uv"
    runner.write_bytes(b"fake uv runner v1")
    source = repo / "tests" / "a.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("def test_a():\n    pass\n", encoding="utf-8")
    consumer = repo / "installed-package" / "module.py"
    consumer.parent.mkdir(parents=True, exist_ok=True)
    consumer.write_text("VALUE = 1\n", encoding="utf-8")
    state = {"interpreter": b"ephemeral Python v1", "transitive": "1",
             "probe": "complete", "calls": [], "consumer": consumer,
             "bootstrap": b"uv bootstrap v1",
             "bootstrap_pth": b"import _virtualenv\n",
             "overlay": b"import site; site.addsitedir(\"/uv/archive\")"}
    real_which = stages.shutil.which
    real_run = stages.subprocess.run
    monkeypatch.setattr(stages.shutil, "which", lambda command, **kwargs:
                        str(runner) if command == "uv" else
                        real_which(command, **kwargs))

    def probe(argv, **_kwargs):
        if argv[0] != "uv":
            return real_run(argv, **_kwargs)
        assert argv[0] == "uv" and "-c" in argv
        state["calls"].append(tuple(argv))
        ephemeral = repo / "temporary-interpreter"
        ephemeral.write_bytes(state["interpreter"])
        try:
            consumer_digest = hashlib.sha256(
                state["consumer"].read_bytes()
            ).hexdigest()
        except OSError:
            consumer_digest = ""
        dependencies = [
            {"name": "psutil", "version": "5", "metadata_sha256": "a" * 64,
             "record_sha256": "b" * 64, "files_count": 1,
             "files_sha256": "1" * 64},
            {"name": "pytest", "version": "8", "metadata_sha256": "c" * 64,
             "record_sha256": "d" * 64, "files_count": 1,
             "files_sha256": "2" * 64},
            {"name": "transitive-package", "version": state["transitive"],
             "metadata_sha256": "e" * 64, "record_sha256": "f" * 64,
             "files_count": 1, "files_sha256": consumer_digest},
        ]
        if state["probe"] == "duplicate":
            dependencies.append(dict(dependencies[-1]))
        elif state["probe"] == "incomplete":
            dependencies[-1]["record_sha256"] = ""
        data = {
            "interpreter_sha256": hashlib.sha256(ephemeral.read_bytes()).hexdigest(),
            "interpreter_size": ephemeral.stat().st_size,
            "version": "3.11", "dependencies": dependencies,
            "uv_bootstrap": [{
                "path": "site-packages[0]/_uv_ephemeral_overlay.pth",
                "size": len(state["overlay"]),
                "sha256": hashlib.sha256(state["overlay"]).hexdigest(),
            }, {
                "path": "site-packages[0]/_virtualenv.pth",
                "size": len(state["bootstrap_pth"]),
                "sha256": hashlib.sha256(state["bootstrap_pth"]).hexdigest(),
            }, {
                "path": "site-packages[0]/_virtualenv.py",
                "size": len(state["bootstrap"]),
                "sha256": hashlib.sha256(state["bootstrap"]).hexdigest(),
            }],
            "import_sources_known": True, "product_import_paths": [],
        }
        ephemeral.unlink()
        return subprocess.CompletedProcess(argv, 0, json.dumps(data), "")

    monkeypatch.setattr(stages.subprocess, "run", probe)
    return state, runner


def test_uv_temporary_interpreter_identity_survives_cleanup(repo: Path, monkeypatch):
    _fake_uv_probe(repo, monkeypatch)
    command = ("UV_CACHE_DIR=/tmp/forge-lean-uv-cache "
               "UV_TOOL_DIR=/tmp/forge-lean-uv-tools "
               "uv run --python 3.11 --with pytest --with psutil "
               "python -m pytest tests/a.py")
    first = stages._proof_tool_identity(repo, command)
    second = stages._proof_tool_identity(repo, command)
    assert first["reusable"] is True
    assert first == second
    assert first["interpreter"]["sha256"]
    assert not (repo / "temporary-interpreter").exists()
    assert "path" not in first["interpreter"]
    assert {row["name"] for row in first["dependencies"]} == {
        "pytest", "psutil", "transitive-package"}


def test_direct_python_probe_keeps_the_executed_venv_entrypoint(
        repo: Path, monkeypatch):
    """A venv symlink must remain the probe executable, not its base Python."""
    target = repo / "base-python"
    entrypoint = repo / "venv-python"
    target.write_bytes(b"base interpreter")
    entrypoint.symlink_to(target)
    detail = {
        "interpreter_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "interpreter_size": target.stat().st_size,
        "version": "3.11",
        "dependencies": [],
        "import_sources_known": True,
        "product_import_paths": [],
    }
    probes = []

    monkeypatch.setattr(stages.shutil, "which", lambda _name, **_kwargs:
                        str(entrypoint))

    def run(argv, **_kwargs):
        probes.append(argv)
        return subprocess.CompletedProcess(argv, 0, json.dumps(detail), "")

    snapshot = stages.product_tree_snapshot(repo)
    allowed_product_paths = {
        (repo / relative).resolve()
        for field in ("tracked", "dirty")
        for relative in (snapshot.get(field) or {})
    }
    monkeypatch.setattr(stages.subprocess, "run", run)
    identity = stages._proof_tool_identity(
        repo, "python3 -m compileall factory/scripts",
        allowed_product_paths=allowed_product_paths,
    )
    assert identity["reusable"] is True
    assert probes and probes[0][0] == str(entrypoint)
    assert identity["runner"]["path"] == str(target)


def test_compileall_reuse_binds_explicit_visible_sources_and_refuses_unknowns(
        repo: Path):
    known = stages._proof_tool_identity(
        repo, "python3 -m compileall factory/scripts",
    )
    assert known["reusable"] is True
    assert known["compileall_inputs"]

    for command in (
            "python3 -m compileall",
            "python3 -m compileall -q",
            "python3 -m compileall /tmp/forge-external-source",
    ):
        assert stages._proof_tool_identity(repo, command)["reusable"] is False

    ignored = repo / "ignored-sources"
    ignored.mkdir()
    (repo / ".gitignore").write_text("ignored-sources/\n", encoding="utf-8")
    (ignored / "source.py").write_text("value = 1\n", encoding="utf-8")
    assert stages._proof_tool_identity(
        repo, "python3 -m compileall ignored-sources",
    )["reusable"] is False

    linked_file = repo / "linked.py"
    linked_file.symlink_to(repo / "factory/scripts/forge.py")
    assert stages._proof_tool_identity(
        repo, "python3 -m compileall linked.py",
    )["reusable"] is False

    linked_parent = repo / "linked-parent"
    linked_parent.symlink_to(repo / "factory/scripts")
    assert stages._proof_tool_identity(
        repo, "python3 -m compileall linked-parent",
    )["reusable"] is False


def test_dedicated_proof_does_not_bind_an_unrelated_canonical_test_runner(
        repo: Path, monkeypatch):
    source = repo / "tests" / "a.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("def test_a():\n    pass\n", encoding="utf-8")
    (repo / "src").mkdir()
    task = {
        **_task(),
        "verify_commands": ["python3 -m compileall factory/scripts"],
    }
    monkeypatch.setenv("FACTORY_TEST_CMD", "python3 -m pytest tests")
    before = stages.proof_identity(repo, task, "tests")
    assert "canonical_test_tool" not in before["inputs"]["semantic"]

    cache = repo / "tests" / "__pycache__"
    cache.mkdir()
    (cache / "a.cpython-311.pyc").write_bytes(b"pytest cache")
    after = stages.proof_identity(repo, task, "tests")
    assert after["identity"] == before["identity"]


def test_metadata_only_head_and_effective_board_inputs(repo: Path):
    task = {**_task(), "verify_commands": [
        "python3 factory/scripts/check_board_complete.py", "git diff --check"]}
    before = stages.proof_identity(repo, task, "verify")
    assert before["reusable"] is True
    event = repo / ".factory" / "events" / "proof-bookkeeping.json"
    event.parent.mkdir(parents=True, exist_ok=True)
    event.write_text(json.dumps({"event": "verified", "story": "S1"}),
                     encoding="utf-8")
    git(repo, "add", ".factory/events/proof-bookkeeping.json")
    git(repo, "commit", "-qm", "record evidence")
    after = stages.proof_identity(repo, task, "verify")
    assert stages.product_tree_snapshot(repo)["head"]
    assert after["identity"] == before["identity"]
    event2 = repo / ".factory" / "events" / "pr-link.json"
    event2.write_text(json.dumps({"event": "pr-linked", "story": "S1"}),
                      encoding="utf-8")
    assert stages.proof_identity(repo, task, "verify")["identity"] != before["identity"]
    subprocess.run(["git", "config", "core.whitespace", "trailing-space"],
                   cwd=repo, check=True)
    assert (stages._proof_tool_identity(repo, "git diff --check")
            != before["inputs"]["tools"][1])


def test_equivalent_board_argv_binds_inputs_and_unknown_shape_forces_fresh(
        repo: Path):
    script = repo / "factory/scripts/check_board_complete.py"
    task = {**_task(), "verify_commands": [
        f"UV_CACHE_DIR=/tmp/forge-lean-uv-cache python3 {script}"]}
    before = stages.proof_identity(repo, task, "verify")
    assert before["reusable"] is True
    assert before["inputs"]["board_inputs"] is not None
    event = repo / ".factory/events/board-link.json"
    event.parent.mkdir(parents=True, exist_ok=True)
    event.write_text(json.dumps({"event": "pr-linked", "story": "S1"}), encoding="utf-8")
    after = stages.proof_identity(repo, task, "verify")
    assert after["identity"] != before["identity"]
    unknown = {**task, "verify_commands": [
        "python3 -u factory/scripts/check_board_complete.py"]}
    assert stages.proof_identity(repo, unknown, "verify")["reusable"] is False
    malformed = {**task, "verify_commands": [
        "python3 'factory/scripts/check_board_complete.py"]}
    assert stages.proof_identity(repo, malformed, "verify")["reusable"] is False


def test_canonical_verifier_binds_workflow_inputs_and_unknown_python_reruns(
        repo: Path):
    command = "python3 factory/scripts/verify.py"
    first = stages._proof_tool_identity(repo, command)
    assert first["reusable"] is False
    assert first["canonical_verify_inputs"]
    state = load_factory_lib(repo).run_state_path(repo)
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"issue_key": "changed"}), encoding="utf-8")
    second = stages._proof_tool_identity(repo, command)
    assert second["canonical_verify_inputs"] != first["canonical_verify_inputs"]
    assert stages._proof_tool_identity(
        repo, "python3 factory/scripts/check_dual_runtime.py",
    )["reusable"] is False


def test_probe_changes_interpreter_dependency_and_runner_inputs(repo: Path, monkeypatch):
    state, runner = _fake_uv_probe(repo, monkeypatch)
    command = "uv run --python 3.11 --with pytest python -m pytest tests/a.py"
    base = stages._proof_tool_identity(repo, command)
    assert base["reusable"] is True
    state["interpreter"] = b"ephemeral Python v2"
    changed = stages._proof_tool_identity(repo, command)
    assert changed["reusable"] is True
    assert changed["interpreter"] != base["interpreter"]
    state["interpreter"] = b"ephemeral Python v1"
    state["transitive"] = "2"
    changed = stages._proof_tool_identity(repo, command)
    assert changed["dependencies"] != base["dependencies"]
    state["probe"] = "incomplete"
    assert stages._proof_tool_identity(repo, command)["reusable"] is False
    state["probe"] = "duplicate"
    assert stages._proof_tool_identity(repo, command)["reusable"] is False
    runner.write_bytes(b"fake uv runner v2")
    assert stages._proof_tool_identity(repo, command)["runner"] != base["runner"]


def test_uv_bootstrap_overlay_bytes_bind_proof_reuse(repo: Path, monkeypatch):
    state, _runner = _fake_uv_probe(repo, monkeypatch)
    command = "uv run --with pytest python -m pytest tests/a.py"
    baseline = stages._proof_tool_identity(repo, command)
    assert baseline["reusable"] is True
    state["bootstrap"] = b"uv bootstrap v2"
    changed = stages._proof_tool_identity(repo, command)
    assert changed["reusable"] is True
    assert changed["uv_bootstrap"] != baseline["uv_bootstrap"]
    state["bootstrap_pth"] = b"import _virtualenv\n# changed"
    pth_changed = stages._proof_tool_identity(repo, command)
    assert pth_changed["reusable"] is True
    assert pth_changed["uv_bootstrap"] != changed["uv_bootstrap"]
    state["overlay"] = b"import site; site.addsitedir(\"/uv/other\")"
    overlay_changed = stages._proof_tool_identity(repo, command)
    assert overlay_changed["reusable"] is True
    assert overlay_changed["uv_bootstrap"] != pth_changed["uv_bootstrap"]


def test_dependency_file_bytes_bind_reuse_and_missing_files_refuse(
        repo: Path, monkeypatch):
    state, _runner = _fake_uv_probe(repo, monkeypatch)
    command = "uv run --python 3.11 --with pytest python -m pytest tests/a.py"
    baseline = stages._proof_tool_identity(repo, command)
    assert baseline["reusable"] is True
    state["consumer"].write_text("VALUE = 2\n", encoding="utf-8")
    changed = stages._proof_tool_identity(repo, command)
    assert changed["reusable"] is True
    assert changed["dependencies"] != baseline["dependencies"]
    state["consumer"].unlink()
    assert stages._proof_tool_identity(repo, command)["reusable"] is False


def test_dependency_probe_hashes_real_recorded_files_and_refuses_editable_dist(
        repo: Path, monkeypatch):
    """Exercise the embedded probe against a real RECORD, not mocked rows."""
    site = repo / "probe-site"
    dist_info = site / "setuptools-80.9.0.dist-info"
    site.mkdir()
    dist_info.mkdir()
    module = site / "fixture_module.py"
    module.write_text("VALUE = 1\n", encoding="utf-8")
    metadata = dist_info / "METADATA"
    metadata.write_text(
        "Metadata-Version: 2.1\nName: setuptools\nVersion: 80.9.0\n",
        encoding="utf-8",
    )
    pth = site / "distutils-precedence.pth"
    pth.write_text(
        "import os; var = 'SETUPTOOLS_USE_DISTUTILS'; "
        "enabled = os.environ.get(var, 'local') == 'local'; "
        "enabled and __import__('_distutils_hack').add_shim();\n",
        encoding="utf-8",
    )
    (dist_info / "RECORD").write_text(
        "fixture_module.py,,\n"
        "distutils-precedence.pth,,\n"
        "setuptools-80.9.0.dist-info/METADATA,,\n"
        "setuptools-80.9.0.dist-info/RECORD,,\n",
        encoding="utf-8",
    )

    real_which = stages.shutil.which
    real_run = stages.subprocess.run
    monkeypatch.setattr(
        stages.shutil, "which",
        lambda command, **kwargs: (
            sys.executable if command == "python3"
            else real_which(command, **kwargs)
        ),
    )

    def run_with_fixture_discovery(argv, *args, **kwargs):
        # Keep the production probe source unchanged. Only its distribution
        # discovery is replaced, so all RECORD parsing and byte hashing run in
        # a real interpreter.
        if (len(argv) >= 3 and argv[0] == sys.executable
                and argv[-2] == "-c"):
            script = argv[-1]
            bootstrap = (
                "import importlib.metadata as _metadata, pathlib\n"
                "_metadata.distributions = lambda: "
                f"[_metadata.PathDistribution(pathlib.Path({str(dist_info)!r}))]\n"
                "import sys as _sys\n"
                f"_sys.path[:] = [{str(site)!r}] + [entry for entry in _sys.path "
                "if 'site-packages' not in entry]\n"
                f"exec({script!r}, globals(), globals())\n"
            )
            argv = [*argv[:-1], bootstrap]
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(stages.subprocess, "run", run_with_fixture_discovery)
    command = "python3 -m compileall factory/scripts"
    baseline = stages._proof_tool_identity(repo, command)
    assert baseline["reusable"] is True, baseline
    baseline_dependency = baseline["dependencies"][0]
    assert baseline_dependency["name"] == "setuptools"
    assert baseline_dependency["files_count"] == 4

    metadata.write_text(
        "Metadata-Version: 2.1\nName: unrelated-dist\nVersion: 80.9.0\n",
        encoding="utf-8",
    )
    assert stages._proof_tool_identity(repo, command)["reusable"] is False
    metadata.write_text(
        "Metadata-Version: 2.1\nName: setuptools\nVersion: 80.9.0\n",
        encoding="utf-8",
    )

    module.write_text("VALUE = 2\n", encoding="utf-8")
    changed = stages._proof_tool_identity(repo, command)
    assert changed["reusable"] is True
    assert changed["dependencies"] != baseline["dependencies"]
    assert changed["dependencies"][0]["files_sha256"] != \
        baseline_dependency["files_sha256"]

    module.unlink()
    assert stages._proof_tool_identity(repo, command)["reusable"] is False

    module.write_text("VALUE = 3\n", encoding="utf-8")
    pth.write_text(pth.read_text(encoding="utf-8") + "import unrelated\n",
                   encoding="utf-8")
    assert stages._proof_tool_identity(repo, command)["reusable"] is False
    pth.write_text(
        "import os; var = 'SETUPTOOLS_USE_DISTUTILS'; "
        "enabled = os.environ.get(var, 'local') == 'local'; "
        "enabled and __import__('_distutils_hack').add_shim();\n",
        encoding="utf-8",
    )
    linked_cache = site / "__pycache__" / "fixture_module.cpython-311.pyc"
    linked_cache.parent.mkdir()
    linked_target = repo / "linked-bytecode-target"
    linked_target.write_bytes(b"linked bytecode")
    linked_cache.symlink_to(linked_target)
    (dist_info / "RECORD").write_text(
        "fixture_module.py,,\n"
        "distutils-precedence.pth,,\n"
        "__pycache__/fixture_module.cpython-311.pyc,,\n"
        "setuptools-80.9.0.dist-info/METADATA,,\n"
        "setuptools-80.9.0.dist-info/RECORD,,\n",
        encoding="utf-8",
    )
    assert stages._proof_tool_identity(repo, command)["reusable"] is False

    (dist_info / "direct_url.json").write_text(
        json.dumps({"url": str(site), "dir_info": {"editable": True}}),
        encoding="utf-8",
    )
    assert stages._proof_tool_identity(repo, command)["reusable"] is False


def test_proof_identity_binds_environment_without_persisting_secrets(
        repo: Path, monkeypatch):
    _fake_uv_probe(repo, monkeypatch)
    task = {**_task(),
            "required_tests": [{**_task()["required_tests"][0],
                                "command": "uv run --with pytest python tests/a.py"}],
            "verify_commands": ["uv run --with pytest python -m pytest tests/a.py"]}
    monkeypatch.setenv("FACTORY_TEST_CMD", "secret-command-one")
    monkeypatch.setenv("PYTEST_ADDOPTS", "secret-options-one")
    first = {
        kind: stages.proof_identity(repo, task, kind, product_tree={})
        for kind in ("verify", "tests")
    }
    serialized = json.dumps(first, sort_keys=True)
    for secret in (
            "FACTORY_TEST_CMD", "PYTEST_ADDOPTS", "secret-command-one",
            "secret-options-one"):
        assert secret not in serialized
    assert all(set(identity["inputs"]["tools"][0]["environment"])
               == {"sha256", "entries", "inherited_pythonutf8_sha256",
                   "inherited_canonical_junit_sha256"}
               for identity in first.values())

    monkeypatch.setenv("FACTORY_TEST_CMD", "secret-command-two")
    changed_command_env = {
        kind: stages.proof_identity(repo, task, kind, product_tree={})
        for kind in ("verify", "tests")
    }
    assert all(changed_command_env[kind]["identity"] != first[kind]["identity"]
               for kind in first)
    monkeypatch.setenv("PYTEST_ADDOPTS", "secret-options-two")
    changed_generic_env = {
        kind: stages.proof_identity(repo, task, kind, product_tree={})
        for kind in ("verify", "tests")
    }
    assert all(changed_generic_env[kind]["identity"]
               != changed_command_env[kind]["identity"] for kind in first)

    monkeypatch.setenv("FORGE_CANONICAL_JUNIT", "inherited-report-one")
    inherited_one = {
        kind: stages.proof_identity(repo, task, kind, product_tree={})["identity"]
        for kind in ("verify", "tests")
    }
    monkeypatch.setenv("FORGE_CANONICAL_JUNIT", "inherited-report-two")
    inherited_two = {
        kind: stages.proof_identity(repo, task, kind, product_tree={})["identity"]
        for kind in ("verify", "tests")
    }
    assert inherited_one != inherited_two

    monkeypatch.setenv("FORGE_PROCESS_TOKEN", "generated-nonce-one")
    monkeypatch.setenv("PYTHONUTF8", "0")
    normalized = {
        kind: stages.proof_identity(repo, task, kind, product_tree={})["identity"]
        for kind in ("verify", "tests")
    }
    monkeypatch.setenv("FORGE_PROCESS_TOKEN", "generated-nonce-two")
    monkeypatch.setenv("PYTHONUTF8", "different-fixed-input")
    assert normalized != {
        kind: stages.proof_identity(repo, task, kind, product_tree={})["identity"]
        for kind in ("verify", "tests")
    }


def test_proof_reuse_refuses_dependency_environment_and_configuration_drift(
        repo: Path, monkeypatch):
    state, _runner = _fake_uv_probe(repo, monkeypatch)
    generated = repo / "generated.json"
    generated.write_text('{"version": 1}\n', encoding="utf-8")
    task = {
        **_task(),
        "required_tests": [{
            **_task()["required_tests"][0],
            "command": "uv run --with pytest python -m pytest tests/a.py",
        }],
        "verify_commands": [
            "uv run --with pytest python -m pytest tests/a.py",
        ],
        "generated_semantic_inputs": ["generated.json"],
    }
    product = {
        "files": {"src/a.py": "one"},
        "tracked": {"tests/a.py": "fixture"},
        "dirty": {},
    }

    def identities() -> dict[str, str]:
        return {
            kind: stages.proof_identity(
                repo, task, kind, product_tree=product,
            )["identity"]
            for kind in ("verify", "tests")
        }

    baseline = identities()
    product["files"]["src/a.py"] = "two"
    assert identities() != baseline
    product["files"]["src/a.py"] = "one"

    task["required_tests"][0]["command"] += " -k test_a"
    assert identities()["tests"] != baseline["tests"]
    task["required_tests"][0]["command"] = (
        "uv run --with pytest python -m pytest tests/a.py"
    )

    state["transitive"] = "2"
    dependency = identities()
    assert dependency != baseline
    state["transitive"] = "1"

    monkeypatch.setenv("PYTEST_ADDOPTS", "--strict-markers")
    environment = identities()
    assert environment != baseline
    monkeypatch.delenv("PYTEST_ADDOPTS")

    config = repo / "pytest.ini"
    config.write_text("[pytest]\naddopts = -x\n", encoding="utf-8")
    assert all(stages.proof_identity(
        repo, task, kind, product_tree=product,
    )["reusable"] is False for kind in ("verify", "tests"))
    config.write_text("[pytest]\naddopts = -q\n", encoding="utf-8")

    generated.write_text('{"version": 2}\n', encoding="utf-8")
    assert identities()["verify"] != baseline["verify"]

    state["probe"] = "incomplete"
    assert all(stages.proof_identity(
        repo, task, kind, product_tree=product,
    )["reusable"] is False for kind in ("verify", "tests"))


def test_proof_reuse_refuses_mutable_external_pythonpath_but_accepts_product_and_recorded_sources(
        repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source = repo / "tests" / "a.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("def test_a():\n    pass\n", encoding="utf-8")
    task = {**_task(), "verify_commands": ["python3 -m pytest tests/a.py"]}

    external = tmp_path / "mutable-imports"
    external.mkdir()
    (external / "mutable_module.py").write_text(
        "VALUE = 1\n", encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(external))
    assert stages.proof_identity(repo, task, "verify")["reusable"] is False

    monkeypatch.setenv("PYTHONPATH", str(repo / "tests"))
    assert stages.proof_identity(repo, task, "verify")["reusable"] is True

    recorded = tmp_path / "recorded-imports"
    recorded.mkdir()
    module = recorded / "recorded_module.py"
    module.write_text("VALUE = 1\n", encoding="utf-8")
    dist = recorded / "recorded_dist-1.0.dist-info"
    dist.mkdir()
    (dist / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: recorded-dist\nVersion: 1.0\n",
        encoding="utf-8",
    )
    (dist / "RECORD").write_text(
        "recorded_module.py,,\n"
        "recorded_dist-1.0.dist-info/METADATA,,\n"
        "recorded_dist-1.0.dist-info/RECORD,,\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(recorded))
    assert stages.proof_identity(repo, task, "verify")["reusable"] is True


def test_proof_reuse_refuses_unbound_import_root_inside_product_tree(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    ignored = repo / "ignored-imports"
    ignored.mkdir()
    (repo / ".gitignore").write_text("ignored-imports/\n", encoding="utf-8")
    (ignored / "mutable_module.py").write_text(
        "VALUE = 1\n", encoding="utf-8",
    )
    task = {**_task(), "verify_commands": ["python3 -m pytest tests/a.py"]}

    monkeypatch.setenv("PYTHONPATH", str(ignored))
    assert stages.proof_identity(repo, task, "verify")["reusable"] is False


def test_pytest_addopts_config_bytes_are_bound_without_persisting_paths(
        repo: Path, monkeypatch):
    _fake_uv_probe(repo, monkeypatch)
    config = repo.parent / "private pytest.ini"
    config.write_text("[pytest]\naddopts = -q\n", encoding="utf-8")
    monkeypatch.setenv("PYTEST_ADDOPTS", f"-c '{config}'")
    command = "uv run --with pytest python -m pytest tests/a.py"
    first = stages._proof_tool_identity(repo, command)
    assert first["reusable"] is False
    serialized = json.dumps(first, sort_keys=True)
    assert str(config) not in serialized
    config.write_text("[pytest]\naddopts = -x\n", encoding="utf-8")
    changed = stages._proof_tool_identity(repo, command)
    assert changed["reusable"] is False
    config.unlink()
    assert stages._proof_tool_identity(repo, command)["reusable"] is False

    config.write_text("[pytest]\n", encoding="utf-8")
    conflict = stages._proof_tool_identity(
        repo, f"{command} --config-file={repo / 'pytest.ini'}",
    )
    assert conflict["reusable"] is False
    monkeypatch.setenv("PYTEST_ADDOPTS", "-c 'unterminated")
    assert stages._proof_tool_identity(repo, command)["reusable"] is False


@pytest.mark.parametrize("config_name", [
    "pytest.ini", ".pytest.ini", "pytest.toml", ".pytest.toml",
    "pyproject.toml", "tox.ini", "setup.cfg",
])
def test_implicitly_discovered_pytest_config_bytes_are_bound(
        repo: Path, monkeypatch, config_name: str):
    _fake_uv_probe(repo, monkeypatch)
    config = repo / config_name
    config.write_text("[pytest]\naddopts = -q\n", encoding="utf-8")
    command = "uv run --with pytest python -m pytest tests/a.py"
    first = stages._proof_tool_identity(repo, command)
    assert first["reusable"] is False
    config.write_text("[pytest]\naddopts = -x\n", encoding="utf-8")
    changed = stages._proof_tool_identity(repo, command)
    assert changed["reusable"] is False


def test_run_stage_proof_memoizes_tool_probe_by_prefix_and_environment(
        repo: Path, monkeypatch):
    state, _runner = _fake_uv_probe(repo, monkeypatch)
    task = {**_task(),
            "required_tests": [{**_task()["required_tests"][0],
                                "command": "uv run --with pytest python tests/a.py"}],
            "verify_commands": ["uv run --with pytest python -m pytest tests/a.py"]}
    test_file = repo / "tests/a.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("pass\n", encoding="utf-8")
    visible_tree = {"tracked": {"tests/a.py": "fixture"}, "dirty": {}}
    monkeypatch.setattr(stages, "product_tree_snapshot",
                        lambda _base: visible_tree)
    monkeypatch.setattr(stages, "protected_authority_snapshot", lambda _base: {})
    # This identity-memoization fixture has no lifecycle pointer by design;
    # make that absent story explicit without masking authoritative read errors.
    monkeypatch.setattr(stages, "raw_run_state", lambda _base: {})
    monkeypatch.setattr(stages, "active_story_key", lambda _base: "")
    monkeypatch.setattr(stages, "_proof_receipt", lambda *_args: {})
    monkeypatch.setattr(stages, "_store_proof_receipt", lambda *_args: None)
    monkeypatch.setattr(stages, "_run_verify_commands", lambda *_args: None)
    monkeypatch.setattr(stages, "_run_required_tests", lambda *_args: ([], []))
    stages.run_stage_proof(repo, "T1", task)
    assert len(state["calls"]) == 1

    memo = {}
    stages.proof_identity(
        repo, task, "verify", product_tree=visible_tree, tool_probe_memo=memo,
    )
    stages.proof_identity(
        repo, task, "tests", product_tree=visible_tree, tool_probe_memo=memo,
    )
    assert len(state["calls"]) == 2

    changed = copy.deepcopy(task)
    changed["verify_commands"][0] = (
        "uv run --with pytest --with pytest-xdist python -m pytest tests/a.py"
    )
    stages.proof_identity(
        repo, changed, "verify", product_tree=visible_tree, tool_probe_memo=memo,
    )
    assert len(state["calls"]) == 3
    monkeypatch.setenv("PYTHONPATH", "different-probe-environment")
    stages.proof_identity(
        repo, task, "verify", product_tree=visible_tree, tool_probe_memo=memo,
    )
    # An unknown external PYTHONPATH is rejected before a child probe starts;
    # memoization must not turn that conservative refusal into a reusable row.
    assert len(state["calls"]) == 3
    assert stages.proof_identity(
        repo, task, "verify", product_tree=visible_tree,
        tool_probe_memo=memo,
    )["reusable"] is False
