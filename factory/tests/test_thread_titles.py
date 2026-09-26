from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HARNESS / "factory" / "scripts"))

from forge_cli import codex_runtime, delegate, grill, review, review_brief, stages  # noqa: E402
from factory_lib import review_identity_body  # noqa: E402


def _assert_title(brief: str | bytes, expected: str) -> None:
    if isinstance(brief, bytes):
        brief = brief.decode("utf-8")
    first_line = brief.splitlines()[0]
    assert first_line == expected
    assert len(first_line) < 60


@pytest.mark.parametrize(("write", "generation", "debug", "expected"), [
    (True, None, False, "Build · S-42/T1 · Add cache"),
    (True, {"generation_id": "review-1"}, False,
     "Fix · S-42/T1 · Add cache"),
    (False, None, False, "Explore · S-42/T1 · Add cache"),
    (False, None, True, "Debug · S-42/T1 · Add cache"),
])
def test_delegation_briefs_use_kind_first_title(
        tmp_path: Path, write, generation, debug, expected):
    task = {"id": "T1", "title": "Add cache"}
    brief = delegate._thread_titled_delegation(
        tmp_path, task, "S-42", "# Brief — T1: Add cache\n\nBody",
        write=write, generation=generation, debug=debug,
    )

    _assert_title(brief, expected)
    assert brief.splitlines()[1] == "# Brief — T1: Add cache"


def test_fix_delegation_uses_available_review_round(tmp_path: Path):
    generations = (tmp_path / ".factory/stories/S-42/tasks/T1/reviews"
                   / "generations")
    generations.mkdir(parents=True)
    for name in ("one.json", "two.json"):
        (generations / name).write_text("{}", encoding="utf-8")

    brief = delegate._thread_titled_delegation(
        tmp_path, {"id": "T1", "title": "Add cache"}, "S-42", "body",
        write=True, generation={"generation_id": "selected"},
    )

    _assert_title(brief, "Fix · S-42/T1 · review round 2")


def test_debug_delegation_requires_read_only(capsys):
    with pytest.raises(SystemExit):
        delegate.cmd_delegate(argparse.Namespace(debug=True, read_only=False))
    assert "--debug requires --read-only" in capsys.readouterr().out


def test_lite_fix_title_is_prepended_by_shared_launcher(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    factory = tmp_path / ".factory"
    (factory / "briefs").mkdir(parents=True)
    monkeypatch.setattr(codex_runtime, "coordinator_runtime", lambda: "codex")
    brief_path = factory / "briefs/Q-0244-9c2a.md"

    descriptor = delegate.launch_companion(
        tmp_path, task_id="Q-0244-9c2a",
        text="# Lite fix — Q-0244-9c2a\n\nFix: Tweak output. More detail.",
        path=brief_path, task_sha256_value="task", model="model",
        effort="max", write=True, mode="lite", print_only=True,
    )

    _assert_title(brief_path.read_bytes(),
                  "Lite · Q-0244-9c2a · Tweak output.")
    _assert_title(descriptor["message"],
                  "Lite · Q-0244-9c2a · Tweak output.")
    assert brief_path.read_text(encoding="utf-8").splitlines()[1] == (
        "# Lite fix — Q-0244-9c2a")


def test_native_descriptor_starts_with_the_brief_title(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / ".factory/briefs").mkdir(parents=True)
    monkeypatch.setattr(codex_runtime, "coordinator_runtime", lambda: "codex")
    title = "Build · S-42/T1 · Add cache"
    descriptor = delegate.launch_companion(
        tmp_path, task_id="T1", text=f"{title}\n# Brief — T1: Add cache\n",
        path=tmp_path / ".factory/briefs/T1.md",
        task_sha256_value="task", model="model", effort="max",
        write=False, print_only=True,
    )

    _assert_title(descriptor["message"], title)
    assert descriptor["message"].splitlines()[1].startswith("Read .factory/briefs/T1.md")


def test_grill_brief_uses_gate_subject_and_keeps_old_heading(tmp_path: Path):
    factory = tmp_path / ".factory"
    factory.mkdir()
    (factory / "run.json").write_text("{}", encoding="utf-8")
    brief = grill._compose_brief(
        tmp_path, "spec", "spec cache-layer.md", "spec text",
    )

    _assert_title(brief, "Grill · spec cache-layer · spec cache-layer.md")
    assert brief.splitlines()[1] == (
        "# Cold-read grill — gate: spec — spec cache-layer.md")


def test_review_prompt_uses_story_task_subject(tmp_path: Path):
    factory = tmp_path / ".factory"
    factory.mkdir()
    (factory / "run.json").write_text(
        json.dumps({"issue_key": "S-42"}), encoding="utf-8",
    )

    prompt = review._combined_prompt(
        {"id": "T1", "title": "Add cache", "plan_contracts": []},
        base=tmp_path,
    )

    _assert_title(prompt, "Review · S-42/T1 · Add cache")
    assert prompt.decode("utf-8").splitlines()[1] == (
        "# Review brief — T1 — combined review")


def test_lite_review_prompt_uses_window_subject():
    prompt = review._combined_prompt({
        "id": "Q-0244-9c2a", "title": "Lite review",
        "_thread_subject": "Q-0244-9c2a", "plan_contracts": [],
    })

    _assert_title(prompt, "Review · Q-0244-9c2a · Lite review")


def test_review_titles_do_not_change_hashed_input():
    task = {"id": "T1", "title": "Add cache", "plan_contracts": []}
    prompt = review._combined_prompt(task)
    renamed = b"Review \xc2\xb7 other subject \xc2\xb7 other title\n" + prompt.split(b"\n", 1)[1]
    assert review_identity_body(prompt) == review_identity_body(renamed)

    dataset = b"Review \xc2\xb7 S-42/T1 \xc2\xb7 Add cache\n# Reviewed contract\n"
    retitled = b"Review \xc2\xb7 S-42/T1 \xc2\xb7 New label\n# Reviewed contract\n"
    changed = b"Review \xc2\xb7 S-42/T1 \xc2\xb7 Add cache\n# Changed contract\n"
    assert stages._canonical_review_dataset(dataset) == stages._canonical_review_dataset(retitled)
    assert stages._canonical_review_dataset(dataset) != stages._canonical_review_dataset(changed)


def test_rendered_review_brief_uses_story_task_subject(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    factory = tmp_path / ".factory"
    factory.mkdir()
    (factory / "run.json").write_text(
        json.dumps({"issue_key": "S-42"}), encoding="utf-8",
    )
    monkeypatch.setattr(review_brief, "_decision_inputs_section", lambda *_: [])
    monkeypatch.setattr(review_brief, "_approved_task_inputs", lambda *_: {})
    monkeypatch.setattr(review_brief, "_settled_section", lambda *_: [])
    monkeypatch.setattr(review_brief, "_task_section", lambda *_args, **_kwargs: [])
    from forge_cli import stages
    monkeypatch.setattr(stages, "load_stages", lambda *_: {"stages": []})

    body, _inputs, _task = review_brief.render_review_brief(
        tmp_path, [{"id": "T1", "title": "Add cache"}],
        "# Plan-contract review brief — T1", all_tasks=False,
        reviewed_task="T1",
    )

    _assert_title(body, "Review · S-42/T1 · Add cache")


def test_long_title_is_truncated_without_changing_kind_or_subject():
    result = delegate.thread_title("Build", "S-42/T1", "cache " * 20)

    assert result.startswith("Build · S-42/T1 · ")
    assert result.endswith("…")
    assert len(result) < 60
