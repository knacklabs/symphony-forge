"""Regressions for worker access and offline test execution."""
from __future__ import annotations

import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from forge_cli import codex_runtime, delegate, doctor, review_brief  # noqa: E402


def test_required_test_runner_uses_local_pytest_without_uv(tmp_path):
    test_file = tmp_path / "test_sample.py"
    test_file.write_text("def test_sample():\n    pass\n", encoding="utf-8")
    report = tmp_path / "junit.xml"
    uv = tmp_path / "uv"
    uv.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    uv.chmod(0o755)

    result = subprocess.run(
        [sys.executable, str(HARNESS / "factory/scripts/run_tests.py"),
         "test_sample.py", "test_sample", str(report)],
        cwd=tmp_path, env={**os.environ, "PATH": str(tmp_path)},
        capture_output=True, text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    cases = ET.parse(report).getroot().iter("testcase")
    case = next(cases)
    assert case.get("name") == "test_sample"
    assert case.get("file", "").endswith("test_sample.py")


def test_codex_scope_is_coordinator_owned_in_brief_and_launch_output(
        tmp_path, monkeypatch, capsys):
    task = {
        "id": "T1", "title": "Update Codex hook", "objective": "Update hook.",
        "write_scope": [".codex/hooks.json"],
        "acceptance_criteria": [], "required_tests": [], "verify_commands": [],
        "reviewer_focus": "Keep the hook valid.",
    }
    monkeypatch.setattr(
        "forge_cli.stages.effective_scope",
        lambda *_args: [".codex/hooks.json"],
    )
    monkeypatch.setattr(delegate, "decision_records", lambda *_args: [])
    monkeypatch.setattr(delegate, "relevant_lessons", lambda *_args: [])
    monkeypatch.setattr(review_brief, "_settled_section", lambda *_args: [])
    brief = delegate.compose_brief(
        tmp_path, task, write=True, user_facing=False, story="",
        scope_override=[".codex/hooks.json"],
    )
    assert "Coordinator-owned paths (do not edit; the coordinator applies these):" in brief
    assert "- .codex/hooks.json" in brief
    assert "YES — edit worker-owned paths only" in brief

    monkeypatch.setattr(codex_runtime, "coordinator_runtime", lambda: "codex")
    brief_path = tmp_path / ".factory/diagnostic-briefs/T1.md"
    monkeypatch.setattr(delegate, "safe_factory_write_bytes", lambda *_args: True)
    monkeypatch.setattr(delegate, "sha256_of", lambda *_args: "digest")
    delegate.launch_companion(
        tmp_path, task_id="T1", text=brief, path=brief_path,
        task_sha256_value="task", model="", effort="", write=True,
        write_scope=[".codex/hooks.json"], print_only=True,
        emit_descriptor=False,
    )
    output = capsys.readouterr().out
    assert "Coordinator-owned paths (do not edit; the coordinator applies these):\n- .codex/hooks.json" in output


def test_doctor_offline_pytest_check_is_advisory(monkeypatch):
    def unavailable(_name):
        raise ImportError

    monkeypatch.setattr(doctor.importlib, "import_module", unavailable)

    check = doctor._offline_pytest_check()

    assert check["name"] == "offline required-test runner"
    assert check["ok"] is False
    assert check["required"] is False
    assert doctor._display_mark(check) == "opt "
