from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

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
        kind: {"status": "passed", "identity":
               stages.proof_identity(repo, task, kind)["identity"]}
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
                        calls.append("tests") or [])
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
    config = tmp_path / "shared-pytest.ini"
    config.write_text("[pytest]\naddopts = -q\n", encoding="utf-8")
    task = _task()
    task["required_tests"][0]["command"] = (
        f"python -m pytest -c {config} tests/a.py -k test_a"
    )
    before = stages.proof_identity(repo, task, "tests")
    assert before["reusable"] is True
    config.write_text("[pytest]\naddopts = -q --strict-markers\n", encoding="utf-8")
    after = stages.proof_identity(repo, task, "tests")
    assert after["identity"] != before["identity"]
    config.unlink()
    assert stages.proof_identity(repo, task, "tests")["reusable"] is False


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


def _fake_uv_probe(repo: Path, monkeypatch) -> tuple[dict, Path]:
    runner = repo / "fake-uv"
    runner.write_bytes(b"fake uv runner v1")
    state = {"interpreter": b"ephemeral Python v1", "transitive": "1",
             "probe": "complete", "calls": []}
    real_which = stages.shutil.which
    monkeypatch.setattr(stages.shutil, "which", lambda command, **kwargs:
                        str(runner) if command == "uv" else
                        real_which(command, **kwargs))

    def probe(argv, **_kwargs):
        assert argv[0] == "uv" and "-c" in argv
        state["calls"].append(tuple(argv))
        ephemeral = repo / "temporary-interpreter"
        ephemeral.write_bytes(state["interpreter"])
        dependencies = [
            {"name": "psutil", "version": "5", "metadata_sha256": "a" * 64,
             "record_sha256": "b" * 64},
            {"name": "pytest", "version": "8", "metadata_sha256": "c" * 64,
             "record_sha256": "d" * 64},
            {"name": "transitive-package", "version": state["transitive"],
             "metadata_sha256": "e" * 64, "record_sha256": "f" * 64},
        ]
        if state["probe"] == "duplicate":
            dependencies.append(dict(dependencies[-1]))
        elif state["probe"] == "incomplete":
            dependencies[-1]["record_sha256"] = ""
        data = {
            "interpreter_sha256": hashlib.sha256(ephemeral.read_bytes()).hexdigest(),
            "interpreter_size": ephemeral.stat().st_size,
            "version": "3.11", "dependencies": dependencies,
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
    assert first["reusable"] is True
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
               == {"sha256", "entries"} for identity in first.values())

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

    monkeypatch.setenv("FORGE_PROCESS_TOKEN", "generated-nonce-one")
    monkeypatch.setenv("PYTHONUTF8", "0")
    normalized = {
        kind: stages.proof_identity(repo, task, kind, product_tree={})["identity"]
        for kind in ("verify", "tests")
    }
    monkeypatch.setenv("FORGE_PROCESS_TOKEN", "generated-nonce-two")
    monkeypatch.setenv("PYTHONUTF8", "different-fixed-input")
    assert normalized == {
        kind: stages.proof_identity(repo, task, kind, product_tree={})["identity"]
        for kind in ("verify", "tests")
    }


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
    monkeypatch.setattr(stages, "product_tree_snapshot", lambda _base: {})
    monkeypatch.setattr(stages, "protected_authority_snapshot", lambda _base: {})
    monkeypatch.setattr(stages, "_proof_receipt", lambda *_args: {})
    monkeypatch.setattr(stages, "_store_proof_receipt", lambda *_args: None)
    monkeypatch.setattr(stages, "_run_verify_commands", lambda *_args: None)
    monkeypatch.setattr(stages, "_run_required_tests", lambda *_args: [])
    stages.run_stage_proof(repo, "T1", task)
    assert len(state["calls"]) == 1

    memo = {}
    stages.proof_identity(
        repo, task, "verify", product_tree={}, tool_probe_memo=memo,
    )
    stages.proof_identity(
        repo, task, "tests", product_tree={}, tool_probe_memo=memo,
    )
    assert len(state["calls"]) == 2

    changed = copy.deepcopy(task)
    changed["verify_commands"][0] = (
        "uv run --with pytest --with pytest-xdist python -m pytest tests/a.py"
    )
    stages.proof_identity(
        repo, changed, "verify", product_tree={}, tool_probe_memo=memo,
    )
    assert len(state["calls"]) == 3
    monkeypatch.setenv("PYTHONPATH", "different-probe-environment")
    stages.proof_identity(
        repo, task, "verify", product_tree={}, tool_probe_memo=memo,
    )
    assert len(state["calls"]) == 4
