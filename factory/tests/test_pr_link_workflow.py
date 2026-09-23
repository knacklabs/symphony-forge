from __future__ import annotations

import json
import subprocess
import sys

from test_gates import HARNESS

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from check_board_complete import board_problems  # noqa: E402


def _workflow() -> str:
    return (HARNESS / ".github/workflows/pr-link.yml").read_text(encoding="utf-8")


def test_pr_link_workflow_stages_per_event_files_not_legacy_jsonl():
    text = _workflow()
    assert "git add -f .factory/events/" in text
    assert "git add -f .factory/events.jsonl" not in text
    assert "head_repository.full_name == github.repository" in text
    assert "workflow_run.event == 'pull_request'" in text


def test_pr_link_workflow_status_description_names_per_event_link_commit():
    text = _workflow()
    assert "link commit touches only per-event .factory/events/" in text
    assert "events.jsonl" not in text
    assert "context=scaffold-check" in text


def test_verified_forge_acc3_and_cfs1_pr_links_make_board_complete():
    expected = {
        ".factory/events/3679bb571b304025956aa2f6ac141e9d.json": {
            "event": "pr-linked", "generated_by": "orchestrator",
            "at": "2026-09-14T04:10:40+00:00", "story": "FORGE-CFS-1",
            "detail": "knacklabs/symphony-forge#109",
        },
        ".factory/events/31d5e07187fb4d9fab0a47009e90331b.json": {
            "event": "pr-linked", "generated_by": "orchestrator",
            "at": "2026-09-14T04:10:40+00:00", "story": "FORGE-ACC-3",
            "detail": "knacklabs/symphony-forge#110",
        },
    }
    merges = {
        "8f1d0530b29083c4b7a0978bebb86fd9b0e1f23c":
            "FORGE-CFS-1: conflict-free story state — overlapping PRs stop colliding on .factory (#109)",
        "6320c1a6e67ba0614ee960f57baf3605811b0d86":
            "FORGE-ACC-3: approval and closeout integrity (+ 0047 task-level shipping) (#110)",
    }
    for commit, subject in merges.items():
        assert subprocess.run(
            ["git", "log", "-1", "--format=%s", commit], cwd=HARNESS,
            capture_output=True, text=True, check=True,
        ).stdout.strip() == subject
    # Anchor on the commit in this branch's own history that added each link,
    # never a feature-branch commit a squash merge leaves unreachable.
    recorders = set()
    for path, payload in expected.items():
        recorder_commit = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%H", "-1", "--", path],
            cwd=HARNESS, capture_output=True, text=True, check=True,
        ).stdout.strip()
        assert recorder_commit, path
        recorders.add(recorder_commit)
        recorded = subprocess.run(
            ["git", "show", f"{recorder_commit}:{path}"], cwd=HARNESS,
            capture_output=True, text=True, check=True,
        ).stdout
        assert json.loads(recorded) == payload
        assert json.loads((HARNESS / path).read_text(encoding="utf-8")) == payload
    # Both links were backfilled together, and that delta adds no other link
    # for these two stories.
    assert len(recorders) == 1
    recorder_commit = recorders.pop()
    changed_paths = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r",
         f"{recorder_commit}^", recorder_commit, "--", ".factory/events/"],
        cwd=HARNESS, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    stories = {payload["story"] for payload in expected.values()}
    backfilled = [
        event for event in (
            json.loads(subprocess.run(
                ["git", "show", f"{recorder_commit}:{path}"], cwd=HARNESS,
                capture_output=True, text=True, check=True,
            ).stdout)
            for path in changed_paths
        )
        if event.get("event") == "pr-linked" and event.get("story") in stories
    ]
    assert sorted(backfilled, key=lambda row: row["story"]) == sorted(
        expected.values(), key=lambda row: row["story"])
    legacy = (HARNESS / ".factory/events.jsonl").read_text(encoding="utf-8")
    assert not any(
        json.loads(line) in expected.values()
        for line in legacy.splitlines() if line.strip()
    )
    problems = board_problems(HARNESS)
    stories = {payload["story"] for payload in expected.values()}
    assert not any(story in problem for story in stories for problem in problems)
