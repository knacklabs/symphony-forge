from __future__ import annotations

import hashlib
import json
from pathlib import Path

from test_gates import (
    DECOMP, configure_origin_main, git, head, intake, repo, run, run_state,
    save_plan, seed_task_start_inputs, sign_off, story_state,
)


def _launch_row(launch_id: str, status: str) -> dict:
    return {
        "generated_by": "orchestrator",
        "at": "2026-09-25T00:00:00+00:00",
        "launch_id": launch_id,
        "task": "grill-plan",
        "brief_sha256": "a" * 64,
        "task_sha256": "b" * 64,
        "write": False,
        "model": "gpt-test",
        "effort": "medium",
        "argv": [],
        "argv_sha256": hashlib.sha256(b"[]").hexdigest(),
        "launch_status": status,
        "transport": "host-native",
    }


def _add_worktree(repo: Path, path: Path, branch: str) -> None:
    git(repo, "worktree", "add", "-b", branch, str(path), head(repo))


def _add_plan_note(plan: Path) -> bytes:
    content = plan.read_text(encoding="utf-8")
    updated = "---\nsaved: after-merge\n---\n" + content
    plan.write_text(updated, encoding="utf-8")
    return plan.read_bytes()


def test_delegation_ledger_is_shared_and_reads_legacy_worktree_rows(
        repo, tmp_path,
):
    from forge_cli.delegate import append_delegation, delegations_path, load_delegations

    planning = tmp_path / "planning"
    task = tmp_path / "task"
    _add_worktree(repo, planning, "planning")
    _add_worktree(repo, task, "task")

    assert delegations_path(planning) == delegations_path(task)
    assert append_delegation(planning, _launch_row("cold-read", "prepared"))
    assert append_delegation(task, _launch_row("cold-read", "succeeded"))

    rows = load_delegations(task)
    assert [row["worktree"] for row in rows] == [
        str(planning.resolve()), str(task.resolve()),
    ]

    legacy = Path(git(planning, "rev-parse", "--absolute-git-dir")) \
        / "forge" / "delegations.jsonl"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(json.dumps({"launch_id": "legacy-planning-row"}) + "\n")
    assert any(row.get("launch_id") == "legacy-planning-row"
               for row in load_delegations(task))


def test_task_start_copies_updated_plan_and_whole_story_records(repo, tmp_path):
    remote = tmp_path / "origin.git"
    sign_off(repo)
    assert intake(repo, "ENG-1")[0] == 0
    assert save_plan(repo, tmp_path)[0] == 0
    configure_origin_main(repo, remote)

    task = {**DECOMP["tasks"][0], "id": "T1", "title": "first"}
    sources = seed_task_start_inputs(repo, "ENG-1", [task], "T1")
    expected_plan = _add_plan_note(sources["plan"])
    extra = story_state(repo) / "approval-events" / "post-merge-note.json"
    extra.write_text('{"from":"planning checkout"}\n', encoding="utf-8")

    code, out = run(repo, "forge.py", "task", "start", "T1")
    assert code == 0, out

    worktree = repo.parent / f"{repo.name}-ENG-1-T1"
    assert (worktree / sources["plan"].relative_to(repo)).read_bytes() == expected_plan
    target_state = story_state(worktree)
    assert (target_state / "grills/tasks/T1.json").read_bytes() == sources["grill"].read_bytes()
    assert (target_state / "approval-events/post-merge-note.json").read_bytes() == extra.read_bytes()
    assert (target_state / "task-plans/T1.md").read_bytes() == sources["task_plan"].read_bytes()


def test_task_start_moves_squash_merged_checkout_and_keeps_records(repo, tmp_path):
    remote = tmp_path / "origin.git"
    sign_off(repo)
    assert intake(repo, "ENG-1")[0] == 0
    assert save_plan(repo, tmp_path)[0] == 0
    configure_origin_main(repo, remote)

    plan = repo / run_state(repo)["plan_file"]
    git(repo, "switch", "-c", "planning")
    git(repo, "add", "-f", plan.relative_to(repo).as_posix())
    git(repo, "config", "user.email", "test@knacklabs.dev")
    git(repo, "config", "user.name", "Gate Tests")
    git(repo, "commit", "-q", "-m", "planning PR")
    planning_head = head(repo)
    tree = git(repo, "rev-parse", f"{planning_head}^{{tree}}")
    main = git(repo, "rev-parse", "refs/remotes/origin/main")
    squash = git(repo, "commit-tree", tree, "-p", main,
                 "-m", "squash merged planning PR")
    git(repo, "push", "-q", "origin", f"{squash}:refs/heads/main")

    task = {**DECOMP["tasks"][0], "id": "T1", "title": "first"}
    sources = seed_task_start_inputs(repo, "ENG-1", [task], "T1")
    expected_plan = _add_plan_note(sources["plan"])
    grill = sources["grill"]
    grill.write_text('{"verdict":"pass","revision":"latest"}\n', encoding="utf-8")

    code, out = run(repo, "forge.py", "task", "start", "T1")
    assert code == 0, out
    assert head(repo) == squash
    assert git(repo, "branch", "--show-current") == "planning"
    assert plan.read_bytes() == expected_plan
    assert grill.read_text(encoding="utf-8").find("latest") != -1
    assert git(repo, "status", "--short", "--", plan.relative_to(repo).as_posix())
