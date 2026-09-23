"""The board reads a task's own proof.

Proof became task-owned (tasks/<id>/verify.json, tests.json) and the review
became one selected generation (0069); the board kept reading story-level
fixed files and showed every task-level story's five gate rows as "not
recorded" (WF-1A, 2026-09-15). The story rows now roll up from the tasks and
the drawer lists each task's own record.
"""
from __future__ import annotations

import sys

from test_gates import HARNESS, repo  # noqa: F401
from test_review_lenses_in_parallel import _built, _fake_skill

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
import factory_lib  # noqa: E402
from forge_cli import board  # noqa: E402
from forge_cli.board import rolled_up_evidence, story_detail, task_proof_records  # noqa: E402
from forge_cli.review import review_task  # noqa: E402
from forge_cli.stages import write_stages  # noqa: E402


def test_the_board_reads_task_level_proof_and_the_selected_generation(repo, tmp_path):
    _built(repo, tmp_path)
    review_task(repo, "T1", skill=str(_fake_skill(tmp_path)), engine="claude")

    proof = task_proof_records(repo, "ENG-1", "T1")
    assert proof["verify"]["ok"] is True
    assert proof["tests"]["automated"]["status"] == "passed"
    assert {aspect: record["score"] for aspect, record in proof["reviews"].items()} == {
        "quality": 10, "performance": 10, "security": 10}
    assert "contract_verdicts" in proof["reviews"]["quality"]

    detail = story_detail(repo, "ENG-1")
    assert detail is not None
    evidence = detail["evidence"]
    # No story-level files exist for a task-level run; the rows come from T1.
    assert list(evidence["task_proof"]) == ["T1"]
    assert evidence["verify"] == {"ok": True, "tasks": {"T1": True}}
    assert evidence["tests"]["automated"]["status"] == "passed"
    assert evidence["reviews"]["quality"]["score"] == 10
    assert evidence["reviews"]["quality"]["summary"].startswith("T1: ")
    task = next(item for item in detail["tasks"] if item["id"] == "T1")
    assert task["proof"]["verify_ok"] is True


def test_a_story_row_passes_only_when_every_task_recorded_and_passed():
    clean = {"score": 10, "blocking_findings": [], "non_blocking_findings": [], "summary": "fine"}
    decomposition = {"tasks": [{"id": "T1"}, {"id": "T2"}]}
    one_of_two = {"T1": {"verify": {"ok": True}, "tests": {"automated": {"status": "passed"}},
                         "reviews": {"quality": clean, "performance": clean, "security": clean}}}
    rolled = rolled_up_evidence(one_of_two, decomposition)
    assert rolled["verify"]["ok"] is False and rolled["verify"]["tasks"] == {"T1": True}
    assert rolled["tests"]["automated"]["status"] == "incomplete"
    assert rolled["reviews"]["quality"]["score"] == 7  # below the seal floor until T2 records

    both = dict(one_of_two, T2={"verify": {"ok": True}, "tests": {"automated": {"status": "passed"}},
                                "reviews": {"quality": {**clean, "score": 9}, "performance": clean,
                                            "security": clean}})
    rolled = rolled_up_evidence(both, decomposition)
    assert rolled["verify"]["ok"] is True
    assert rolled["tests"]["automated"]["status"] == "passed"
    assert rolled["reviews"]["quality"]["score"] == 9  # the lowest task's record is shown
    assert rolled["reviews"]["quality"]["summary"] == "T1: fine; T2: fine"


def test_active_task_uses_current_generation_while_done_task_uses_sealed_marker(
        repo, tmp_path, monkeypatch):
    _built(repo, tmp_path)
    task_root = repo / ".factory" / "stories" / "ENG-1" / "tasks" / "T1"
    (task_root / "reviews").mkdir(parents=True, exist_ok=True)
    (task_root / "reviews" / "selected.json").write_text("{}\n", encoding="utf-8")
    # This is the retained marker from the prior seal. Its presence must not
    # make a reopened/active task read the old selected generation.
    (task_root / "pr-ready.json").write_text("{\"commit\": \"A\"}\n", encoding="utf-8")

    sealed = {
        "lenses": {
            "quality": {"summary": "sealed A"},
            "performance": {"summary": "sealed A"},
            "security": {"summary": "sealed A"},
        },
    }
    current = {
        "lenses": {
            "quality": {"summary": "current B"},
            "performance": {"summary": "current B"},
            "security": {"summary": "current B"},
        },
    }
    selected_commits = []

    def read_selected(_base, _key, _task_id, *, sealed_commit="", **_kwargs):
        selected_commits.append(sealed_commit)
        return (sealed if sealed_commit == "marker-A" else current, {}, [])

    monkeypatch.setattr(board, "read_selected_review_generation", read_selected)
    monkeypatch.setattr(
        board, "validated_task_marker_commit", lambda *_args: "marker-A",
    )

    # `task_rows` derives await-merge from a durable done stage whose marker is
    # not on the trunk. Proof selection must still use that durable status.
    write_stages(repo, {"issue": "ENG-1", "stages": [
        {"id": "T1", "title": "core slice", "status": "done"},
    ]})
    monkeypatch.setattr(factory_lib, "_has_origin", lambda _root: True)
    monkeypatch.setattr(factory_lib, "fetch_trunk", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        factory_lib, "task_marker_on_main", lambda *_args, **_kwargs: False,
    )
    rows = factory_lib.task_rows(repo)
    assert rows[0]["state"] == "await-merge"
    stages = board._stages_for(repo, "ENG-1")["stages"]
    merged = board.merge_task_detail(
        {"tasks": [{"id": "T1"}]}, stages, rows,
    )
    assert merged[0]["status"] == "done"
    assert merged[0]["state"] == "await-merge"
    await_merge_statuses = board._task_proof_statuses(stages, merged)
    assert await_merge_statuses == {"T1": "done"}

    active = board.task_proof_records(repo, "ENG-1", "T1", task_status="active")
    done = board.task_proof_records(repo, "ENG-1", "T1", task_status="done")

    assert active["reviews"]["quality"]["summary"] == "current B"
    assert done["reviews"]["quality"]["summary"] == "sealed A"
    assert selected_commits == ["", "marker-A"]

    proof_calls = []

    def proof_problems(_base, _key, _task, *, preseal=False, **_kwargs):
        proof_calls.append(preseal)
        return []

    monkeypatch.setattr(factory_lib, "task_proof_problems", proof_problems)
    decomposition = {"tasks": [{"id": "T1"}]}
    active_proof = board.story_task_proof(
        repo, "ENG-1", decomposition, task_statuses={"T1": "active"},
    )
    done_proof = board.story_task_proof(
        repo, "ENG-1", decomposition, task_statuses={"T1": "done"},
    )
    await_merge = board.story_task_proof(
        repo, "ENG-1", decomposition, task_statuses=await_merge_statuses,
    )

    assert active_proof["T1"]["current"] is True
    assert done_proof["T1"]["current"] is True
    assert await_merge["T1"]["reviews"]["quality"]["summary"] == "sealed A"
    assert await_merge["T1"]["current"] is True
    assert selected_commits == ["", "marker-A", "", "marker-A", "marker-A"]
    assert proof_calls == [True, False, False]


def test_shipped_story_skips_task_proof_revalidation_on_board_poll(
        repo, tmp_path, monkeypatch):
    _built(repo, tmp_path)

    def unexpected(*_args, **_kwargs):
        raise AssertionError("shipped task proof was revalidated")

    monkeypatch.setattr(factory_lib, "task_proof_problems", unexpected)
    _progress, _evidence, tasks = board._plan_evidence(
        repo, "ENG-1", None, shipped=True,
    )

    assert tasks


def test_board_marks_an_exactly_approved_plan_grill_as_passed(repo):
    path = repo / "plans/active/ENG-1-plan.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\nstatus: approved\nstory: ENG-1\n---\n\n# Plan\n",
        encoding="utf-8",
    )
    detail = {
        "plan": {
            "status": "approved",
            "path": path.relative_to(repo).as_posix(),
            "decisions_reviewed": [row["id"] for row in board.active_decisions(repo)],
        },
        "plan_body": "## Surface Impact\n\nCLI and tests.\n",
        "evidence": {
            "grills": {},
            "plan_approval": {
                "approved_plan_sha256": factory_lib.plan_digest_without_assumptions(path),
            },
        },
    }

    readiness = board.approval_readiness(repo, detail)

    assert readiness[1]["label"] == "plan grill passed"
    assert readiness[1]["ok"] is True


def test_board_accepts_approved_plan_grill_for_shipped_story_only(repo):
    detail = {
        "story": {"status": "done"},
        "plan": {"status": "approved"},
        "evidence": {"grills": {}, "plan_approval": None},
    }

    readiness = board.approval_readiness(repo, detail)
    assert readiness[1]["ok"] is True

    detail["story"]["status"] = "in-progress"
    readiness = board.approval_readiness(repo, detail)
    assert readiness[1]["ok"] is False
