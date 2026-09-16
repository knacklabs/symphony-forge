"""The shared gate table matches Lean's runnable cold-read contract."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from test_gates import HARNESS, git, load_factory_lib, repo  # noqa: F401

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from grill_gates import GATES  # noqa: E402


ALL_GATES = sorted(GATES)


def test_the_table_covers_every_gate_the_recorder_accepts():
    recorder = (HARNESS / "factory" / "scripts"
                / "record_grill_from_json.py").read_text(encoding="utf-8")
    schema = json.loads((HARNESS / "factory" / "schemas" / "grill.json"
                         ).read_text(encoding="utf-8"))
    documented = schema["recorded_by"].split("--gate ", 1)[1].split()[0]
    assert set(documented.split("|")) == set(ALL_GATES)
    assert ALL_GATES == ["epics", "plan", "signoff", "spec", "task"]
    assert "choices=gate_names()" in recorder
    assert "GATE_ROUND_FLOORS" not in recorder
    assert "frontier_empty" not in recorder


@pytest.mark.parametrize("gate", ALL_GATES)
def test_every_gate_can_be_located_and_composed(repo, gate):
    sys.path.insert(0, str(repo / "factory" / "scripts"))
    from forge_cli.grill import _artifact_text, _compose_brief

    lib = load_factory_lib(repo)
    control = Path(git(repo, "rev-parse", "--absolute-git-dir")) / "forge"
    control.mkdir(parents=True, exist_ok=True)
    lib.dump_json(control / "run.json", {"issue_key": "ENG-1"})

    marker = f"UNIQUE-MARKER-FOR-{gate}"
    task_id = ""
    file_arg = ""
    if gate == "task":
        task_id = "T1"
        plan = lib.evidence_path(
            repo, "ENG-1", "task-plans/T1.md", for_write=True)
        plan.parent.mkdir(parents=True, exist_ok=True)
        plan.write_text(f"# T1\n\n{marker}\n", encoding="utf-8")
    elif gate == "spec":
        path = repo / "docs/specs/thing.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# Thing\n\n{marker}\n", encoding="utf-8")
        file_arg = "docs/specs/thing.md"
    elif gate == "epics":
        path = repo / "proposal.json"
        path.write_text(json.dumps({"epics": [{"id": marker}]}),
                        encoding="utf-8")
        file_arg = "proposal.json"
    elif gate == "plan":
        path = repo / "draft.md"
        path.write_text(f"# Draft\n\n{marker}\n", encoding="utf-8")
        file_arg = "draft.md"
    else:
        path = repo / "docs/product/BRIEF.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# Brief\n\n{marker}\n", encoding="utf-8")

    label, artifact = _artifact_text(repo, gate, task_id, file_arg)
    brief = _compose_brief(repo, gate, label, artifact)
    assert marker in artifact and marker in brief
    assert "You did NOT write what follows" in brief
    assert "ONE independent cold read" in brief


def test_schema_and_recorder_require_dispositions_not_rounds():
    schema = json.loads((HARNESS / "factory" / "schemas" / "grill.json"
                         ).read_text(encoding="utf-8"))
    assert "finding_dispositions" in schema["required"]
    assert "rounds" not in schema["required"]
    assert "rounds" not in schema["optional"]
    assert "cold_input_sha256" in schema["optional"]
    assert "final_artifact_sha256" in schema["optional"]
