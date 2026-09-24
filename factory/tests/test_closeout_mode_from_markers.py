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


def test_reconcile_refuses_other_tasks_scoped_commit_on_trunk(repo, tmp_path):
    from forge_cli.stages import load_stages, write_stages

    _two_task_story(repo, tmp_path)
    base = git(repo, "rev-parse", "HEAD")
    stages = load_stages(repo)
    stages["stages"][0]["status"] = "active"
    stages["stages"][0]["base_sha"] = base
    write_stages(repo, stages)

    trunk = tmp_path / "reconcile-unrelated-trunk"
    git(repo, "worktree", "add", "-q", "--detach", str(trunk), base)
    (trunk / "src" / "unrelated.py").write_text("print('T2 trunk work')\n")
    git(trunk, "add", "src/unrelated.py")
    git(trunk, "commit", "-q", "-m", "ship T2 scoped work",
        "-m", "Ticket: ENG-1/T2")
    git(trunk, "push", "-q", "origin", "HEAD:main")
    git(repo, "worktree", "remove", "-f", str(trunk))
    git(repo, "merge", "--ff-only", "origin/main")

    code, out = run(repo, "forge.py", "task", "reconcile", "T1")

    assert code != 0 and (
        "no scoped commit in" in out and "Ticket: ENG-1/T1" in out
    ), out
    assert not (repo / task_marker_path("ENG-1", "T1")).exists()


def test_reconcile_refuses_branch_behind_declared_trunk_commit(repo, tmp_path):
    from forge_cli.stages import load_stages, write_stages

    _two_task_story(repo, tmp_path)
    base = git(repo, "rev-parse", "HEAD")
    stages = load_stages(repo)
    stages["stages"][0]["status"] = "active"
    stages["stages"][0]["base_sha"] = base
    write_stages(repo, stages)

    trunk = tmp_path / "declared-trunk"
    git(repo, "worktree", "add", "-q", "--detach", str(trunk), base)
    (trunk / "src" / "core.py").write_text("print('squash merged task work')\n")
    git(trunk, "add", "src/core.py")
    git(trunk, "commit", "-q", "-m", "squash merge task scoped change",
        "-m", "Ticket: ENG-1/T1")
    git(trunk, "push", "-q", "origin", "HEAD:main")
    git(repo, "worktree", "remove", "-f", str(trunk))

    code, out = run(repo, "forge.py", "task", "reconcile", "T1")

    assert code != 0 and "merge origin/main into this branch first" in out, out


def test_reconcile_refuses_later_local_scoped_commit(repo, tmp_path):
    from forge_cli.stages import load_stages, write_stages

    _two_task_story(repo, tmp_path)
    git(repo, "config", "user.email", "test@knacklabs.dev")
    git(repo, "config", "user.name", "Gate Tests")
    base = git(repo, "rev-parse", "HEAD")
    stages = load_stages(repo)
    stages["stages"][0]["status"] = "active"
    stages["stages"][0]["base_sha"] = base
    write_stages(repo, stages)

    source = repo / "src" / "core.py"
    source.write_text("print('task work shipped')\n")
    git(repo, "add", "src/core.py")
    git(repo, "commit", "-q", "-m", "ship T1 scoped work",
        "-m", "Ticket: ENG-1/T1")
    git(repo, "push", "-q", "origin", "HEAD:main")
    source.write_text("print('later local scoped work')\n")
    git(repo, "add", "src/core.py")
    git(repo, "commit", "-q", "-m", "later local scoped work")

    code, out = run(repo, "forge.py", "task", "reconcile", "T1")

    assert code != 0 and "committed scoped changes" in out, out
    assert not (repo / task_marker_path("ENG-1", "T1")).exists()


def test_reconcile_accepts_squash_commit_and_marker_passes_pr_gate(
        repo, tmp_path):
    from forge_cli.stages import load_stages, write_stages

    _two_task_story(repo, tmp_path)
    base = git(repo, "rev-parse", "HEAD")
    stages = load_stages(repo)
    stages["stages"][0]["status"] = "active"
    stages["stages"][0]["base_sha"] = base
    write_stages(repo, stages)
    task_content = "print('squash merged task work')\n"
    trunk = tmp_path / "squash-trunk"
    git(repo, "worktree", "add", "-q", "--detach", str(trunk), base)
    source = trunk / "src" / "core.py"
    source.write_text(task_content)
    git(trunk, "add", "src/core.py")
    git(trunk, "commit", "-q", "-m", "squash merge task scoped change",
        "-m", "Ticket: ENG-1/T1")
    task_commit = git(trunk, "rev-parse", "HEAD")
    later_doc = trunk / "docs" / "after-task.md"
    later_doc.parent.mkdir(parents=True, exist_ok=True)
    later_doc.write_text("unrelated trunk update\n")
    git(trunk, "add", "docs/after-task.md")
    git(trunk, "commit", "-qm", "unrelated trunk update after task shipped")
    git(trunk, "push", "-q", "origin", "HEAD:main")
    git(repo, "worktree", "remove", "-f", str(trunk))
    git(repo, "merge", "--ff-only", "origin/main")

    code, out = run(repo, "forge.py", "task", "reconcile", "T1",
                    "--commit", base)

    assert code != 0 and "--commit must be one of this task's declared" in out
    assert not (repo / task_marker_path("ENG-1", "T1")).exists()

    code, out = run(repo, "forge.py", "task", "reconcile", "T1",
                    "--commit", task_commit)

    assert code == 0, out
    marker = json.loads((repo / task_marker_path("ENG-1", "T1")).read_text())
    assert marker["commit"] == task_commit
    trunk_tip = git(repo, "rev-parse", "origin/main")
    assert trunk_tip != task_commit
    pr_base = git(repo, "merge-base", "origin/main", "HEAD")
    assert pr_base == trunk_tip
    code, out = run(repo, "check_task_proof.py", "--base", pr_base)
    assert code == 0, out


def test_reconcile_accepts_commit_only_in_amended_scope(repo, tmp_path):
    from forge_cli.stages import load_stages, scope_amendments_path, write_stages

    _two_task_story(repo, tmp_path)
    base = git(repo, "rev-parse", "HEAD")
    stages = load_stages(repo)
    stages["stages"][0]["status"] = "active"
    stages["stages"][0]["base_sha"] = base
    write_stages(repo, stages)
    amendments = scope_amendments_path(repo)
    amendments.parent.mkdir(parents=True, exist_ok=True)
    amendments.write_text(json.dumps({"tasks": {"T1": {
        "added_paths": ["tests/added_scope.py"],
        "amendments": [{"reason": "measured task work",
                        "added_paths": ["tests/added_scope.py"]}],
    }}}))
    added = repo / "tests" / "added_scope.py"
    added.parent.mkdir(parents=True, exist_ok=True)
    added.write_text("print('task work in the amended scope')\n")
    git(repo, "add", "tests/added_scope.py")
    git(repo, "commit", "-q", "-m", "task change in amended scope",
        "-m", "Ticket: ENG-1/T1")
    task_commit = git(repo, "rev-parse", "HEAD")
    git(repo, "push", "-q", "origin", "HEAD:main")

    code, out = run(repo, "forge.py", "task", "reconcile", "T1")

    assert code == 0, out
    marker = json.loads((repo / task_marker_path("ENG-1", "T1")).read_text())
    assert marker["commit"] == task_commit


def test_reconcile_refuses_uncommitted_scoped_edit(repo, tmp_path):
    from forge_cli.stages import load_stages, write_stages

    _two_task_story(repo, tmp_path)
    base = git(repo, "rev-parse", "HEAD")
    stages = load_stages(repo)
    stages["stages"][0]["status"] = "active"
    stages["stages"][0]["base_sha"] = base
    write_stages(repo, stages)
    source = repo / "src" / "core.py"
    source.write_text("print('committed task work')\n")
    git(repo, "add", "src/core.py")
    git(repo, "commit", "-q", "-m", "task scoped change",
        "-m", "Ticket: ENG-1/T1")
    git(repo, "push", "-q", "origin", "HEAD:main")
    source.write_text("print('uncommitted scoped edit')\n")
    (repo / "src" / "untracked.py").write_text("print('untracked scoped edit')\n")

    code, out = run(repo, "forge.py", "task", "reconcile", "T1")

    assert code != 0 and "uncommitted changes in the task's scope" in out, out
    assert not (repo / task_marker_path("ENG-1", "T1")).exists()


def test_reconcile_refuses_when_task_has_no_own_scoped_commits(
        repo, tmp_path):
    from forge_cli.stages import load_stages, write_stages

    _two_task_story(repo, tmp_path)
    stages = load_stages(repo)
    stages["stages"][0]["status"] = "active"
    stages["stages"][0]["base_sha"] = git(repo, "rev-parse", "HEAD")
    write_stages(repo, stages)

    code, out = run(repo, "forge.py", "task", "reconcile", "T1")

    assert code != 0 and (
        "no scoped commit in" in out and "Ticket: ENG-1/T1" in out
    ), out
    assert not (repo / task_marker_path("ENG-1", "T1")).exists()


def test_reconcile_refuses_when_recorded_stage_base_is_missing(repo, tmp_path):
    from forge_cli.stages import load_stages, write_stages

    _two_task_story(repo, tmp_path)
    stages = load_stages(repo)
    stages["stages"][0]["status"] = "active"
    stages["stages"][0].pop("base_sha", None)
    write_stages(repo, stages)

    code, out = run(repo, "forge.py", "task", "reconcile", "T1")

    assert code != 0 and (
        "T1 has no recorded stage base commit" in out
    ), out
    assert not (repo / task_marker_path("ENG-1", "T1")).exists()


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
    assert "has no effective write_scope" in out
    assert not (repo / task_marker_path("ENG-1", "T1")).exists()


def test_ci_task_proof_reconciled_marker_rejects_product_changes(repo):
    git(repo, "checkout", "-qb", "feat/reconciled-marker-product")
    base = git(repo, "rev-parse", "HEAD")
    marker = (repo / ".factory" / "stories" / "ENG-1" / "tasks" / "T1"
              / "pr-ready.json")
    marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps({"reconciled": True, "commit": base}))
    product = repo / "src" / "reconciled-bypass.py"
    product.parent.mkdir(exist_ok=True)
    product.write_text("bypassed = True\n")
    git(repo, "add", marker.relative_to(repo).as_posix(),
        product.relative_to(repo).as_posix())
    git(repo, "commit", "-qm", "add reconciled marker with product change")

    code, out = run(repo, "check_task_proof.py", "--base", base)

    assert code == 1, out


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
    from forge_cli.stages import load_stages, write_stages
    stages = load_stages(repo)
    stages["stages"][0]["status"] = "active"
    stages["stages"][0]["base_sha"] = git(repo, "rev-parse", "HEAD")
    write_stages(repo, stages)
    source = repo / "src" / "core.py"
    source.write_text("print('T1 work shipped before adoption')\n")
    git(repo, "add", "src/core.py")
    git(repo, "commit", "-q", "-m", "ship T1 scoped work",
        "-m", "Ticket: ENG-1/T1")
    git(repo, "push", "-q", "origin", "HEAD:main")
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


def test_reconcile_readopts_trunk_marker_without_recorded_stage_base(repo, tmp_path):
    from forge_cli.stages import load_stages, write_stages

    _two_task_story(repo, tmp_path)
    git(repo, "config", "user.email", "test@knacklabs.dev")
    git(repo, "config", "user.name", "Gate Tests")
    base = git(repo, "rev-parse", "HEAD")
    stages = load_stages(repo)
    stages["stages"][0]["status"] = "active"
    stages["stages"][0].pop("base_sha", None)
    write_stages(repo, stages)

    source = repo / "src" / "core.py"
    source.write_text("print('T1 work shipped')\n")
    git(repo, "add", "src/core.py")
    git(repo, "commit", "-q", "-m", "ship T1 scoped work",
        "-m", "Ticket: ENG-1/T1")
    task_commit = git(repo, "rev-parse", "HEAD")
    git(repo, "push", "-q", "origin", "HEAD:main")

    marker = repo / task_marker_path("ENG-1", "T1")
    marker.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "task_id": "T1",
        "branch": "feat/ENG-1-T1",
        "base_main_sha": base,
        "commit": task_commit,
        "sealed_at": "2026-09-24T00:00:00+00:00",
    }
    marker.write_text(json.dumps(payload) + "\n")
    git(repo, "add", marker.relative_to(repo).as_posix())
    git(repo, "commit", "-q", "-m", "seal T1")
    git(repo, "push", "-q", "origin", "HEAD:main")

    code, out = run(repo, "forge.py", "task", "reconcile", "T1", "--readopt",
                    "reconcile shipped marker after proof refresh")

    assert code == 0, out
    assert json.loads(marker.read_text()) == {**payload, "reconciled": True}
