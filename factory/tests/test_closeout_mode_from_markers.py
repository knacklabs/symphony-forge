"""Story closeout tells task-level from story-level by the evidence, not by a
pointer field only task worktrees ever get.

`forge task start` writes `base_main_sha` into the TASK worktree's pointer and
nothing writes it into the story's own. So WF-1, whose five tasks each shipped
as their own PR, was classed story-level at closeout and asked for the
story-wide verify, three-lens review and functional pass that the per-task
flow retired (2026-09-14). A task marker on the trunk, or committed in the
tree, is proof the story ships task by task: a story-level run cannot make one.
"""
from __future__ import annotations

import json

from test_gates import (  # noqa: F401
    configure_origin_main, delegation_ledger, git, prepare_pr_ready_story,
    publish_task_marker, repo, run, task_with_plan_contracts,
)
from factory_lib import (  # noqa: E402
    require_closeout_order, run_is_task_level, task_marker_path,
)

__all__ = ["repo"]


def _two_task_story(repo, tmp_path):
    scoped = prepare_pr_ready_story(repo, tmp_path, scoped_layout=True)
    control = delegation_ledger(repo).parent
    decomposition_path = control / "decomposition.json"
    decomposition = json.loads(decomposition_path.read_text())
    decomposition["tasks"].append({
        **decomposition["tasks"][0], "id": "T2", "title": "second slice",
    })
    decomposition["tasks"] = [
        task_with_plan_contracts(task, prefix=f"{task['id']}-C")
        for task in decomposition["tasks"]
    ]
    decomposition_path.write_text(json.dumps(decomposition))
    (scoped / "decomposition.json").write_text(json.dumps(decomposition))
    configure_origin_main(repo, tmp_path / "closeout-origin.git")
    marker = task_marker_path("ENG-1", "T1")
    git(repo, "rm", "-q", marker)
    git(repo, "commit", "-q", "-m", "start story without T1 marker")
    git(repo, "push", "-q", "origin", "HEAD:main")
    assert not (repo / marker).exists()
    assert not git(repo, "ls-tree", "-r", "--name-only", "origin/main", "--", marker)
    pointer = json.loads((control / "run.json").read_text())
    pointer.pop("base_main_sha", None)
    (control / "run.json").write_text(json.dumps(pointer))
    assert "base_main_sha" not in pointer  # exercise marker-based story classification
    return scoped


def test_a_task_marker_on_the_trunk_makes_the_story_task_level(repo, tmp_path):
    _two_task_story(repo, tmp_path)
    # No marker anywhere yet: nothing says the story ships task by task.
    assert run_is_task_level(repo) is False
    story_level = require_closeout_order(repo)
    assert any("verify" in problem for problem in story_level)

    publish_task_marker(repo, "ENG-1", "T1")
    assert run_is_task_level(repo) is True
    task_level = require_closeout_order(repo)
    # The story-wide chain is no longer asked for; the per-task proof is.
    assert not any(".factory/verify.json" in problem for problem in task_level)
    assert not any("functional" in problem for problem in task_level)
    assert any("T2" in problem for problem in task_level), task_level
    code, out = run(repo, "pr_ready.py")
    assert code != 0, out
    assert "every task must have its committed pr-ready marker on the trunk; missing: T2" in out
    assert "stage completion: T2 not done" in out
    # The story-wide chain is not asked for any more.
    assert "successful .factory/verify.json" not in out
    assert ".factory/tests.json:functional" not in out


def test_a_marker_committed_in_the_tree_counts_before_it_reaches_the_trunk(repo, tmp_path):
    _two_task_story(repo, tmp_path)
    marker = repo / task_marker_path("ENG-1", "T1")
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({
        "task_id": "T1", "branch": "feat/ENG-1-T1",
        "base_main_sha": git(repo, "rev-parse", "origin/main"),
        "commit": git(repo, "rev-parse", "HEAD"),
        "sealed_at": "2026-09-14T00:00:00+00:00",
    }) + "\n")
    git(repo, "add", marker.relative_to(repo).as_posix())
    git(repo, "commit", "-q", "-m", "seal T1")
    assert run_is_task_level(repo) is True


def test_pr_ready_uses_the_fetched_trunk_proof_when_local_checkout_is_old(
        repo, tmp_path):
    prepare_pr_ready_story(repo, tmp_path, scoped_layout=True)
    tests = repo / ".factory/stories/ENG-1/tasks/T1/tests.json"
    payload = json.loads(tests.read_text(encoding="utf-8"))
    payload["automated"]["status"] = "failed"
    tests.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    code, out = run(repo, "pr_ready.py")
    assert code == 0, out
    assert "shipped in place" in out


def test_pr_ready_refuses_proof_changed_on_the_current_trunk(
        repo, tmp_path):
    prepare_pr_ready_story(repo, tmp_path, scoped_layout=True)
    local_head = git(repo, "rev-parse", "HEAD")
    tests = repo / ".factory/stories/ENG-1/tasks/T1/tests.json"
    payload = json.loads(tests.read_text(encoding="utf-8"))
    payload["automated"]["status"] = "failed"
    tests.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    git(repo, "add", tests.relative_to(repo).as_posix())
    git(repo, "commit", "-qm", "tamper current trunk proof")
    git(repo, "push", "-q", "origin", "HEAD:main")
    git(repo, "reset", "--hard", "-q", local_head)

    code, out = run(repo, "pr_ready.py")
    assert code != 0
    assert "committed pr-ready marker on the trunk" in out


def test_the_pointer_field_still_wins_inside_a_task_worktree(repo, tmp_path):
    _two_task_story(repo, tmp_path)
    control = delegation_ledger(repo).parent
    pointer = json.loads((control / "run.json").read_text())
    pointer["base_main_sha"] = git(repo, "rev-parse", "origin/main")
    (control / "run.json").write_text(json.dumps(pointer))
    assert run_is_task_level(repo) is True


def test_reconcile_refuses_active_task_with_scoped_changes_off_trunk(repo, tmp_path):
    from forge_cli.stages import load_stages, write_stages
    from factory_lib import task_proof_problems

    _two_task_story(repo, tmp_path)
    stages = load_stages(repo)
    stages["stages"][0]["status"] = "active"
    write_stages(repo, stages)
    git(repo, "fetch", "origin", "main")
    source = repo / "src" / "core.py"
    shared_task_content = "print('partially merged task work')\n"
    source.write_text(shared_task_content)
    extra_source = repo / "src" / "extra.py"
    extra_source.write_text("print('local work not on trunk')\n")
    git(repo, "add", "src/core.py", "src/extra.py")
    git(repo, "commit", "-qm", "keep scoped work off trunk")

    trunk = tmp_path / "partial-trunk"
    base = git(repo, "rev-parse", "origin/main")
    git(repo, "worktree", "add", "-q", "--detach", str(trunk), base)
    (trunk / "src" / "core.py").write_text(shared_task_content)
    git(trunk, "add", "src/core.py")
    git(trunk, "commit", "-qm", "partially merge task work")
    git(trunk, "push", "-q", "origin", "HEAD:main")
    git(repo, "worktree", "remove", "-f", str(trunk))

    code, out = run(repo, "forge.py", "task", "reconcile", "T1")

    assert code != 0, out
    assert "scoped changes" in out
    marker = repo / task_marker_path("ENG-1", "T1")
    assert not marker.exists()

    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({
        "task_id": "T1",
        "branch": git(repo, "symbolic-ref", "--short", "HEAD"),
        "base_main_sha": base,
        "commit": git(repo, "rev-parse", "HEAD"),
        "sealed_at": "2026-09-23T00:00:00+00:00",
        "reconciled": True,
    }) + "\n")
    git(repo, "add", marker.relative_to(repo).as_posix())
    git(repo, "commit", "-qm", "local reconciled marker with off-trunk work")
    problems = task_proof_problems(repo, "ENG-1", {"id": "T1"})
    assert any("reconciled marker commit is not an ancestor of origin/main" in p
               for p in problems), problems


def test_reconcile_refuses_revert_to_pre_branch_point_content(repo, tmp_path):
    from forge_cli.stages import load_stages, write_stages

    _two_task_story(repo, tmp_path)
    base = git(repo, "rev-parse", "origin/main")
    trunk = tmp_path / "revert-trunk"
    git(repo, "worktree", "add", "-q", "--detach", str(trunk), base)
    source = trunk / "src" / "core.py"
    pre_branch_point_content = "print('pre-branch-point content')\n"
    source.write_text(pre_branch_point_content)
    git(trunk, "add", "src/core.py")
    git(trunk, "commit", "-qm", "record prior scoped content")
    source.write_text("print('branch-point content')\n")
    git(trunk, "add", "src/core.py")
    git(trunk, "commit", "-qm", "advance trunk branch point")
    git(trunk, "push", "-q", "origin", "HEAD:main")
    git(repo, "worktree", "remove", "-f", str(trunk))
    git(repo, "fetch", "origin", "main")
    git(repo, "checkout", "-q", "-b", "feat/ENG-1-T1", "origin/main")

    stages = load_stages(repo)
    stages["stages"][0]["status"] = "active"
    write_stages(repo, stages)
    source = repo / "src" / "core.py"
    source.write_text(pre_branch_point_content)
    git(repo, "add", "src/core.py")
    git(repo, "commit", "-qm", "revert scoped file to prior content")

    code, out = run(repo, "forge.py", "task", "reconcile", "T1")

    assert code != 0, out
    assert "scoped changes" in out
    assert not (repo / task_marker_path("ENG-1", "T1")).exists()


def test_reconcile_accepts_merged_task_with_later_trunk_edit(repo, tmp_path):
    from forge_cli.stages import load_stages, write_stages

    _two_task_story(repo, tmp_path)
    stages = load_stages(repo)
    stages["stages"][0]["status"] = "active"
    write_stages(repo, stages)
    source = repo / "src" / "core.py"
    source.write_text("print('task work')\n")
    git(repo, "add", "src/core.py")
    git(repo, "commit", "-qm", "ship scoped task change")

    trunk = tmp_path / "later-trunk"
    git(repo, "worktree", "add", "-q", "--detach", str(trunk), "HEAD")
    (trunk / "src" / "core.py").write_text("print('later trunk edit')\n")
    git(trunk, "add", "src/core.py")
    git(trunk, "commit", "-qm", "edit scoped file after task merge")
    git(trunk, "push", "-q", "origin", "HEAD:main")
    git(repo, "worktree", "remove", "-f", str(trunk))

    code, out = run(repo, "forge.py", "task", "reconcile", "T1")

    assert code == 0, out


def test_reconcile_accepts_squash_merged_task(repo, tmp_path):
    from forge_cli.stages import load_stages, write_stages

    _two_task_story(repo, tmp_path)
    stages = load_stages(repo)
    stages["stages"][0]["status"] = "active"
    write_stages(repo, stages)
    base = git(repo, "rev-parse", "HEAD")
    task_content = "print('squash merged task work')\n"
    source = repo / "src" / "core.py"
    source.write_text(task_content)
    git(repo, "add", "src/core.py")
    git(repo, "commit", "-qm", "task scoped change")

    trunk = tmp_path / "squash-trunk"
    git(repo, "worktree", "add", "-q", "--detach", str(trunk), base)
    (trunk / "src" / "core.py").write_text(task_content)
    git(trunk, "add", "src/core.py")
    git(trunk, "commit", "-qm", "squash merge task scoped change")
    git(trunk, "push", "-q", "origin", "HEAD:main")
    git(repo, "worktree", "remove", "-f", str(trunk))

    code, out = run(repo, "forge.py", "task", "reconcile", "T1")

    assert code == 0, out


def test_reconcile_refuses_active_task_with_empty_write_scope(repo, tmp_path):
    from factory_lib import protected_decomposition_state_path
    from forge_cli.stages import load_stages, write_stages

    _two_task_story(repo, tmp_path)
    stages = load_stages(repo)
    stages["stages"][0]["status"] = "active"
    write_stages(repo, stages)
    decomposition_path = protected_decomposition_state_path(repo)
    decomposition = json.loads(decomposition_path.read_text())
    decomposition["tasks"][0]["write_scope"] = []
    decomposition_path.write_text(json.dumps(decomposition))

    code, out = run(repo, "forge.py", "task", "reconcile", "T1")

    assert code != 0, out
    assert "has no write_scope" in out
    assert not (repo / task_marker_path("ENG-1", "T1")).exists()


def test_an_adopted_marker_closes_without_proof_and_readopt_makes_one(repo, tmp_path):
    """The PR gate and the frontier already accept a `reconciled` marker without
    proof; closeout must agree, or a story of adopted tasks never closes. And a
    task whose trunk marker is real but whose proof predates the current
    predicate (WF-1 after the review-generation change) is re-adopted with
    `forge task reconcile --readopt`, reason on the timeline."""
    from test_gates import fake_gh_env, story_state
    from factory_lib import task_proof_problems
    from forge_cli.events import load_events
    _two_task_story(repo, tmp_path)
    git(repo, "config", "user.email", "test@knacklabs.dev")
    git(repo, "config", "user.name", "Gate Tests")
    tasks = json.loads((delegation_ledger(repo).parent / "decomposition.json").read_text())["tasks"]
    t1 = next(t for t in tasks if t["id"] == "T1")
    publish_task_marker(repo, "ENG-1", "T1")           # a real marker on the trunk ...
    marker = story_state(repo) / "tasks" / "T1" / "pr-ready.json"
    payload = json.loads(marker.read_text())
    payload.pop("reconciled")                           # ... sealed, not adopted
    marker.write_text(json.dumps(payload) + "\n")
    git(repo, "add", marker.relative_to(repo).as_posix())
    git(repo, "commit", "-q", "-m", "seal T1")
    git(repo, "push", "-q", "origin", "HEAD:main")
    assert any("T1" in p for p in task_proof_problems(repo, "ENG-1", t1))

    readopt_gh = tmp_path / "readopt-gh"
    readopt_gh.mkdir()
    gh_env, _argv = fake_gh_env(readopt_gh)
    code, out = run(repo, "forge.py", "task", "reconcile", "T1", "--readopt", "short",
                    env=gh_env)
    assert code != 0 and "a dozen characters" in out, out
    code, out = run(repo, "forge.py", "task", "reconcile", "T1",
                    "--readopt", "proof predates the review-generation format", env=gh_env)
    assert code == 0, out
    readopted = json.loads(marker.read_text())
    assert readopted == {**payload, "reconciled": True}  # identity untouched
    assert marker.relative_to(repo).as_posix() in git(
        repo, "show", "--name-only", "--format=", "HEAD")
    assert "re-adopted" in git(repo, "log", "-1", "--format=%s")
    assert any("re-adopted: proof predates" in str(e.get("detail", ""))
               for e in load_events(repo) if e.get("event") == "stage-reconciled")
    git(repo, "push", "-q", "origin", "HEAD:main")
    # Committed and adopted: closeout asks this task for no proof at all.
    assert task_proof_problems(repo, "ENG-1", t1) == []
    closeout = require_closeout_order(repo)
    assert any("T2 not done" in p for p in closeout), closeout
    assert not any("T1" in p for p in closeout), "\n".join(closeout)
