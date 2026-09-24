"""A repeated same-file review finding asks for the next fix approach."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from factory_lib import review_generation_id  # noqa: E402
from forge_cli import findings, fix, quickfix  # noqa: E402


def _review(base: Path, story: str, task: str, run: str, recorded_at: str,
            file_path: str, *, category: str = "bug") -> None:
    lenses = {
        aspect: {
            "blocking_findings": ([{"category": category, "file_path": file_path}]
                                  if aspect == "quality" else []),
            "non_blocking_findings": [],
        }
        for aspect in ("quality", "performance", "security")
    }
    generation = {
        "origin": "combined", "story": story, "task_id": task,
        "review_run_id": run, "recorded_at": recorded_at, "lenses": lenses,
    }
    generation["generation_id"] = review_generation_id(generation)
    path = (base / ".factory" / "stories" / story / "tasks" / task
            / "reviews" / "generations" / f"{generation['generation_id']}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(generation), encoding="utf-8")


def _prepare_fix(monkeypatch, base: Path, repeated_file: str | None):
    launched = {}
    monkeypatch.setattr(fix, "load_active", lambda _base: {
        "id": "lite-1", "profile": "lite", "max_files": 5,
    })
    monkeypatch.setattr(fix, "mode_run_config", lambda *_args: ("model", "max", 5))
    monkeypatch.setattr(findings, "repeated_finding_file",
                        lambda *_args, **_kwargs: repeated_file)
    monkeypatch.setattr(fix, "record_files", lambda *_args: None)
    monkeypatch.setattr(fix, "_lite_dirty_product_files", lambda *_args: [])
    monkeypatch.setattr(fix, "task_digest", lambda _contract: "digest")
    monkeypatch.setattr(fix, "launch_companion",
                        lambda *_args, **kwargs: launched.update(kwargs))
    monkeypatch.setattr("forge_cli.codex_runtime.coordinator_runtime", lambda: "codex")
    return launched


@pytest.fixture(autouse=True)
def _skip_schema_for_minimal_review_fixtures(monkeypatch):
    monkeypatch.setattr(findings, "validate_review_document", lambda *_args: None)


def test_consecutive_same_file_findings_require_a_choice(
        tmp_path: Path, monkeypatch, capsys):
    _review(tmp_path, "ENG-1", "T1", "run-1", "2026-01-01T00:00:00Z", "src/a.py")
    _review(tmp_path, "ENG-1", "T1", "run-2", "2026-01-02T00:00:00Z", "src/a.py")

    file_path = findings.repeated_finding_file(tmp_path, "ENG-1", "T1")
    assert file_path == "src/a.py"
    assert findings.choice_error(file_path, None) == (
        "src/a.py drew findings in two consecutive reviews. Ask the user: "
        "refactor it, or patch once more? Then re-run with --choice refactor|patch."
    )
    _prepare_fix(monkeypatch, tmp_path, file_path)
    with pytest.raises(SystemExit):
        fix.cmd_fix(SimpleNamespace(description="patch behavior", repo=str(tmp_path),
                                    choice=None))
    assert capsys.readouterr().out.strip() == f"ERROR: {findings.choice_error(file_path, None)}"


def test_patch_choice_allows_the_fix_round(tmp_path: Path, monkeypatch):
    launched = _prepare_fix(monkeypatch, tmp_path, "src/a.py")

    fix.cmd_fix(SimpleNamespace(description="patch the behavior", repo=str(tmp_path),
                                choice="patch"))

    assert launched["choice"] == "patch"
    assert findings.choice_error("src/a.py", launched["choice"]) == ""


def test_refactor_choice_adds_the_requested_brief_line():
    brief = fix._brief({"id": "lite-1"}, "fix it", "src/a.py")
    assert "Refactor src/a.py: replace the approach with one simpler rule." in brief


def test_different_files_do_not_trigger_the_rule(tmp_path: Path):
    _review(tmp_path, "ENG-1", "T1", "run-1", "2026-01-01T00:00:00Z", "src/a.py")
    _review(tmp_path, "ENG-1", "T1", "run-2", "2026-01-02T00:00:00Z", "src/b.py")

    assert findings.repeated_finding_file(tmp_path, "ENG-1", "T1") is None


def test_print_only_is_never_refused():
    assert findings.choice_error("src/a.py", None, preview=True) == ""


def test_lite_detector_compares_current_head_reviews_to_the_last_closed_window(
        tmp_path: Path, monkeypatch):
    aspects = ("quality", "performance", "security")
    current_window = {
        "id": "lite-current", "profile": "lite", "base_sha": "head-1",
        "started_at": "2026-01-03T00:00:00Z",
    }
    previous_reviews = {
        aspect: {
            "blocking_findings": ([{"category": "bug", "file_path": "src/a.py"}]
                                  if aspect == "security" else []),
            "non_blocking_findings": [], "commit": "head-1",
            "review_base_sha": "base-0", "branch_diff_digest": "old-delta",
        }
        for aspect in aspects
    }
    current_reviews = {
        aspect: {
            "generated_by": "autoreview", "score": 7,
            "summary": "reviewed", "recommendation": "request-changes",
            "blocking_findings": ([{"category": "bug", "file_path": "src/a.py"}]
                                  if aspect == "quality" else []),
            "non_blocking_findings": [], "commit": "head-2",
            "review_base_sha": "head-1", "branch_diff_digest": "new-delta",
        }
        for aspect in aspects
    }
    for aspect, artifact in current_reviews.items():
        (tmp_path / f"{aspect}.json").write_text(json.dumps(artifact), encoding="utf-8")

    monkeypatch.setattr(findings, "_active_story_key", lambda _base: "ENG-1")
    monkeypatch.setattr(findings, "_git_is_ancestor", lambda *_args: True)
    monkeypatch.setattr(findings, "head_sha", lambda _base: "head-2")
    monkeypatch.setattr(findings, "product_delta_digest", lambda *_args: "new-delta")
    monkeypatch.setattr(findings, "evidence_path",
                        lambda base, _key, name: base / name.rsplit("/", 1)[-1])
    monkeypatch.setattr(findings, "validate_payload", lambda *_args: None)
    monkeypatch.setattr(quickfix, "load_active", lambda _base: current_window)
    monkeypatch.setattr(quickfix, "closed_windows", lambda _base: [{
        "event": "done", "id": "lite-previous", "profile": "lite",
        "base_sha": "base-0", "completed_at": "2026-01-02T00:00:00Z",
        "reviews": previous_reviews,
    }])

    assert findings.repeated_finding_file(
        tmp_path, "", "lite-current", lite=True,
    ) == "src/a.py"
