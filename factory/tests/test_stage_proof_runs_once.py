"""A task's proof runs once per tree and is recorded where the gates read it
(decision 0079).

Before this, the suite ran in the worker, again in verify.py so the review had
a verify.json, again by hand before every close, and again inside close --
four to five full runs per fix cycle on WF-BIO-1 T4. The close now records
what it ran, bound to the product tree and the contract, and a later close
over the same tree and contract runs nothing.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

from test_gates import (  # noqa: F401
    HARNESS, STAGE_TASK, git, head, repo, run, stamp_and_commit, start_stage,
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


# ------------------------------------------- flakes, headroom, elapsed (0080)


def test_a_command_that_fails_once_and_passes_on_re_run_is_a_recorded_flake(
        repo, tmp_path, capsys):
    """T4 hit one 2-second cleanup grace four times in four spec files and
    re-ran blindly each time, with no record. A first failure that passes on
    re-run is now a recorded flake with its output in the journal; the proof
    passes on the second run and nothing waits on a human."""
    from factory_lib import task_proof_problems
    from forge_cli import journal
    marker = tmp_path / "flaked-once"
    command = (
        "python3 -c \"import pathlib, sys; p = pathlib.Path(r'" + str(marker) + "'); "
        "sys.exit(0) if p.exists() else (p.write_text('1'), sys.exit(1))\""
    )
    task = {**STAGE_TASK, "verify_commands": [command]}
    recorded = _built(repo, tmp_path, task)
    run_stage_proof(repo, "T1", recorded)
    printed = capsys.readouterr().out
    assert "running it once more to tell a flake from a defect" in printed
    assert "a FLAKE, recorded as J-" in printed
    assert "proof: " in printed and "passed on re-run" in printed
    verify = _evidence(repo, "verify.json")
    assert verify["ok"] is True and verify["flakes"][0]["command"] == command
    entries = journal.entries(repo, "ENG-1", "T1")
    flake = next(e for e in entries if e["kind"] == "flake")
    assert flake["command"] == command and verify["flakes"][0]["journal"] == flake["id"]
    proofs = [e for e in entries if e["kind"] == "proof" and e["command"].startswith(command)]
    assert [e["exit_code"] for e in proofs] == [1, 0], proofs
    # Recorded, never a refusal: the seal rests on the second run.
    problems = task_proof_problems(repo, "ENG-1", recorded, preseal=True)
    assert not any("flake" in p.lower() for p in problems), problems


def test_the_proof_refuses_to_start_without_memory_headroom(
        repo, tmp_path, monkeypatch, capsys):
    from forge_cli import stages
    task, counter = _counting_task(tmp_path)
    recorded = _built(repo, tmp_path, task)
    harness = repo / "harness.yaml"
    text = harness.read_text(encoding="utf-8")
    if "min_free_memory_gb" in text:
        text = re.sub(r"min_free_memory_gb:\s*[\d.]+", "min_free_memory_gb: 3", text)
    else:
        text += "\nproof:\n  min_free_memory_gb: 3\n"
    harness.write_text(text, encoding="utf-8")
    monkeypatch.setattr(stages, "_free_memory_gb", lambda: 1.4)
    with pytest.raises(SystemExit):
        run_stage_proof(repo, "T1", recorded)
    printed = capsys.readouterr()
    assert "1.4 GB of commit memory free, below the 3 GB floor" in printed.out + printed.err
    assert counter.read_text() == "0"
    monkeypatch.setattr(stages, "_free_memory_gb", lambda: 8.0)
    run_stage_proof(repo, "T1", recorded)
    assert counter.read_text() == "1"


def test_every_proof_command_prints_its_elapsed_time_and_lands_in_the_journal(
        repo, tmp_path, capsys):
    from forge_cli import journal
    task, counter = _counting_task(tmp_path)
    recorded = _built(repo, tmp_path, task)
    run_stage_proof(repo, "T1", recorded)
    printed = capsys.readouterr().out
    assert "proof: " in printed and "passed (" in printed
    proofs = [e for e in journal.entries(repo, "ENG-1", "T1") if e["kind"] == "proof"]
    assert {e["command"] for e in proofs} >= {task["verify_commands"][0], "required test 'test_stage_contract'"}
    assert all(e["exit_code"] == 0 and "elapsed_s" in e for e in proofs)
