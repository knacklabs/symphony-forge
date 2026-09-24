"""Repeated review findings ask for the next fix approach."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import factory_lib  # noqa: E402
from factory_lib import review_generation_bytes, review_generation_id  # noqa: E402
from forge_cli import delegate, findings, fix, quickfix  # noqa: E402


def _review(base: Path, story: str, task: str, run: str, recorded_at: str,
            file_path: str | tuple[str, ...], *, category: str = "bug",
            source_generation_id: str = "") -> dict:
    file_paths = (file_path,) if isinstance(file_path, str) else file_path
    lenses = {
        aspect: {
            "blocking_findings": ([{"category": category, "file_path": path}
                                   for path in file_paths]
                                  if aspect == "quality" else []),
            "non_blocking_findings": [],
        }
        for aspect in ("quality", "performance", "security")
    }
    generation = {
        "format": "forge-review-generation/v1",
        "origin": "rejection" if source_generation_id else "combined",
        "story": story, "task_id": task, "delta_id": "d" * 64,
        "review_run_id": run, "recorded_at": recorded_at, "lenses": lenses,
    }
    if source_generation_id:
        lesson_path = (f".factory/stories/{story}/tasks/{task}/reviews/lessons/{run}.json")
        lesson = base / lesson_path
        lesson.parent.mkdir(parents=True, exist_ok=True)
        lesson.write_text("lesson\n", encoding="utf-8")
        generation["rejection"] = {
            "source_generation_id": source_generation_id,
            "history": [{
                "lesson_path": lesson_path,
                "lesson_sha256": hashlib.sha256(lesson.read_bytes()).hexdigest(),
            }],
        }
    generation["generation_id"] = review_generation_id(generation)
    path = (base / ".factory" / "stories" / story / "tasks" / task
            / "reviews" / "generations" / f"{generation['generation_id']}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(review_generation_bytes(generation))
    return generation


def _select(base: Path, generation: dict) -> None:
    path = (base / ".factory" / "stories" / generation["story"] / "tasks"
            / generation["task_id"] / "reviews" / "selected.json")
    document = {
        "format": "forge-review-selection/v1",
        "story": generation["story"], "task_id": generation["task_id"],
        "generation_id": generation["generation_id"],
        "generation_sha256": hashlib.sha256(
            review_generation_bytes(generation)
        ).hexdigest(),
        "delta_id": generation["delta_id"], "selected_at": "2026-01-03T00:00:00Z",
    }
    path.write_bytes(review_generation_bytes(document))


def _prepare_fix(monkeypatch, base: Path, repeated_files: list[str]):
    launched = {}
    monkeypatch.setattr(fix, "load_active", lambda _base: {
        "id": "lite-1", "profile": "lite", "max_files": 5,
    })
    monkeypatch.setattr(fix, "mode_run_config", lambda *_args: ("model", "max", 5))
    monkeypatch.setattr(findings, "repeated_finding_files",
                        lambda *_args, **_kwargs: repeated_files)
    monkeypatch.setattr(fix, "record_files", lambda *_args: None)
    monkeypatch.setattr(fix, "_lite_dirty_product_files", lambda *_args: [])
    monkeypatch.setattr(fix, "task_digest", lambda _contract: "digest")
    monkeypatch.setattr(fix, "launch_companion",
                        lambda *_args, **kwargs: launched.update(kwargs))
    monkeypatch.setattr("forge_cli.codex_runtime.coordinator_runtime", lambda: "codex")
    return launched


def _prepare_delegate(monkeypatch, base: Path, repeated_files: list[str]) -> None:
    from forge_cli import review, stages

    task = {
        "id": "T1", "title": "bounded task", "objective": "change one file",
        "write_scope": ["src/"], "required_tests": [],
        "review_budget": {"max_changed_files": 1, "max_changed_lines": 10,
                          "reason": "bounded fixture"},
    }
    decomposition = base / "decomposition.json"
    run_state = base / "run.json"
    monkeypatch.setattr(delegate, "protected_decomposition_state_path",
                        lambda _base: decomposition)
    monkeypatch.setattr(delegate, "run_state_path", lambda _base: run_state)
    monkeypatch.setattr(
        delegate, "load_json",
        lambda path, default=None: ({"tasks": [task]} if path == decomposition
                                    else {"story": "ENG-1"}),
    )
    monkeypatch.setattr(delegate, "load_stages", lambda _base: {
        "stages": [{"id": "T1", "status": "active", "started_at": "stage-1"}],
    })
    monkeypatch.setattr(delegate, "require_task_worktree", lambda _base: None)
    monkeypatch.setattr(delegate, "require_ready_task", lambda *_args: task)
    monkeypatch.setattr(stages, "effective_scope", lambda *_args: task["write_scope"])
    monkeypatch.setattr(delegate, "task_digest", lambda _task: "digest")
    monkeypatch.setattr(delegate, "pinned_run_config", lambda _base: ("model", "medium"))
    monkeypatch.setattr(
        delegate, "compose_brief",
        lambda _base, _task, *, write, **_kwargs:
        f"write access: {'YES' if write else 'NO — read only'}\n",
    )
    monkeypatch.setattr(findings, "repeated_finding_files",
                        lambda *_args, **_kwargs: repeated_files)
    monkeypatch.setattr(review, "selected_generation", lambda *_args: None)
    monkeypatch.setattr(review, "untriaged_actionable_blocking",
                        lambda *_args, **_kwargs: (0, 0))
    monkeypatch.setattr("forge_cli.codex_runtime.coordinator_runtime", lambda: "codex")


@pytest.fixture(autouse=True)
def _skip_schema_for_minimal_review_fixtures(monkeypatch):
    monkeypatch.setattr(findings, "validate_review_document", lambda *_args: None)
    monkeypatch.setattr(factory_lib, "validate_review_document", lambda *_args: None)
    monkeypatch.setattr(factory_lib, "_rejection_successor_problems",
                        lambda *_args: [])


def test_consecutive_same_file_findings_require_a_choice(
        tmp_path: Path, monkeypatch, capsys):
    previous = _review(
        tmp_path, "ENG-1", "T1", "run-1", "2026-01-01T00:00:00Z", "src/a.py",
    )
    selected = _review(
        tmp_path, "ENG-1", "T1", "run-2", "2026-01-02T00:00:00Z", "src/a.py",
        source_generation_id=previous["generation_id"],
    )
    _select(tmp_path, selected)

    file_paths = findings.repeated_finding_files(tmp_path, "ENG-1", "T1")
    assert file_paths == ["src/a.py"]
    assert findings.choice_error(file_paths, None) == (
        "src/a.py drew findings in two consecutive reviews. Ask the user: "
        "refactor it, or patch once more? Then re-run with --choice refactor|patch."
    )
    _prepare_fix(monkeypatch, tmp_path, file_paths)
    with pytest.raises(SystemExit):
        fix.cmd_fix(SimpleNamespace(description="patch behavior", repo=str(tmp_path),
                                    choice=None))
    assert capsys.readouterr().out.strip() == f"ERROR: {findings.choice_error(file_paths, None)}"


def test_patch_choice_allows_the_fix_round(tmp_path: Path, monkeypatch):
    launched = _prepare_fix(monkeypatch, tmp_path, ["src/a.py"])

    fix.cmd_fix(SimpleNamespace(description="patch the behavior", repo=str(tmp_path),
                                choice="patch"))

    assert launched["choice"] == "patch"
    assert findings.choice_error(["src/a.py"], launched["choice"]) == ""


def test_two_repeated_files_are_named_and_get_refactor_lines(
        tmp_path: Path, monkeypatch, capsys):
    paths = ("src/a.py", "src/b.py")
    previous = _review(
        tmp_path, "ENG-1", "T1", "run-1", "2026-01-01T00:00:00Z", paths,
    )
    selected = _review(
        tmp_path, "ENG-1", "T1", "run-2", "2026-01-02T00:00:00Z", paths,
        source_generation_id=previous["generation_id"],
    )
    _select(tmp_path, selected)
    repeated_files = findings.repeated_finding_files(tmp_path, "ENG-1", "T1")
    assert repeated_files == ["src/a.py", "src/b.py"]
    assert findings.choice_error(repeated_files, None) == (
        "src/a.py, src/b.py drew findings in two consecutive reviews. Ask the user: "
        "refactor it, or patch once more? Then re-run with --choice refactor|patch."
    )

    launched = _prepare_fix(monkeypatch, tmp_path, repeated_files)
    fix.cmd_fix(SimpleNamespace(description="fix it", repo=str(tmp_path),
                                choice="refactor"))
    for file in repeated_files:
        line = f"Refactor {file}: replace the approach with one simpler rule."
        assert line in launched["text"]

    _prepare_delegate(monkeypatch, tmp_path, repeated_files)
    delegate.cmd_delegate(SimpleNamespace(
        repo=str(tmp_path), id="T1", read_only=False, scope=[], background=False,
        context_file=None, print_only=True, choice="refactor",
    ))
    output = capsys.readouterr().out
    descriptor = json.loads(output.splitlines()[-1])
    brief = (tmp_path / descriptor["brief_path"]).read_text(encoding="utf-8")
    for file in repeated_files:
        line = f"Refactor {file}: replace the approach with one simpler rule."
        assert line in brief


def test_different_files_do_not_trigger_the_rule(tmp_path: Path):
    previous = _review(
        tmp_path, "ENG-1", "T1", "run-1", "2026-01-01T00:00:00Z", "src/a.py",
    )
    selected = _review(
        tmp_path, "ENG-1", "T1", "run-2", "2026-01-02T00:00:00Z", "src/b.py",
        source_generation_id=previous["generation_id"],
    )
    _select(tmp_path, selected)

    assert findings.repeated_finding_files(tmp_path, "ENG-1", "T1") == []


def test_normal_selected_review_compares_with_an_earlier_generation(
        tmp_path: Path):
    _review(tmp_path, "ENG-1", "T1", "run-1", "2026-01-01T00:00:00Z", "src/a.py")
    selected = _review(
        tmp_path, "ENG-1", "T1", "run-2", "2026-01-02T00:00:00Z", "src/a.py",
    )
    _select(tmp_path, selected)

    assert findings.repeated_finding_files(tmp_path, "ENG-1", "T1") == ["src/a.py"]


def test_later_orphan_generation_is_ignored_after_selected_review(tmp_path: Path):
    _review(
        tmp_path, "ENG-1", "T1", "run-1", "2026-01-01T00:00:00Z", "src/a.py",
    )
    selected = _review(
        tmp_path, "ENG-1", "T1", "run-2", "2026-01-02T00:00:00Z", "src/a.py",
    )
    _review(tmp_path, "ENG-1", "T1", "orphan", "2026-01-04T00:00:00Z", "src/b.py")
    _select(tmp_path, selected)

    assert findings.repeated_finding_files(tmp_path, "ENG-1", "T1") == ["src/a.py"]


def test_single_selected_review_has_no_predecessor(tmp_path: Path):
    selected = _review(
        tmp_path, "ENG-1", "T1", "run-1", "2026-01-01T00:00:00Z", "src/a.py",
    )
    _select(tmp_path, selected)

    assert findings.repeated_finding_files(tmp_path, "ENG-1", "T1") == []


def test_print_only_without_choice_warns_and_emits_read_only_descriptor(
        tmp_path: Path, monkeypatch, capsys):
    repeated_files = ["src/a.py", "src/b.py"]
    _prepare_delegate(monkeypatch, tmp_path, repeated_files)

    delegate.cmd_delegate(SimpleNamespace(
        repo=str(tmp_path), id="T1", read_only=False, scope=[], background=False,
        context_file=None, print_only=True, choice=None,
    ))

    output = capsys.readouterr().out
    assert ("WARNING: src/a.py, src/b.py drew findings in two consecutive reviews "
            "-- this preview carries no write authority until the user chooses "
            "--choice refactor|patch.") in output
    descriptor = json.loads(output.splitlines()[-1])
    assert descriptor["write"] is False
    assert "write access: NO — read only" in (
        tmp_path / descriptor["brief_path"]
    ).read_text(encoding="utf-8")


def test_real_delegate_without_choice_is_refused(tmp_path: Path, monkeypatch, capsys):
    _prepare_delegate(monkeypatch, tmp_path, ["src/a.py", "src/b.py"])
    monkeypatch.setattr(
        delegate, "launch_companion",
        lambda *_args, **_kwargs: pytest.fail("refused launch must not be prepared"),
    )

    with pytest.raises(SystemExit):
        delegate.cmd_delegate(SimpleNamespace(
            repo=str(tmp_path), id="T1", read_only=False, scope=[], background=False,
            context_file=None, print_only=False, choice=None,
        ))
    assert "src/a.py, src/b.py drew findings in two consecutive reviews" in (
        capsys.readouterr().out
    )


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

    assert findings.repeated_finding_files(
        tmp_path, "", "lite-current", lite=True,
    ) == ["src/a.py"]
