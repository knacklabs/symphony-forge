from __future__ import annotations

import sys
from pathlib import Path

from test_gates import HARNESS, repo  # noqa: F401

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from forge_cli import stages  # noqa: E402


def test_proof_identity_uses_normalized_environment(repo: Path, monkeypatch):
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
    monkeypatch.setenv("PYTHONUTF8", "1")
    assert identities() == baseline

    task["required_tests"][0]["command"] += " -k test_a"
    changed = identities()
    assert changed["tests"] != baseline["tests"]
    assert changed["verify"] == baseline["verify"]
