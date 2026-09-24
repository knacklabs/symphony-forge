"""Decision 0090: one human approval per story."""
from __future__ import annotations

import json
from pathlib import Path

from test_gates import (  # noqa: F401
    DECOMP, STAGE_TASK, _fake_psutil_module, fake_companion_env, git, intake, load_factory_lib,
    native_claude_approval, plan_draft, post_hook, record_grill,
    record_skeleton_then_frontier, record_task_grill, repo, run, save_plan,
    sign_off, story_state, task_skeleton,
)


def test_task_cold_read_opens_stage_without_task_approval(repo: Path, tmp_path):
    sign_off(repo)
    intake(repo)
    assert save_plan(repo, tmp_path)[0] == 0
    record_skeleton_then_frontier(repo, [STAGE_TASK])
    assert record_task_grill(repo, STAGE_TASK)[0] == 0
    lib = load_factory_lib(repo)
    assert lib.task_frontier_state(repo)[0] == "stage-start"
    code, out = run(repo, "forge.py", "next")
    assert code == 0, out
    assert "cold-grilled T1 plan is ready" not in out
    assert "final bytes in native Plan Mode" not in out
    code, out = run(repo, "forge.py", "stage", "start", "T1", "--trunk")
    assert code == 0, out
    code, out = run(repo, "forge.py", "delegate", "T1",
                    env={**fake_companion_env(tmp_path),
                         "PYTHONPATH": str(_fake_psutil_module(tmp_path))})
    assert code == 0, out


def test_delivery_preserving_story_amendment_rebinds_graph(repo: Path, tmp_path):
    sign_off(repo)
    intake(repo)
    body = "\n\n".join(
        f"## {name}\nTest content for {name}." for name in (
            "What and why", "What changes for you", "Done when", "Risks",
            "Technical approach", "Task decomposition", "Verify plan",
        )) + "\n"
    draft = tmp_path / "plan.md"
    draft.write_text(plan_draft(repo, body), encoding="utf-8")
    record_grill(repo, "plan", digest_of=draft)
    assert run(repo, "forge.py", "plan", "save", "--from", str(draft),
               "--story", "ENG-1")[0] == 0
    assert post_hook(repo, native_claude_approval(repo))[0] == 0
    record_skeleton_then_frontier(repo, [STAGE_TASK])
    lib = load_factory_lib(repo)
    plan = repo / lib.load_json(lib.run_state_path(repo))["plan_file"]
    before = plan.read_text(encoding="utf-8")
    plan.write_text(before.replace("## Technical approach", "## Technical approach\n\nReorder tasks."), encoding="utf-8")
    digest = lib.require_approved_plan_digest(repo)
    assert digest == lib.plan_digest_without_assumptions(plan)
    assert lib.load_json(story_state(repo) / "plan-approval.json")["carried_forward_reason"]
    code, out = run(repo, "record_decomposition_from_json.py",
                    stdin=json.dumps({**DECOMP, "tasks": [STAGE_TASK,
                        task_skeleton({**STAGE_TASK, "id": "T2", "title": "Second task"})]}))
    assert code == 0, out
    plan.write_text(plan.read_text(encoding="utf-8").replace("## Done when", "## Done when\n\nNew delivery."), encoding="utf-8")
    try:
        lib.require_approved_plan_digest(repo)
    except SystemExit as exc:
        assert "native Plan Mode" in str(exc)
    else:
        raise AssertionError("delivery edit must require native approval")


def test_grill_tree_uses_declared_scope(repo: Path):
    lib = load_factory_lib(repo)
    plan = repo / "plans" / "active" / "TEST-1-test-plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("# Plan\n", encoding="utf-8")
    control = Path(git(repo, "rev-parse", "--absolute-git-dir")) / "forge"
    control.mkdir(parents=True, exist_ok=True)
    lib.dump_json(control / "run.json", {"plan_file": plan.relative_to(repo).as_posix()})
    task = {"id": "T1", "write_scope": ["src/"]}
    before = lib.grounding_digest(repo, task)
    grill = {"input_sha256": before}
    other = repo / "docs" / "specs" / "other.md"
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_text("changed\n", encoding="utf-8")
    git(repo, "add", other.relative_to(repo).as_posix())
    assert lib.task_grill_grounding_matches(repo, task, grill)
    own = repo / "src" / "main.py"
    own.parent.mkdir(parents=True, exist_ok=True)
    own.write_text("changed\n", encoding="utf-8")
    git(repo, "add", own.relative_to(repo).as_posix())
    assert not lib.task_grill_grounding_matches(repo, task, grill)
