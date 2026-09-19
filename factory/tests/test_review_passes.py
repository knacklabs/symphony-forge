"""Passes over the whole task for a diff too big for one prompt (0081)."""
from __future__ import annotations

import sys

import pytest

from test_gates import HARNESS  # noqa: F401

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from forge_cli.review_passes import merge_pass_reports, pass_note, plan_passes  # noqa: E402


def test_passes_are_contiguous_slices_in_git_order_within_capacity():
    sizes = {"a": 40, "b": 50, "c": 30, "d": 90, "e": 10}
    assert plan_passes(sizes, 100) == [["a", "b"], ["c"], ["d", "e"]]
    assert plan_passes(sizes, 1000) == [["a", "b", "c", "d", "e"]]
    with pytest.raises(SystemExit):
        plan_passes({"lock": 200, "a": 1}, 100)  # one path alone over capacity
    with pytest.raises(SystemExit):
        plan_passes(sizes, 0)


def test_a_pass_is_told_what_it_holds_and_which_contracts_are_its():
    task = {"plan_contracts": [
        {"id": "C1", "statement": "x", "source": "p", "lands_in": "src/a.py"},
        {"id": "C2", "statement": "y", "source": "p", "lands_in": "src/c.py"},
        {"id": "C3", "statement": "z", "source": "p"},
    ]}
    note = pass_note(1, 2, ["src/a.py", "src/b.py"], ["src/c.py"], task)
    assert note.startswith("REVIEW PASS 1 OF 2")
    assert "holds the diff for: src/a.py, src/b.py" in note
    assert "Not in this pass (another pass holds them): src/c.py" in note
    assert "give one for C1, C3" in note and "give NONE for C2" in note


def _pass(findings, correctness="patch is correct", confidence=0.9, aside=None):
    report = {"findings": findings, "overall_correctness": correctness,
              "overall_explanation": "x", "overall_confidence": confidence,
              "provider_report": {"findings": findings, "overall_correctness": correctness,
                                  "overall_explanation": "x", "overall_confidence": confidence}}
    if aside:
        report["scope_rejected_findings"] = aside
    return report


def _finding(title, path, body="b", priority="P2"):
    return {"title": title, "body": body, "priority": priority, "confidence": 0.9,
            "category": "maintainability", "source_attribution": None,
            "code_location": {"file_path": path, "line": 1}}


def test_passes_merge_into_the_tools_own_chunked_shape():
    first = _pass([_finding("[quality] Name it", "src/a.py")])
    second = _pass([_finding("[quality] Name it", "src/a.py"),
                    _finding("[security] Token echoed", "src/b.py", priority="P1")],
                   correctness="patch is incorrect", confidence=0.8)
    merged = merge_pass_reports([first, second])
    assert [p["label"] for p in merged["pass_reports"]] == ["chunk 1/2", "chunk 2/2"]
    assert [f["title"] for f in merged["findings"]] == ["[quality] Name it",
                                                         "[security] Token echoed"]
    assert merged["findings"][0]["body"].startswith("chunk 1/2:")
    assert merged["findings"][1]["body"].startswith("chunk 2/2:")
    assert merged["overall_correctness"] == "patch is incorrect"
    assert merged["overall_confidence"] == 0.8
    assert merged["review_status"] == "findings" and "scope_rejected_findings" not in merged
    clean = merge_pass_reports([_pass([]), _pass([])])
    assert clean["review_status"] == "scoped-clean" and clean["findings"] == []
    with pytest.raises(SystemExit):
        merge_pass_reports([_pass([])])
