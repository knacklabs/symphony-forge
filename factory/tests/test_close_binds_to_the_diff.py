"""Closeout binds to the product diff, and closes with one command.

Marking a task done took longer than building it. The review stamp hashed
the contract text, the brief text and every tracked file; the launch hashed
the contract and the brief; the grill hashed the measurement fields. None of
those is the code a reviewer read, so a scope widening, a decision record or
a contract re-record staled a review of unchanged code -- and one contract
edit orphaned the launch, staled the stamp and staled the grill at once. On
WF-1 T2 that was 4.5 hours, six reviews, one grill, a plan rewrite, a human
re-approval and a no-op Codex launch after a clean build.

Its own module: test_gates.py is one very large file where every added
branch collides with every other.
"""
from __future__ import annotations

import contextlib
import json
import shlex
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

from test_gates import (  # noqa: F401
    DECOMP, HARNESS, STAGE_TASK, delegation_ledger, fake_gh_env, git, head,
    load_factory_lib, measured_stage, record_stage_local, repo, run,
    stamp_and_commit, start_stage, story_state, write_in_scope,
    write_task_proof,
)

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from factory_lib import (  # noqa: E402
    load_json, plan_digest_without_assumptions, product_delta_digest,
    protected_decomposition_state_path, render_recorded_task_contract,
    task_evidence_path,
)
from forge_cli.stages import (  # noqa: E402
    load_stages, stamp_is_fresh, task_digest, task_for, write_stages,
)


def _stage(repo: Path, task_id: str = "T1") -> dict:
    return next(s for s in load_stages(repo)["stages"] if s["id"] == task_id)


def _rerecord(repo: Path, task: dict) -> tuple[int, str]:
    return run(repo, "record_decomposition_from_json.py",
               stdin=json.dumps({**DECOMP, "tasks": [task]}))


def _commit_decision(repo: Path, name: str = "0099-mid-stage-call") -> None:
    path = repo / "docs" / "decisions" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {name}\n\nAnswered a worker signal.\n", encoding="utf-8")
    git(repo, "add", path.relative_to(repo).as_posix())
    git(repo, "commit", "-qm", f"decision {name}")


# ------------------------------------------------- the stamp is about the diff


def test_the_stamp_survives_bookkeeping_but_not_reviewed_meaning(repo, tmp_path):
    """Bookkeeping can reuse; a semantic contract change cannot."""
    start_stage(repo, tmp_path, STAGE_TASK)
    write_in_scope(repo, "src/core.py")
    stamp_and_commit(repo)
    stage, task = _stage(repo), task_for(repo, "T1")
    assert stamp_is_fresh(repo, stage, task)
    assert "delta_id" in stage["local_review_stamp"]
    assert "product_tree_digest" not in stage["local_review_stamp"]
    assert "brief_sha256" not in stage["local_review_stamp"]

    _commit_decision(repo)
    assert stamp_is_fresh(repo, _stage(repo), task), "a decision record staled the review"

    code, out = _rerecord(repo, {**STAGE_TASK, "write_scope": ["src/", "lib/"]})
    assert code == 0, out
    assert not stamp_is_fresh(repo, _stage(repo), task_for(repo, "T1")), \
        "a reviewed-meaning change reused the old review"


def test_the_stamp_goes_stale_on_exactly_a_product_change(repo, tmp_path):
    start_stage(repo, tmp_path, STAGE_TASK)
    write_in_scope(repo, "src/core.py", "version = 1\n")
    stamp_and_commit(repo)
    assert stamp_is_fresh(repo, _stage(repo), task_for(repo, "T1"))
    write_in_scope(repo, "src/core.py", "version = 2\n")
    git(repo, "add", "src/core.py")
    git(repo, "commit", "-qm", "the diff moved")
    assert not stamp_is_fresh(repo, _stage(repo), task_for(repo, "T1"))
    code, out = run(repo, "forge.py", "stage", "done", "T1")
    assert code != 0 and "STALE stage-local review stamp" in out, out
    assert "the product diff changed since the review read it" in out
    assert "task close T1" in out


# --------------------------------------- the T2 cascade, replayed and ended


def test_stage_done_requires_review_after_semantic_contract_rerecord(repo, tmp_path):
    """A launch remains attributable, but changed reviewed meaning reruns review."""
    start_stage(repo, tmp_path, STAGE_TASK)
    write_in_scope(repo, "src/core.py")
    stamp_and_commit(repo)
    ledger = [json.loads(line) for line in
              delegation_ledger(repo).read_text().splitlines()]
    launched_under = ledger[-1]["task_sha256"]

    code, out = _rerecord(repo, {**STAGE_TASK, "write_scope": ["src/", "lib/"]})
    assert code == 0, out
    assert "changed only in how the work is MEASURED" in out
    # The launch that built the code was made under the OLD contract digest
    # and still counts: it proves Codex wrote inside this stage.
    assert task_digest(task_for(repo, "T1")) != launched_under

    code, out = run(repo, "forge.py", "stage", "done", "T1")
    assert code != 0, out
    assert "STALE stage-local review stamp" in out


def test_native_stage_done_requires_current_scope_bound_preparation(
        repo, tmp_path, monkeypatch, capsys):
    """Host-native close binds preparation without inventing PID evidence."""
    from forge_cli.delegate import brief_path, launch_companion
    from forge_cli.stages import _require_successful_launch

    monkeypatch.setenv("FORGE_COORDINATOR", "codex")
    # This fixture is not a trusted Codex checkout, and the readiness probe
    # shells out to the real `codex` CLI -- absent in CI, and bound to the
    # harness rather than this temp repo locally. The gate has its own
    # regression coverage in test_native_setup.py.
    from forge_cli import doctor
    monkeypatch.setattr(
        doctor, "codex_hook_readiness", lambda _base: (True, "fixture-ready"),
    )
    start_stage(repo, tmp_path, STAGE_TASK, launch=False)
    stage, task = _stage(repo), task_for(repo, "T1")
    with pytest.raises(SystemExit):
        _require_successful_launch(repo, "T1", stage, task)
    assert "preparation" in capsys.readouterr().out.lower()

    common = dict(
        task_id="T1", text="# T1 native brief\n", path=brief_path(repo, "T1"),
        task_sha256_value=task_digest(task), model="ignored", effort="ignored",
        write=True, story="ENG-1", stage_started_at=stage["started_at"],
        task_metadata=task,
    )
    launch_companion(repo, write_scope=["other/"], **common)
    with pytest.raises(SystemExit):
        _require_successful_launch(repo, "T1", stage, task)
    assert "scope" in capsys.readouterr().out.lower()

    launch_companion(repo, write_scope=task["write_scope"], **common)
    assert _require_successful_launch(repo, "T1", stage, task) == ""

    brief_path(repo, "T1").write_text("# stale native brief\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        _require_successful_launch(repo, "T1", stage, task)
    assert "brief" in capsys.readouterr().out.lower()
    launch_companion(repo, write_scope=task["write_scope"], **common)
    assert _require_successful_launch(repo, "T1", stage, task) == ""

    write_in_scope(repo, "src/core.py")
    git(repo, "add", "src/core.py")
    git(repo, "commit", "-qm", "native host work")
    write_task_proof(repo, "T1", publish_review=True)
    stamp_and_commit(repo)
    code, out = run(
        repo, "forge.py", "stage", "done", "T1",
        env={"FORGE_COORDINATOR": "codex"},
    )
    assert code == 0, out


def test_legacy_stamp_never_converts_in_normal_runtime(repo, tmp_path):
    """Lean migration owns old stamp conversion; runtime requires current proof."""
    start_stage(repo, tmp_path, STAGE_TASK)
    write_in_scope(repo, "src/core.py")
    git(repo, "add", "src/core.py")
    git(repo, "commit", "-qm", "work")
    write_task_proof(repo, "T1", publish_review=True)
    data = load_stages(repo)
    stage = next(s for s in data["stages"] if s["id"] == "T1")
    legacy = {
        "stage_id": "T1",
        "task_sha256": task_digest(task_for(repo, "T1")),
        "brief_sha256": "legacy",
        "base_sha": stage["base_sha"],
        "product_tree_digest": product_delta_digest(repo, stage["base_sha"]),
        "recorded_at": "2026-09-09T00:00:00+00:00",
        "generated_by": "autoreview",
    }
    stage["local_review_stamp"] = legacy
    from forge_cli.stages import write_stages
    write_stages(repo, data)

    assert not stamp_is_fresh(repo, _stage(repo), task_for(repo, "T1"))


# -------------------------------------------------------- the grill and plan


def test_the_grill_reads_the_recorded_contract_and_the_amended_scope(repo, tmp_path):
    """The cold reader used to see only the plan's hand-written copy of the
    contract; a path added with amend-scope was invisible to it, which is
    what pushed T2 into re-recording. It now reads the contract itself."""
    from forge_cli.grill import _contract_section
    start_stage(repo, tmp_path, STAGE_TASK)
    section = _contract_section(repo, "task", "T1")
    assert "The contract as recorded" in section
    assert "- src/" in section
    assert "the slice runs green" in section

    write_in_scope(repo, "src/core.py")
    write_in_scope(repo, "lib/helper.py")
    git(repo, "add", "src/core.py", "lib/helper.py")
    git(repo, "commit", "-qm", "touches a path outside scope")
    code, out = run(repo, "forge.py", "stage", "amend-scope", "T1",
                    "--reason", "the helper is the only seam for the criterion")
    assert code == 0, out
    section = _contract_section(repo, "task", "T1")
    assert "lib/helper.py" in section and "only seam" in section


def test_task_plan_omits_contract_rendered_from_decomposition(repo, tmp_path):
    start_stage(repo, tmp_path, STAGE_TASK)
    plan = story_state(repo) / "task-plans" / "T1.md"
    text = plan.read_text(encoding="utf-8")
    assert "<!-- forge:contract -->" not in text
    contract = render_recorded_task_contract(repo, "T1")
    assert "<!-- forge:contract -->" in contract and "- src/" in contract
    before = plan_digest_without_assumptions(plan)

    write_in_scope(repo, "src/core.py")
    write_in_scope(repo, "lib/helper.py")
    git(repo, "add", "src/core.py", "lib/helper.py")
    git(repo, "commit", "-qm", "touches a path outside scope")
    code, out = run(repo, "forge.py", "stage", "amend-scope", "T1",
                    "--reason", "the helper is the only seam for the criterion")
    assert code == 0, out
    contract = render_recorded_task_contract(repo, "T1")
    assert "lib/helper.py" in contract and "only seam" in contract
    assert "<!-- forge:contract -->" not in plan.read_text(encoding="utf-8")
    assert plan_digest_without_assumptions(plan) == before, \
        "rendering the contract changed the plan's approval digest"


# --------------------------------------------------------- one command


def _ship_ready(repo: Path, tmp_path: Path) -> dict:
    """A built, reviewed, committed task with an origin and a fake gh."""
    git(repo, "config", "user.email", "test@knacklabs.dev")
    git(repo, "config", "user.name", "Gate Tests")
    remote = tmp_path / "origin.git"
    proc = subprocess.run(["git", "init", "--bare", str(remote)],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    if "origin" not in git(repo, "remote").split():
        git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", f"{head(repo)}:refs/heads/main")
    git(repo, "fetch", "-q", "origin")
    git(repo, "checkout", "-qb", "feat/test-close")
    python = shlex.quote(sys.executable)
    task = {
        **STAGE_TASK,
        "verify_commands": [f"{python} -m compileall src"],
        "required_tests": [{
            "id": "test_plan_body_digest_is_line_ending_agnostic",
            "path": "factory/tests/test_gates.py",
            "command": (
                f"{python} -m pytest {{path}}::{{id}} -o junit_family=legacy "
                "--junitxml={report}"
            ),
        }],
    }
    start_stage(repo, tmp_path, task)
    write_in_scope(repo, "src/core.py")
    stamp_and_commit(repo)
    # The seal pushes the run pointer's branch; the intake fixture names a
    # story branch it never creates. Point it at the branch we are on, as
    # `forge task start` would have (and as prepare_task_pr_ready does).
    control = delegation_ledger(repo).parent
    pointer = json.loads((control / "run.json").read_text(encoding="utf-8"))
    pointer.update({
        "task_id": "T1",
        "branch": git(repo, "symbolic-ref", "--short", "HEAD"),
        "base_main_sha": git(repo, "rev-parse", "origin/main"),
    })
    (control / "run.json").write_text(json.dumps(pointer), encoding="utf-8")
    env, _ = fake_gh_env(tmp_path)
    with pytest.MonkeyPatch.context() as proof_environment:
        proof_environment.setenv("FORGE_COORDINATOR", "claude")
        for key, value in env.items():
            proof_environment.setenv(key, value)
        proof = write_task_proof(repo, "T1", publish_review=True)
    git(repo, "add", proof.relative_to(repo).as_posix(),
        ".factory/review-briefs/all.md")
    git(repo, "commit", "-qm", "record T1 proof")
    return env


def test_task_close_goes_from_built_to_pr_and_is_idempotent(repo, tmp_path):
    env = _ship_ready(repo, tmp_path)
    marker = story_state(repo) / "tasks" / "T1" / "pr-ready.json"

    code, out = run(repo, "forge.py", "task", "close", "T1",
                    "--skill", str(tmp_path / "no-such-autoreview"), env=env)
    assert code == 0, out
    # The stamp covered this diff, so no review ran -- the missing skill
    # would have failed it.
    assert "no review needed" in out
    assert measured_stage(repo)["status"] == "done"
    assert marker.is_file()
    sealed_head = head(repo)

    # Run it again with nothing changed: nothing is redone, nothing is
    # re-committed.
    code, out = run(repo, "forge.py", "task", "close", "T1",
                    "--skill", str(tmp_path / "no-such-autoreview"), env=env)
    assert code == 0, out
    assert "is closed and its review covers the current diff" in out
    assert head(repo) == sealed_head


def test_task_close_reopens_a_done_stage_whose_diff_moved(repo, tmp_path):
    """A moved post-seal diff gets a fresh proof before review is launched."""
    env = _ship_ready(repo, tmp_path)
    code, out = run(repo, "forge.py", "task", "close", "T1",
                    "--skill", str(tmp_path / "no-such-autoreview"), env=env)
    assert code == 0, out

    write_in_scope(repo, "src/core.py", "version = 2\n")
    git(repo, "add", "src/core.py")
    git(repo, "commit", "-qm", "post-seal fix")
    code, out = run(repo, "forge.py", "task", "close", "T1",
                    "--skill", str(tmp_path / "no-such-autoreview"), env=env)
    assert code != 0, out
    assert "autoreview skill not found" in out, out
    assert "review proof preflight failed before helper launch" not in out, out
    assert "T1: task proof committed" in out, out
    assert "reopened: the diff moved" in out
    stage = _stage(repo)
    assert stage["status"] == "active"
    assert stage["review_fix_count"] == 1
    assert "local_review_stamp" not in stage
    events = [json.loads(p.read_text()) for p in (repo / ".factory" / "events").glob("*.json")]
    assert any(e.get("event") == "stage-reopened" for e in events)


FAKE_REVIEW_WITH = r'''
import json, os, pathlib, sys
args = sys.argv[1:]
out = pathlib.Path(args[args.index("--json-output") + 1])
priority = os.environ["FAKE_PRIORITY"]
findings = [
    {"title": "[quality] VERDICT C1: implemented", "body": "src/core.py:1 runs green",
     "priority": "P3", "confidence": 1, "category": "maintainability",
     "source_attribution": None, "code_location": {"file_path": "src/core.py", "line": 1}},
    {"title": "[quality] Name the literal", "body": "src/core.py:1 bare literal",
     "priority": priority, "confidence": 0.9, "category": "maintainability",
     "source_attribution": None, "code_location": {"file_path": "src/core.py", "line": 1}},
]
provider = {"findings": findings, "overall_correctness": "patch is incorrect",
            "overall_explanation": (
                "BEGIN FORGE ASSESSMENT quality\nRead.\nEND FORGE ASSESSMENT quality\n"
                "BEGIN FORGE ASSESSMENT performance\nFine.\nEND FORGE ASSESSMENT performance\n"
                "BEGIN FORGE ASSESSMENT security\nSafe.\nEND FORGE ASSESSMENT security"),
            "overall_confidence": 0.9}
out.write_text(json.dumps({**provider, "provider_report": provider, "review_status": "findings"},
                          indent=2) + "\n", encoding="utf-8")
sys.exit(1)
'''


def _post_seal_fix_with_a_review(repo: Path, tmp_path: Path, priority: str) -> tuple[dict, str]:
    """Seal T1, move its diff, and close again with a helper that answers
    with one finding of the given priority."""
    env = _ship_ready(repo, tmp_path)
    code, out = run(repo, "forge.py", "task", "close", "T1",
                    "--skill", str(tmp_path / "no-such-autoreview"), env=env)
    assert code == 0, out
    write_in_scope(repo, "src/core.py", "version = 2\n")
    git(repo, "add", "src/core.py")
    git(repo, "commit", "-qm", "post-seal fix")
    review_env = {**env, "FAKE_PRIORITY": priority}
    with pytest.MonkeyPatch.context() as proof_environment:
        proof_environment.setenv("FORGE_COORDINATOR", "claude")
        for key, value in review_env.items():
            proof_environment.setenv(key, value)
        write_task_proof(repo, "T1")
    task_reviews = story_state(repo) / "tasks" / "T1" / "reviews"
    for aspect in ("quality", "performance", "security"):
        (task_reviews / f"{aspect}.json").unlink()
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "proof at the new tip")
    skill = tmp_path / "fake-autoreview.py"
    skill.write_text(FAKE_REVIEW_WITH, encoding="utf-8")
    code, out = run(repo, "forge.py", "task", "close", "T1", "--engine", "claude",
                    "--skill", str(skill), env=review_env)
    return {"code": code, "env": env, "skill": skill}, out


def test_close_says_the_review_covers_the_whole_task_delta(repo, tmp_path):
    """The stop message promised a re-review of "only the new diff"; a review
    always covers the task delta, base to tip (0069), and says so."""
    result, out = _post_seal_fix_with_a_review(repo, tmp_path, "P1")
    assert result["code"] != 0, out
    assert "1 blocking finding(s)" in out
    assert "selected generation" in out
    assert "1 of 1 actionable P0/P1 defect finding(s) untriaged" in out
    assert './forge review T1 --triage "<finding text>"' in out
    assert out.index('./forge review T1 --triage "<finding text>"') \
        < out.index("./forge delegate T1")
    assert "reviews the whole task delta, base to tip" in out
    assert "only the new diff" not in out


def test_recorded_non_blocking_follow_ups_never_trigger_another_review(repo, tmp_path):
    """A P2 is a recorded follow-up: the stage seals on the stamp, and a
    second close finds the stamp fresh and spends no review on it."""
    result, out = _post_seal_fix_with_a_review(repo, tmp_path, "P2")
    assert result["code"] == 0, out
    assert "non-blocking=1" in out
    assert measured_stage(repo)["status"] == "done"
    code, out = run(repo, "forge.py", "task", "close", "T1",
                    "--skill", str(tmp_path / "no-such-autoreview"), env=result["env"])
    assert code == 0, out
    assert "is closed and its review covers the current diff" in out


def test_task_close_runs_the_proof_before_it_spends_a_review(repo, tmp_path):
    """T2 at 08:25: review clean, then stage done found a failing required
    test, then the fix cost a second review. Proof first means the failing
    test is the cheapest possible stop."""
    env = _ship_ready(repo, tmp_path)
    write_in_scope(repo, "src/core.py", "version = 2\n")
    git(repo, "add", "src/core.py")
    git(repo, "commit", "-qm", "unreviewed change")
    code, out = _rerecord(repo, {**STAGE_TASK, "verify_commands": ["false"]})
    assert code == 0, out
    code, out = run(repo, "forge.py", "task", "close", "T1",
                    "--skill", str(tmp_path / "no-such-autoreview"), env=env)
    assert code != 0, out
    assert "verify command" in out, out
    assert "autoreview skill not found" not in out, "the review ran before the proof"
    assert "is not recorded for ENG-1" not in out, "the review ran before the proof"


def test_task_close_is_the_single_full_suite_owner_and_records_truthful_automated_proof(
        repo, monkeypatch):
    from forge_cli import close, delegate, review, stages, tasks

    task = {**STAGE_TASK, "verify_commands": ["canonical verify"]}
    stage = {"id": "T1", "status": "active", "started_at": "now"}
    (repo / ".factory" / "run.json").write_text(
        json.dumps({"issue_key": "ENG-1", "story": "ENG-1"}),
        encoding="utf-8",
    )
    story_state(repo).mkdir(parents=True, exist_ok=True)
    proof_root = story_state(repo) / "tasks" / "T1"
    proof_root.mkdir(parents=True, exist_ok=True)
    tests_path = proof_root / "tests.json"
    tests_path.write_text(json.dumps({
        "commit": head(repo),
        "automated": {
            "generated_by": "implementer", "status": "passed",
            "summary": "focused checks passed", "blocking_findings": [],
            "commands_run": ["focused pytest"], "reviewed_scope": ["src/"],
            "remaining_gaps": [], "recorded_at": "earlier", "commit": head(repo),
        },
        "functional": {
            "generated_by": "functional-checker", "status": "passed",
            "score": 9, "blocking_findings": [],
            "commands_run": ["manual functional"],
        },
    }), encoding="utf-8")
    reviewed = {"done": False}

    monkeypatch.setattr(review, "_product_dirty", lambda _base: [])
    monkeypatch.setattr(close, "load_json", lambda *_args, **_kwargs: {
        "issue_key": "ENG-1",
    })
    monkeypatch.setattr(close, "task_seal_shared_problems", lambda *_args: [])
    monkeypatch.setattr(stages, "task_for", lambda *_args: task)
    monkeypatch.setattr(stages, "load_stages", lambda _base: {"stages": [stage]})
    monkeypatch.setattr(stages, "stage_review_binding", lambda *_args: {
        "delta_id": "d" * 64,
    })
    monkeypatch.setattr(stages, "_measure", lambda *_args: {"strays": []})
    monkeypatch.setattr(stages, "_require_successful_launch", lambda *_args: "")
    monkeypatch.setattr(stages, "stamp_is_fresh", lambda *_args: reviewed["done"])
    monkeypatch.setattr(delegate, "load_delegations", lambda _base: [])
    monkeypatch.setattr(
        delegate, "delegation_exclusion",
        lambda *_args, **_kwargs: contextlib.nullcontext(),
    )

    proof = ({}, {}, [])
    fresh_context = {"proofs": "from-close"}

    def run_proof(_base, _task_id, _task, *, proof_context=None):
        assert proof_context == {}
        proof_context.update(fresh_context)
        stages.record_stage_proof(
            repo, _task_id, _task, key="proof-key",
            verify_results=[{
                "command": "canonical verify", "status": "passed",
                "exit_code": 0,
            }],
            test_results=[{
                "id": "test_stage_contract", "path": "stage_contract_proof.py",
                "status": "passed",
            }],
            test_id_misses=[], close_owned=True,
            commands_run=["canonical verify"],
        )
        return proof

    monkeypatch.setattr(stages, "run_stage_proof", run_proof)

    def commit_proof(_base, _story, _task_id, proof, *, proof_context=None):
        assert proof_context == fresh_context
        return proof

    monkeypatch.setattr(close, "_commit_task_proof", commit_proof)
    monkeypatch.setattr(
        close, "task_proof_problems", lambda *_args, **_kwargs: [],
    )

    def run_review(*_args, **kwargs):
        assert kwargs["proof_context"] == fresh_context
        evidence = json.loads(tests_path.read_text(encoding="utf-8"))
        automated = evidence["automated"]
        assert automated["commands_run"] == ["focused pytest", "canonical verify"]
        assert "close-owned proof:" in automated["pass_fail_summary"]
        assert automated["bound_by"] == "stage-proof"
        assert evidence["functional"] == {
            "generated_by": "functional-checker", "status": "passed",
            "score": 9, "blocking_findings": [],
            "commands_run": ["manual functional"],
        }
        reviewed["done"] = True
        return {"blocking": 0}

    monkeypatch.setattr(review, "review_task", run_review)
    monkeypatch.setattr(
        stages, "_finish_stage",
        lambda *_args, **_kwargs: stage.update(status="done"),
    )
    monkeypatch.setattr(tasks, "seal_task", lambda *_args: None)

    close.cmd_task_close(Namespace(
        repo=str(repo), id="T1", engine="codex", max_priority="P3", skill=None,
    ))

    assert reviewed["done"] is True
    assert stage["status"] == "done"


def test_task_close_reruns_review_for_clean_selection_with_stale_meaning(
        repo, monkeypatch):
    import factory_lib
    from forge_cli import close, delegate, review, stages, tasks

    task = {**STAGE_TASK, "verify_commands": ["canonical verify"]}
    stage = {"id": "T1", "status": "active", "started_at": "now"}
    delta_id = "d" * 64
    generation = {
        "origin": "combined", "input": {"sha256": "old", "bytes": 3},
        "delta_id": delta_id,
    }
    (repo / ".factory" / "run.json").write_text(
        json.dumps({"issue_key": "ENG-1"}), encoding="utf-8",
    )
    monkeypatch.setattr(review, "_product_dirty", lambda _base: [])
    monkeypatch.setattr(close, "load_json", lambda *_args, **_kwargs: {
        "issue_key": "ENG-1",
    })
    monkeypatch.setattr(close, "task_seal_shared_problems", lambda *_args: [])
    monkeypatch.setattr(stages, "task_for", lambda *_args: task)
    monkeypatch.setattr(stages, "load_stages", lambda _base: {"stages": [stage]})
    monkeypatch.setattr(stages, "stage_review_binding", lambda *_args: {
        "delta_id": delta_id,
    })
    monkeypatch.setattr(stages, "_measure", lambda *_args: {"strays": []})
    monkeypatch.setattr(stages, "_require_successful_launch", lambda *_args: "")
    monkeypatch.setattr(stages, "stamp_is_fresh", lambda *_args: False)
    monkeypatch.setattr(stages, "reviewed_meaning_identity", lambda *_args: {
        "accepted_inputs": [{"sha256": "new", "bytes": 3}],
    })
    monkeypatch.setattr(stages, "stamp_stage_review", lambda *_args, **_kwargs: pytest.fail(
        "close tried to restamp a selection with stale reviewed meaning",
    ))
    monkeypatch.setattr(delegate, "load_delegations", lambda _base: [])
    monkeypatch.setattr(
        delegate, "delegation_exclusion",
        lambda *_args, **_kwargs: contextlib.nullcontext(),
    )
    monkeypatch.setattr(stages, "run_stage_proof", lambda *_args, **_kwargs: ({}, {}, []))
    monkeypatch.setattr(close, "_commit_task_proof", lambda *_args, **_kwargs: ({}, {}, []))
    monkeypatch.setattr(close, "task_proof_problems", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(factory_lib, "selected_review_problems", lambda *_args: [])
    monkeypatch.setattr(
        factory_lib, "read_selected_review_generation",
        lambda *_args, **kwargs: (
            generation, {"generation_id": "g"},
            [] if kwargs.get("expected_delta_id") == delta_id else ["wrong delta"],
        ),
    )
    reviewed = []
    monkeypatch.setattr(review, "review_task", lambda *_args, **_kwargs: (
        reviewed.append(True) or {"blocking": 0}
    ))
    monkeypatch.setattr(
        stages, "_finish_stage", lambda *_args, **_kwargs: stage.update(status="done"),
    )
    monkeypatch.setattr(tasks, "seal_task", lambda *_args: None)

    close.cmd_task_close(Namespace(
        repo=str(repo), id="T1", engine="codex", max_priority="P3", skill=None,
    ))

    assert reviewed == [True]
    assert stage["status"] == "done"


@pytest.mark.parametrize("user_facing", [False, True])
def test_fresh_close_owned_report_lists_only_executed_commands(
        repo, monkeypatch, user_facing):
    from forge_cli import stages

    task = {**STAGE_TASK, "user_facing": user_facing}
    (repo / ".factory" / "run.json").write_text(
        json.dumps({"issue_key": "ENG-1", "story": "ENG-1"}),
        encoding="utf-8",
    )
    story_state(repo).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(stages, "_review_covers_tree", lambda *_args: False)
    stages.record_stage_proof(
        repo, "T1", task, key="proof-key",
        verify_results=[{"command": "true", "exit_code": 0}],
        test_results=[{"id": "test_stage_contract", "path": "stage_contract_proof.py",
                       "status": "passed"}],
        test_id_misses=[], close_owned=True, commands_run=["true"],
    )
    evidence = json.loads(
        (story_state(repo) / "tasks/T1/tests.json").read_text(encoding="utf-8")
    )
    automated = evidence["automated"]
    assert automated["commands_run"] == ["true"]
    assert "executed commands=1" in automated["summary"]
    assert "required test command" not in automated["commands_run"]


def test_task_close_stops_early_and_names_the_next_step(repo, tmp_path):
    start_stage(repo, tmp_path, STAGE_TASK)
    write_in_scope(repo, "src/core.py")
    code, out = run(repo, "forge.py", "task", "close", "T1")
    assert code != 0, out
    assert "close stopped at tree" in out and "commit the product tree" in out


@pytest.mark.parametrize("invalid", ["launch", "measurement"])
def test_task_close_checks_stage_inputs_before_running_proof(repo, tmp_path, invalid):
    env = _ship_ready(repo, tmp_path)
    marker = tmp_path / "proof-started"
    command = shlex.join([
        sys.executable, "-c",
        f"from pathlib import Path; Path({str(marker)!r}).touch()",
    ])
    code, out = _rerecord(repo, {**STAGE_TASK, "verify_commands": [command]})
    assert code == 0, out
    if invalid == "launch":
        delegation_ledger(repo).write_text("", encoding="utf-8")
        expected = "no successful write launch"
    else:
        write_in_scope(repo, "src/core.py", "# oversized change\n" * 801)
        git(repo, "add", "src/core.py")
        git(repo, "commit", "-qm", "exceed the hard review bound")
        expected = "more than TWICE"

    code, out = run(repo, "forge.py", "task", "close", "T1", env=env)

    assert not marker.exists(), "proof ran before the invalid stage was rejected"
    assert code != 0 and expected in out, out


def test_task_close_checks_every_required_path_before_running_proof(repo, tmp_path):
    env = _ship_ready(repo, tmp_path)
    marker = tmp_path / "proof-started"
    command = shlex.join([
        sys.executable, "-c",
        f"from pathlib import Path; Path({str(marker)!r}).touch()",
    ])
    required = [*STAGE_TASK["required_tests"], {
        "id": "test_missing", "path": "missing_proof.py",
        "command": "python3 {path} {id} {report}",
    }]
    code, out = _rerecord(repo, {
        **STAGE_TASK, "required_tests": required, "verify_commands": [command],
    })
    assert code == 0, out

    code, out = run(repo, "forge.py", "task", "close", "T1", env=env)

    assert code != 0 and "required test 'test_missing' is missing" in out, out
    assert not marker.exists(), "verification ran before all required paths were checked"


def test_required_input_is_rechecked_after_an_earlier_test_runs(tmp_path, capsys):
    from forge_cli.stages import _run_required_tests

    runner = tmp_path / "runner.py"
    runner.write_text(
        "import sys\nfrom pathlib import Path\n"
        "source, name, report = sys.argv[1:]\n"
        "if source == 'first.py':\n    Path('second.py').unlink()\n"
        "Path(report).write_text('<testsuite><testcase name=\"' + name + "
        "'\" file=\"' + source + '\"/></testsuite>')\n",
        encoding="utf-8",
    )
    for name in ("first.py", "second.py"):
        (tmp_path / name).touch()
    command = shlex.join([sys.executable, str(runner), "{path}", "{id}", "{report}"])
    task = {"required_tests": [
        {"id": "test_first", "path": "first.py", "command": command},
        {"id": "test_second", "path": "second.py", "command": command},
    ]}

    with pytest.raises(SystemExit):
        _run_required_tests(tmp_path, "T1", task)

    assert "required test 'test_second' is missing" in capsys.readouterr().out


# ------------------------------------------------- the contracts say close


def test_forge_next_and_the_review_hint_name_close(repo, tmp_path):
    from forge_cli.review import _next_hint
    assert "task close T1" in _next_hint("T1", "active", 0, 0)
    assert "task close T1" in _next_hint("T1", "done", 2, 0)
    phase = (HARNESS / "factory" / "scripts" / "forge_cli" / "phase.py").read_text(encoding="utf-8")
    assert "./forge task close {id}" in phase
    workflow = (HARNESS / "WORKFLOW.md").read_text(encoding="utf-8")
    assert "forge task close <id>" in workflow
    assert "delta_id" in workflow


# --------------------------------------- the review verdict has one source


def _record_quality_with_a_partial_contract(repo: Path) -> None:
    """What the recorder does with a partial verdict: it BECOMES a blocking
    finding in the recorded file, whatever the payload's own list said."""
    write_task_proof(repo, "T1")
    code, out = run(repo, "forge.py", "review-brief", "--all")
    assert code == 0, out
    payload = {
        "generated_by": "autoreview", "task_id": "T1", "score": 10,
        "summary": "quality lens", "blocking_findings": [],
        "non_blocking_findings": [], "recommendation": "approve",
        "skills_used": ["review-animations"],
        "contract_verdicts": [
            {"contract_id": "C1", "verdict": "partial", "evidence": "half of it"},
        ],
    }
    code, out = run(repo, "record_review_from_json.py", "--aspect", "quality",
                    "--task", "T1", stdin=json.dumps(payload))
    assert code == 0, out


def test_the_review_verdict_is_counted_from_what_was_recorded(repo, tmp_path):
    """A fixed diagnostic cannot compete with the selected generation."""
    from forge_cli.review import recorded_review_totals
    start_stage(repo, tmp_path, STAGE_TASK)
    write_in_scope(repo, "src/core.py")
    git(repo, "add", "src/core.py")
    git(repo, "commit", "-qm", "work")
    _record_quality_with_a_partial_contract(repo)
    blocking, caveats, recorded = recorded_review_totals(
        repo, "ENG-1", "T1", ("quality",))
    assert blocking == 0 and caveats == 0 and recorded["quality"] == {}
    write_task_proof(repo, "T1", publish_review=True)
    blocking, caveats, recorded = recorded_review_totals(
        repo, "ENG-1", "T1", ("quality",))
    assert blocking == 0 and caveats == 0
    assert recorded["quality"]["score"] == 10


def test_actionable_review_rows_exclude_plan_contract_acceptance_blockers(
        repo, tmp_path):
    from factory_lib import publish_review_generation, read_selected_review_generation
    from forge_cli.review import (
        actionable_blocking_with_triage, untriaged_actionable_blocking,
    )

    start_stage(repo, tmp_path, STAGE_TASK)
    write_in_scope(repo, "src/core.py")
    git(repo, "add", "src/core.py")
    git(repo, "commit", "-qm", "work")
    write_task_proof(repo, "T1", publish_review=True, review_blocked=True)
    generation, _selection, problems = read_selected_review_generation(
        repo, "ENG-1", "T1",
    )
    assert not problems and generation is not None
    candidate = json.loads(json.dumps(generation))
    candidate.pop("generation_id")
    candidate["lenses"]["quality"]["blocking_findings"].append({
        "category": "plan-contract-partial",
        "area": "src/core.py",
        "summary": "C1 remains partial",
        "file_path": "src/core.py",
        "line": 1,
        "title": "VERDICT C1: partial",
    })
    candidate["lenses"]["quality"].update({
        "score": 7, "recommendation": "request-changes",
    })
    publish_review_generation(
        repo, "ENG-1", "T1", candidate,
        expected_source_id=generation["generation_id"],
    )

    rows = actionable_blocking_with_triage(repo, "ENG-1", "T1")
    assert [(lens, finding["category"]) for lens, finding, _triage in rows] == [
        ("security", "security"),
    ]
    assert untriaged_actionable_blocking(repo, "ENG-1", "T1") == (1, 1)


def test_the_delegate_brief_carries_the_selected_current_findings(repo, tmp_path):
    """G4. A fix launch used to get a brief that said nothing about the
    findings it existed to fix; one made zero edits. The recorded findings
    are the channel."""
    from forge_cli.delegate import compose_brief
    start_stage(repo, tmp_path, STAGE_TASK)
    write_in_scope(repo, "src/core.py")
    git(repo, "add", "src/core.py")
    git(repo, "commit", "-qm", "work")
    task = task_for(repo, "T1")
    before = compose_brief(repo, task, write=True, user_facing=False, story="ENG-1")
    assert "Review findings to fix" not in before

    write_task_proof(repo, "T1", publish_review=True, review_blocked=True)
    diagnostic = story_state(repo) / "tasks" / "T1" / "reviews" / "quality.json"
    stale = {"score": 1}
    stale["blocking_findings"] = [{
        "category": "bug", "area": "old.py", "summary": "obsolete finding",
    }]
    diagnostic.write_text(json.dumps(stale))
    after = compose_brief(repo, task, write=True, user_facing=False, story="ENG-1")
    assert "Review findings to fix" in after
    assert "BLOCKING" in after
    assert "[security] security: selected current finding" in after
    assert "obsolete finding" not in after


# --------------------------------------------- the porcelain parse bug


def test_product_dirty_does_not_eat_the_first_path_character(repo):
    """The first porcelain entry for an unstaged edit starts with a space;
    stripping the output then `line[3:]` cut a character off the path, so a
    dirty `plans/roadmap.json` read as `lans/roadmap.json` and refused a review
    on harness bookkeeping. Every path must come back whole."""
    from forge_cli.review import _product_dirty
    # Two tracked files: one under an excluded prefix, one product.
    (repo / "plans").mkdir(exist_ok=True)
    (repo / "plans" / "roadmap.json").write_text("{}\n", encoding="utf-8")
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "core.py").write_text("v = 1\n", encoding="utf-8")
    git(repo, "add", "plans/roadmap.json", "src/core.py")
    git(repo, "commit", "-qm", "seed")
    assert _product_dirty(repo) == []
    # An UNSTAGED modification to the excluded file is the first entry.
    (repo / "plans" / "roadmap.json").write_text("{\"x\": 1}\n", encoding="utf-8")
    assert _product_dirty(repo) == []
    # A product edit is reported with its full path, whether or not an excluded
    # entry precedes it.
    (repo / "src" / "core.py").write_text("v = 2\n", encoding="utf-8")
    assert _product_dirty(repo) == ["src/core.py"]


# ------------------------------------------------- the proof runs once (0079)


def test_task_close_records_the_proof_in_the_marker_commit(repo, tmp_path):
    """The PR gate reads verify.json and tests.json from the sealed tree, so
    the proof close ran ships with the marker."""
    from factory_lib import task_evidence_path
    env = _ship_ready(repo, tmp_path)
    # The fixture starts with a worker proof. Remove only its typed receipts so
    # this close exercises the fresh stage-proof -> proof commit -> seal path.
    stages = load_stages(repo)
    for stage in stages["stages"]:
        if stage.get("id") == "T1":
            stage.pop("proof_receipts", None)
    write_stages(repo, stages)
    code, out = run(repo, "forge.py", "task", "close", "T1", env=env)
    assert code == 0, out
    assert "proof reused" not in out
    shown = git(repo, "show", "--name-only", "--format=", "HEAD")
    verify_rel = task_evidence_path(
        repo, "ENG-1", "T1", "verify.json").relative_to(repo).as_posix()
    tests_rel = task_evidence_path(
        repo, "ENG-1", "T1", "tests.json").relative_to(repo).as_posix()
    # Close commits the proof it recorded as its own commit before the
    # review; the marker commit follows and names it. The worker's tests.json
    # was committed unchanged before close and is simply in the sealed tree.
    assert "pr-ready.json" in shown and verify_rel not in shown, shown
    proof_commit = git(repo, "show", "--name-only", "--format=%s", "HEAD~1")
    assert proof_commit.startswith("ENG-1 T1: task proof"), proof_commit
    assert verify_rel in proof_commit and tests_rel not in proof_commit, proof_commit
    assert git(repo, "ls-tree", "--name-only", "HEAD", tests_rel) == tests_rel
    verify = json.loads(git(repo, "show", f"HEAD:{verify_rel}"))
    assert verify["recorded_by"] == "stage-proof" and verify["ok"] is True
    assert [entry["status"] for entry in verify["required_tests"]] == ["passed"]
    tests = json.loads(git(repo, "show", f"HEAD:{tests_rel}"))
    assert tests["automated"]["generated_by"] == "implementer"
    assert "measured" not in tests["automated"], "the worker's record is never edited"


def test_task_close_reuses_the_proof_when_only_bookkeeping_moved(repo, tmp_path):
    """A second close over the same product tree runs no test: the record
    from the first close is the proof."""
    env = _ship_ready(repo, tmp_path)
    write_in_scope(repo, "src/core.py", "version = 2\n")
    git(repo, "add", "src/core.py")
    git(repo, "commit", "-qm", "unreviewed change")
    skill = str(tmp_path / "no-such-autoreview")
    code, out = run(repo, "forge.py", "task", "close", "T1", "--skill", skill, env=env)
    assert code != 0 and "autoreview skill not found" in out, out
    assert "proof reused" not in out
    verify_path = task_evidence_path(repo, "ENG-1", "T1", "verify.json")
    first_verify = verify_path.read_bytes()
    code, out = run(repo, "forge.py", "task", "close", "T1", "--skill", skill, env=env)
    assert code != 0 and "autoreview skill not found" in out, out
    assert "T1: task proof committed" not in out, out
    assert verify_path.read_bytes() == first_verify


def test_task_close_rebinds_a_stale_worker_record_before_the_review(repo, tmp_path):
    """After a fix commit the worker's record names the old commit; the brief
    refused it and the coordinator re-recorded by hand. Close re-binds it when
    it measures the new tree, so the review is reached and the seal follows."""
    from factory_lib import task_evidence_path
    env = _ship_ready(repo, tmp_path)
    tests_path = task_evidence_path(repo, "ENG-1", "T1", "tests.json")
    original = json.loads(tests_path.read_text(encoding="utf-8"))["automated"]["commit"]
    write_in_scope(repo, "src/core.py", "version = 2\n")
    git(repo, "add", "src/core.py")
    git(repo, "commit", "-qm", "fix commit")
    fixed = head(repo)
    skill = tmp_path / "fake-autoreview.py"
    skill.write_text(FAKE_REVIEW_WITH, encoding="utf-8")
    code, out = run(repo, "forge.py", "task", "close", "T1", "--engine", "claude",
                    "--skill", str(skill), env={**env, "FAKE_PRIORITY": "P3"})
    assert "Review brief refused" not in out and "stale commit" not in out, out
    assert code == 0, out
    tests = json.loads(task_evidence_path(
        repo, "ENG-1", "T1", "tests.json").read_text(encoding="utf-8"))
    assert tests["automated"]["commit"] == fixed == tests["commit"]
    assert tests["automated"]["worker_commit"] == original
    assert tests["automated"]["summary"] == "focused task proof passed"
    assert git(repo, "show", "--name-only", "--format=%s", "HEAD~1").startswith(
        "ENG-1 T1: task proof")
