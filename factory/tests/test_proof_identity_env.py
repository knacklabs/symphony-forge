from __future__ import annotations

import sys
from pathlib import Path

from test_gates import HARNESS, git, head, repo  # noqa: F401

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from factory_lib import (  # noqa: E402
    dump_json, protected_decomposition_state_path, run_state_path,
)
from forge_cli.close import _commit_task_proof  # noqa: E402
from forge_cli.review import pre_review_proof_problems  # noqa: E402
from forge_cli import stages  # noqa: E402


def test_proof_identity_binds_full_effective_environment(repo: Path, monkeypatch):
    task = {
        "required_tests": [{
            "id": "test_a", "path": "tests/a.py",
            "command": "python3 -m pytest tests/a.py",
        }],
        "verify_commands": ["python3 -m compileall factory/scripts"],
    }

    def identities() -> dict[str, str]:
        return {
            kind: stages.proof_identity(
                repo, task, kind, product_tree={},
            )["identity"]
            for kind in ("tests", "verify")
        }

    monkeypatch.delenv("PYTHONUTF8", raising=False)
    baseline = identities()
    monkeypatch.setenv("UNRELATED_PROOF_ENV", "extra")
    assert identities() != baseline
    monkeypatch.delenv("UNRELATED_PROOF_ENV")
    monkeypatch.setenv("PYTHONUTF8", "1")
    assert identities() == baseline
    monkeypatch.delenv("PYTHONUTF8")

    task["required_tests"][0]["command"] += " -k test_a"
    changed = identities()
    assert changed["tests"] != baseline["tests"]
    assert changed["verify"] == baseline["verify"]


def test_close_proof_and_preflight_bind_same_effective_environment(
        repo: Path, monkeypatch):
    source = repo / "tests" / "a.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("def test_a():\n    pass\n", encoding="utf-8")
    (repo / ".envrc").write_text(
        'export FACTORY_TEST_CMD="python3 -m pytest tests"\n'
        'export FACTORY_TYPECHECK_CMD="python3 -m compileall tests"\n',
        encoding="utf-8",
    )
    git(repo, "config", "user.email", "test@knacklabs.dev")
    git(repo, "config", "user.name", "Gate Tests")
    git(repo, "add", "tests/a.py", ".envrc")
    git(repo, "commit", "-qm", "proof inputs")
    task = {
        "id": "T1", "write_scope": ["tests/a.py"],
        "verify_commands": ["python3 factory/scripts/verify.py"],
        "required_tests": [{
            "id": "test_a", "path": "tests/a.py",
            "command": "python3 -m pytest tests/a.py::test_a",
        }],
    }
    dump_json(run_state_path(repo), {"story": "S1", "issue_key": "S1"})
    dump_json(protected_decomposition_state_path(repo), {"tasks": [task]})
    stages.write_stages(repo, {"issue": "S1", "stages": [{
        "id": "T1", "status": "active", "proof_receipts": {},
    }]})
    monkeypatch.delenv("PYTHONUTF8", raising=False)
    monkeypatch.delenv("FORGE_CANONICAL_JUNIT", raising=False)
    monkeypatch.delenv("FACTORY_TEST_CMD", raising=False)
    monkeypatch.delenv("FACTORY_TYPECHECK_CMD", raising=False)
    monkeypatch.setattr(stages, "_run_verify_commands", lambda *_args: [{
        "command": task["verify_commands"][0], "exit_code": 0,
    }])
    monkeypatch.setattr(stages, "_run_required_tests", lambda *_args: (
        [], [{"id": "test_a", "path": "tests/a.py", "status": "passed"}],
    ))

    base_head = head(repo)
    context: dict[str, object] = {}
    proof = stages.run_stage_proof(repo, "T1", task, proof_context=context)
    _commit_task_proof(repo, "S1", "T1", proof, proof_context=context)
    before = {kind: stages._proof_receipt(repo, "T1", kind)
              for kind in ("verify", "tests")}
    assert all(before[kind]["inputs"] == context["proofs"][kind]["inputs"]
               for kind in before)

    # Both runners replace these inherited keys before launching the commands
    # represented by these receipts.
    monkeypatch.setenv("PYTHONUTF8", "0")
    monkeypatch.setenv("FORGE_CANONICAL_JUNIT", "inherited-report.xml")
    assert pre_review_proof_problems(
        repo, "S1", "T1", base_head, head(repo), proof_context=context,
    ) == []
    assert all(stages.proof_identity(repo, task, kind)["inputs"]
               == before[kind]["inputs"] for kind in before)
    monkeypatch.setenv("ARBITRARY_PROOF_INPUT", "changed")
    assert any("verify proof receipt identity is stale" in problem
               for problem in pre_review_proof_problems(
                   repo, "S1", "T1", base_head, head(repo),
                   proof_context=context,
               ))
