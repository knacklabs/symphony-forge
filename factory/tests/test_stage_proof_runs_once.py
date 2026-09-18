"""A task's proof runs once per tree and is recorded where the gates read it
(decision 0079).

Before this, the suite ran in the worker, again in verify.py so the review had
a verify.json, again by hand before every close, and again inside close --
four to five full runs per fix cycle on WF-BIO-1 T4. The close now records
what it ran, bound to the product tree and the contract, and a later close
over the same tree and contract runs nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

from test_gates import (  # noqa: F401
    HARNESS, STAGE_TASK, git, head, repo, stamp_and_commit, start_stage,
    write_in_scope,
)

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from factory_lib import load_json, task_evidence_path  # noqa: E402
from forge_cli.stages import run_stage_proof, task_for  # noqa: E402


def _counting_task(tmp_path: Path, **over) -> tuple[dict, Path]:
    counter = tmp_path / "proof-runs.txt"
    counter.write_text("0")
    command = (
        "python3 -c \"import pathlib; p = pathlib.Path(r'" + str(counter) + "'); "
        "p.write_text(str(int(p.read_text()) + 1))\""
    )
    return {**STAGE_TASK, "verify_commands": [command], **over}, counter


def _evidence(repo: Path, name: str) -> dict:
    return load_json(task_evidence_path(repo, "ENG-1", "T1", name), default={})


def _built(repo: Path, tmp_path: Path, task: dict) -> dict:
    start_stage(repo, tmp_path, task)
    write_in_scope(repo, "src/core.py")
    stamp_and_commit(repo)  # commits the product; seeds a verify.py-shaped verify.json
    return task_for(repo, "T1")


def test_the_proof_is_recorded_and_reused_for_an_unchanged_tree(repo, tmp_path):
    task, counter = _counting_task(tmp_path)
    recorded = _built(repo, tmp_path, task)
    tests_path = task_evidence_path(repo, "ENG-1", "T1", "tests.json")
    worker_record = tests_path.read_bytes()

    run_stage_proof(repo, "T1", recorded)
    assert counter.read_text() == "1"
    verify = _evidence(repo, "verify.json")
    assert verify["recorded_by"] == "stage-proof" and verify["ok"] is True
    assert verify["commit"] == head(repo) and verify["tree_digest"] and verify["proof_key"]
    assert [entry["status"] for entry in verify["required_tests"]] == ["passed"]
    assert verify["results"][0]["exit_code"] == 0
    # The worker's report is untouched: the review brief renders it verbatim.
    assert tests_path.read_bytes() == worker_record

    run_stage_proof(repo, "T1", recorded)
    assert counter.read_text() == "1", "same tree, same contract: nothing ran"


def test_a_changed_tree_or_contract_runs_the_proof_again(repo, tmp_path):
    task, counter = _counting_task(tmp_path)
    recorded = _built(repo, tmp_path, task)
    run_stage_proof(repo, "T1", recorded)
    assert counter.read_text() == "1"

    write_in_scope(repo, "src/core.py", "version = 2\n")
    git(repo, "add", "src/core.py")
    git(repo, "commit", "-qm", "product moved")
    run_stage_proof(repo, "T1", recorded)
    assert counter.read_text() == "2"

    run_stage_proof(repo, "T1", {**recorded, "required_tests": []})
    assert counter.read_text() == "3", "a different contract is a different proof"


def test_an_uncommitted_tree_runs_but_is_not_recorded(repo, tmp_path):
    task, counter = _counting_task(tmp_path)
    recorded = _built(repo, tmp_path, task)
    run_stage_proof(repo, "T1", recorded)
    before = _evidence(repo, "verify.json")

    write_in_scope(repo, "src/core.py", "version = 3\n")
    run_stage_proof(repo, "T1", recorded)
    assert counter.read_text() == "2"
    assert _evidence(repo, "verify.json") == before


def test_a_stale_worker_record_is_rebound_when_no_review_covers_the_tree(repo, tmp_path):
    """After a fix commit the worker's record names the old commit and the
    review brief refuses it; the coordinator used to re-record the same
    report by hand. The proof re-binds it, narrative untouched."""
    task, counter = _counting_task(tmp_path)
    recorded = _built(repo, tmp_path, task)  # record and review at the first tree
    first = head(repo)
    write_in_scope(repo, "src/core.py", "version = 2\n")
    git(repo, "add", "src/core.py")
    git(repo, "commit", "-qm", "fix commit")
    run_stage_proof(repo, "T1", recorded)
    tests = _evidence(repo, "tests.json")
    automated = tests["automated"]
    assert automated["commit"] == head(repo) == tests["commit"]
    assert automated["worker_commit"] == first
    assert automated["bound_by"] == "stage-proof"
    assert automated["generated_by"] == "implementer"
    assert automated["summary"] == "focused task proof passed"


def test_a_task_without_a_worker_record_gets_the_harness_record(repo, tmp_path):
    task, counter = _counting_task(tmp_path)
    recorded = _built(repo, tmp_path, task)
    task_evidence_path(repo, "ENG-1", "T1", "tests.json").unlink()
    run_stage_proof(repo, "T1", recorded)
    automated = _evidence(repo, "tests.json")["automated"]
    assert automated["generated_by"] == "stage-proof" and automated["status"] == "passed"
    assert automated["commands_run"][0] == task["verify_commands"][0]
    assert automated["reviewed_scope"] == task["write_scope"]
    assert automated["commit"] == head(repo)
    assert _evidence(repo, "verify.json")["required_tests"][0]["status"] == "passed"


def test_a_user_facing_task_still_owes_its_own_record(repo, tmp_path):
    task, counter = _counting_task(tmp_path, user_facing=True)
    recorded = _built(repo, tmp_path, task)
    path = task_evidence_path(repo, "ENG-1", "T1", "tests.json")
    path.unlink()
    run_stage_proof(repo, "T1", recorded)
    assert counter.read_text() == "1"
    assert not path.exists(), "the design-skill attestation is the coordinator's"
    assert _evidence(repo, "verify.json")["recorded_by"] == "stage-proof"
