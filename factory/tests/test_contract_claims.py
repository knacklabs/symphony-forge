"""A contract is a claim with a place and a proof (decision 0082)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from test_gates import (  # noqa: F401
    DECOMP, HARNESS, READY_TASK_FIELDS, STAGE_TASK, head, repo, run,
    sign_off, intake, save_plan, stamp_and_commit, start_stage, write_in_scope,
)

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from factory_lib import load_json, task_evidence_path  # noqa: E402
from forge_cli.stages import run_stage_proof, task_for  # noqa: E402

CLAIM = {"id": "C-claim", "statement": "the slice runs green",
         "source": "plans/active/TEST-1-test-plan.md#acceptance-criteria",
         "lands_in": "src/core.py", "proof": "test_stage_contract"}


def _record(repo: Path, task: dict) -> tuple[int, str]:
    return run(repo, "record_decomposition_from_json.py",
               stdin=json.dumps({**DECOMP, "tasks": [task]}))


def test_the_recorder_accepts_a_claim_with_a_place_and_a_proof(repo, tmp_path):
    sign_off(repo)
    intake(repo)
    save_plan(repo, tmp_path)
    code, out = _record(repo, {**STAGE_TASK, "plan_contracts": [CLAIM]})
    assert code == 0, out
    code, out = _record(repo, {**STAGE_TASK, "plan_contracts": [{**CLAIM, "proof": "no_such_test"}]})
    assert code != 0 and "not one of this task's required_tests ids" in out, out
    code, out = _record(repo, {**STAGE_TASK, "plan_contracts": [{**CLAIM, "lands_in": "../x.py"}]})
    assert code != 0 and "lands_in must be a repo-relative posix path" in out, out
    code, out = _record(repo, {**STAGE_TASK, "plan_contracts": [{**CLAIM, "extra": "no"}]})
    assert code != 0 and "optionally lands_in and proof" in out, out


def test_the_proof_run_answers_each_bound_claim(repo, tmp_path):
    task = {**STAGE_TASK, "plan_contracts": [CLAIM]}
    start_stage(repo, tmp_path, task)
    write_in_scope(repo, "src/core.py")
    stamp_and_commit(repo)
    run_stage_proof(repo, "T1", task_for(repo, "T1"))
    verify = load_json(task_evidence_path(repo, "ENG-1", "T1", "verify.json"), default={})
    assert verify["claims"] == [{"id": "C-claim", "proof": "test_stage_contract",
                                 "status": "passed"}]


def test_a_partial_verdict_on_a_proven_claim_without_a_line_in_its_test_is_set_aside():
    """T5: seven partial verdicts on paragraphs, three rounds, zero defects.
    The claim's own test passed; the reviewer's partial is set aside unless it
    cites a line in that test."""
    from forge_cli.review import _contract_verdicts
    task = {"id": "T1", "plan_contracts": [CLAIM, {"id": "C-free", "statement": "free text",
                                                    "source": "plan"}]}
    proven = {"C-claim": ("test_stage_contract", "stage_contract_proof.py")}
    texts = ["VERDICT C-claim: partial — src/core.py:1 does half of it",
             "VERDICT C-free: partial — src/core.py:2 missing the rest"]
    out = {v["contract_id"]: v for v in _contract_verdicts(task, {}, [], {}, verdict_texts=texts,
                                                             proven=proven)}
    assert out["C-claim"]["verdict"] == "implemented"
    assert "set aside" in out["C-claim"]["evidence"] and "does half of it" in out["C-claim"]["evidence"]
    assert out["C-free"]["verdict"] == "partial", "an unbound contract is still the reviewer's call"
    # A line in the bound test itself is a real verdict against the proof.
    texts = ["VERDICT C-claim: partial — stage_contract_proof.py:3 asserts nothing about the slice"]
    out = {v["contract_id"]: v for v in _contract_verdicts(task, {}, [], {}, verdict_texts=texts,
                                                             proven=proven)}
    assert out["C-claim"]["verdict"] == "partial"
