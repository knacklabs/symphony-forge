"""A default task review calls one helper and publishes one selected generation."""
from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

import pytest

from test_gates import (  # noqa: F401
    DECOMP, HARNESS, bind_task_proof_receipts, git, head, intake,
    load_factory_lib, record_skeleton_then_frontier, record_task_grill, repo,
    save_plan, sign_off, write_in_scope, write_stages,
)

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from forge_cli.review import _helper_identity, codex_runs_path, review_task  # noqa: E402
from forge_cli.stages import (  # noqa: E402
    load_stages, reviewed_meaning_identity, task_for,
)


FAKE_REVIEW = r'''
import json, os, pathlib, sys
args = sys.argv[1:]
out = pathlib.Path(args[args.index("--json-output") + 1])
prompt = pathlib.Path(args[args.index("--prompt-file") + 1])
dataset = pathlib.Path(args[args.index("--dataset") + 1])
assert "### Approved task inputs" in dataset.read_text(encoding="utf-8")
text = prompt.read_text(encoding="utf-8")
assert all(marker in text for marker in (
    "BEGIN FORGE ASSESSMENT quality", "BEGIN FORGE ASSESSMENT performance",
    "BEGIN FORGE ASSESSMENT security",
    "[quality] ", "[performance] ", "[security] ",
))
provider = {
    "findings": [],
    "overall_correctness": "patch is correct",
    "overall_explanation": (
        "BEGIN FORGE ASSESSMENT quality\n"
        "VERDICT C1: implemented — src/core.py:1\n"
        "END FORGE ASSESSMENT quality\n"
        "BEGIN FORGE ASSESSMENT performance\nNo repeated work.\n"
        "END FORGE ASSESSMENT performance\n"
        "BEGIN FORGE ASSESSMENT security\nNo unsafe boundary.\n"
        "END FORGE ASSESSMENT security"
    ),
    "overall_confidence": 0.9,
}
report = {**provider, "provider_report": provider, "review_status": "scoped-clean"}
out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
if os.environ.get("FAKE_MUTATE_HELPER"):
    pathlib.Path(__file__).write_text(pathlib.Path(__file__).read_text() + "\n# changed\n")
if os.environ.get("FAKE_MUTATE_PRODUCT"):
    (pathlib.Path(os.environ["FAKE_MUTATE_PRODUCT"]) / "src/core.py").write_text("changed\n")
sys.exit(0)
'''


def _fake_skill(tmp_path: Path) -> Path:
    path = tmp_path / "fake-autoreview.py"
    path.write_text(FAKE_REVIEW, encoding="utf-8")
    return path


def _built(repo: Path, tmp_path: Path) -> None:
    sign_off(repo)
    intake(repo)
    save_plan(repo, tmp_path)
    task = {
        **DECOMP["tasks"][0], "id": "T1", "write_scope": ["src/core.py"],
        "required_tests": [{
            "id": "test_board_review_rollup_is_incomplete_when_any_task_lacks_a_lens",
            "path": "factory/tests/test_gates.py",
            "command": "python3 -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}",
        }],
        "verify_commands": ["python3 -m compileall src"],
        "plan_contracts": [{"id": "C1",
                            "statement": DECOMP["tasks"][0]["acceptance_criteria"][0],
                            "source": "plan"}],
    }
    record_skeleton_then_frontier(repo, [task])
    write_stages(repo, {"issue": "ENG-1", "stages": [
        {"id": "T1", "title": task["title"], "status": "active", "base_sha": head(repo)},
    ]})
    code, output = record_task_grill(repo, task)
    assert code == 0, output
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "prepare review")
    write_stages(repo, {"issue": "ENG-1", "stages": [
        {"id": "T1", "title": task["title"], "status": "active", "base_sha": head(repo)},
    ]})
    write_in_scope(repo, "src/core.py")
    git(repo, "add", "src/core.py")
    git(repo, "commit", "-qm", "work")
    lib = load_factory_lib(repo)
    commit = head(repo)
    automated = {
        "generated_by": "implementer", "status": "passed",
        "summary": "combined review fixture passed", "blocking_findings": [],
        "commands_run": ["pytest test_review_lenses_in_parallel.py"],
        "reviewed_scope": ["src/core.py"], "remaining_gaps": [],
        "recorded_at": "2026-09-11T00:00:00+00:00", "commit": commit,
    }
    for name, body in (
        ("verify.json", {"ok": True, "commit": commit}),
        ("tests.json", {"automated": automated, "commit": commit}),
    ):
        path = lib.proof_path(repo, "ENG-1", name, task_id="T1", for_write=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        lib.dump_json(path, body)
    bind_task_proof_receipts(repo, "T1")


def _selection(repo: Path) -> tuple[Path, dict, dict]:
    path = repo / ".factory/stories/ENG-1/tasks/T1/reviews/selected.json"
    pointer = json.loads(path.read_text())
    generation_path = path.parent / "generations" / f"{pointer['generation_id']}.json"
    return path, pointer, json.loads(generation_path.read_text())


def test_default_review_uses_one_helper_and_publishes_one_generation(repo, tmp_path):
    _built(repo, tmp_path)
    outcome = review_task(repo, "T1", skill=str(_fake_skill(tmp_path)), engine="claude")

    assert outcome["blocking"] == 0 and outcome["stamped"] is True
    selection_path, pointer, generation = _selection(repo)
    assert selection_path.is_file()
    assert generation["origin"] == "combined"
    assert set(generation["lenses"]) == {"quality", "performance", "security"}
    raw = base64.b64decode(generation["raw_result"]["data"], validate=True)
    assert json.loads(raw)["overall_correctness"] == "patch is correct"
    rows = [json.loads(line) for line in codex_runs_path(repo).read_text().splitlines()]
    assert [row["status"] for row in rows if row.get("kind") == "review"].count(
        "starting") == 1
    stage = next(item for item in load_stages(repo)["stages"] if item["id"] == "T1")
    assert stage["local_review_stamp"]["delta_id"] == pointer["delta_id"]
    meaning = reviewed_meaning_identity(
        repo, stage, task_for(repo, "T1"), generation["helper"],
    )
    assert generation["input"] in meaning["accepted_inputs"]
    prompt = (repo / ".factory/review-briefs/T1.combined.md").read_bytes()
    assert generation["input"] == {
        "sha256": hashlib.sha256(prompt).hexdigest(), "bytes": len(prompt),
    }


def test_review_helper_identity_mismatch_refuses_publication(repo, tmp_path, monkeypatch):
    _built(repo, tmp_path)
    helper = _fake_skill(tmp_path)
    review_task(repo, "T1", skill=str(helper), engine="claude")
    selection_path, _pointer, _generation = _selection(repo)
    before = selection_path.read_bytes()

    monkeypatch.setenv("FAKE_MUTATE_HELPER", "1")
    bind_task_proof_receipts(repo, "T1")
    with pytest.raises(SystemExit):
        review_task(repo, "T1", skill=str(helper), engine="claude")
    assert selection_path.read_bytes() == before


def test_review_helper_identity_records_installed_version(tmp_path):
    helper = tmp_path / "plugin" / "autoreview" / "SKILL.md"
    helper.parent.mkdir(parents=True)
    helper.write_text("helper\n", encoding="utf-8")
    (helper.parent.parent / ".upstream-sha").write_text("a" * 40, encoding="utf-8")
    assert _helper_identity(helper)[0]["version"] == "a" * 40


def test_review_product_change_during_helper_refuses_publication(
        repo, tmp_path, monkeypatch, capsys):
    _built(repo, tmp_path)
    helper = _fake_skill(tmp_path)
    review_task(repo, "T1", skill=str(helper), engine="claude")
    selection_path, _pointer, _generation = _selection(repo)
    before = selection_path.read_bytes()

    monkeypatch.setenv("FAKE_MUTATE_PRODUCT", str(repo))
    bind_task_proof_receipts(repo, "T1")
    with pytest.raises(SystemExit):
        review_task(repo, "T1", skill=str(helper), engine="claude")
    assert "product changed during the review" in capsys.readouterr().out
    assert selection_path.read_bytes() == before


def test_helper_result_cannot_stamp_evidence_changed_during_review(
        repo, tmp_path, monkeypatch, capsys):
    from forge_cli import review
    from factory_lib import proof_path
    _built(repo, tmp_path)
    original = review._run_skill

    def run_then_change_evidence(*args, **kwargs):
        result = original(*args, **kwargs)
        path = proof_path(repo, "ENG-1", "tests.json", task_id="T1")
        data = json.loads(path.read_text())
        data["automated"]["commands_run"].append("pytest changed-after-helper")
        path.write_text(json.dumps(data))
        return result

    monkeypatch.setattr(review, "_run_skill", run_then_change_evidence)
    with pytest.raises(SystemExit):
        review_task(repo, "T1", skill=str(_fake_skill(tmp_path)), engine="claude")
    assert "current reviewed meaning" in capsys.readouterr().out
    assert not proof_path(repo, "ENG-1", "reviews/selected.json", task_id="T1").exists()


def test_dataset_rendering_refuses_evidence_drift_before_helper(
        repo, tmp_path, monkeypatch, capsys):
    from forge_cli import review
    from factory_lib import proof_path
    _built(repo, tmp_path)
    original = review.cmd_review_brief
    called = []

    def render_then_change_evidence(args):
        original(args)
        path = proof_path(repo, "ENG-1", "tests.json", task_id="T1")
        data = json.loads(path.read_text())
        data["automated"]["commands_run"].append("pytest changed-during-render")
        path.write_text(json.dumps(data))

    def helper_must_not_run(*args, **kwargs):
        called.append(True)

    monkeypatch.setattr(review, "cmd_review_brief", render_then_change_evidence)
    monkeypatch.setattr(review, "_run_skill", helper_must_not_run)
    with pytest.raises(SystemExit):
        review_task(repo, "T1", skill=str(_fake_skill(tmp_path)), engine="claude")
    assert "changed while rendering" in capsys.readouterr().out
    assert not called
    assert not proof_path(repo, "ENG-1", "reviews/selected.json", task_id="T1").exists()
