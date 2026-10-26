"""Busy views keep their output and finish within the interactive time budget.

Audit: the public commands own this performance contract. Many retained branch
copies of long-lived fixes expose repeated work over identical state. Existing
Git-call caps cannot detect that CPU cost. This uses real Git and needs no
production test seam. Only GitHub is replaced at its external boundary.
"""
import json
import os
import time
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from test_machine_views_recent_finished_items import NOW, client, finished_fix, landed
from test_board_counts import github

STORY = "the-busy-repo-takes-about-8-seconds-for"


def failed_attempt(gh, attempt, test):
    gh.respond("api", "repos/{owner}/{repo}/actions/runs", stdout=json.dumps({"workflow_runs": [{
        "id": 7, "run_attempt": attempt, "workflow_id": 1, "name": "Nightly",
        "conclusion": "failure", "path": ".github/workflows/nightly.yml"}]}))
    gh.respond("run", "view", "7", "--log-failed",
               stdout=f"Linux\tTests\tx FAILED tests/test_example.py::{test} - broken")


@pytest.mark.platform
@pytest.mark.parametrize("history,command", [
    ("new", "next"), ("new", "next-json"), ("new", "board"), ("adopted-v1.2.2", "board")])
def test_1_busy_views_finish_within_five_seconds(repo, gh, monkeypatch, history, command):
    client(repo, gh, history)
    monkeypatch.setenv("FORGE_NOW", NOW)
    steps = [{"step": "worker round", "at": NOW} for _ in range(500)]
    files = {f".factory/fixes/saved-{n}.json": {
        **finished_fix(f"saved-{n}"), "steps": steps} for n in range(1200)}
    if command != "next":
        # Independent elapsed-time facts prove that reused completed rows still
        # read changed local inputs, not just a changed title outside the time record.
        began = (datetime.fromisoformat(NOW) - timedelta(seconds=10)).isoformat()
        files[".factory/fixes/saved-0.json"]["steps"] = [*steps, {"step": "start", "at": began}]
        github(SimpleNamespace(repo=repo, gh=gh), [{"headRefName": "fix/saved-0",
               "state": "MERGED", "mergedAt": NOW,
               "files": [{"path": ".factory/fixes/saved-0.json"}]}])
    landed(repo, monkeypatch, NOW, files)
    repo.git("push", "-q", "origin", *(
        f"HEAD:refs/heads/fix/saved-{n}" for n in range(80)))
    repo.git("fetch", "-q", "origin")
    repo.git("switch", "-qc", "fix/saved-0")
    # Audit: time the first read and a refresh, not only primed caches. Completed
    # attempt logs cannot change; downloading one again delays the same answer.
    # Existing lifetime coverage has no failed run. Only GitHub is faked here.
    if command == "next":
        failed_attempt(gh, 1, "test_old")
        gh.respond("api", "repos/{owner}/{repo}/actions/workflows/forge.yml/runs",
                   stdout='{"workflow_runs": []}')
    args = ["next"] if command == "next" else [command.removesuffix("-json"), "--json"]
    start = time.monotonic()
    first = repo.forge(*args, timeout=120)
    first_elapsed = time.monotonic() - start
    assert first.returncode == 0, first.stderr
    changed = {**files[".factory/fixes/saved-0.json"], "why": "Current local title"}
    if command != "next":
        assert next(row for row in json.loads(first.stdout)["items"] if row["id"] == "saved-0")["total_seconds"] == 10
        changed["steps"] = [*steps, {"step": "start", "at": (
            datetime.fromisoformat(NOW) - timedelta(seconds=20)).isoformat()}]
    repo.write(".factory/fixes/saved-0.json", json.dumps(changed))
    monkeypatch.setenv("FORGE_NOW", (datetime.fromisoformat(NOW) + timedelta(seconds=601)).isoformat())
    start = time.monotonic()
    result = repo.forge(*args, timeout=120)
    elapsed = time.monotonic() - start
    assert result.returncode == 0, result.stderr
    if command == "next":
        assert result.stdout == first.stdout
        assert "Next: forge close saved-0" in result.stdout
        assert "tests/test_example.py::test_old" in result.stdout
        assert sum(call[:3] == ["run", "view", "7"] for call in gh.calls()) == 1
        # A rerun keeps the run id but has new logs. It must not reuse attempt one's failures.
        monkeypatch.setenv("FORGE_NOW", (datetime.fromisoformat(NOW) + timedelta(seconds=1202)).isoformat())
        failed_attempt(gh, 2, "test_retry")
        retried = repo.forge(*args, timeout=120)
        assert retried.returncode == 0, retried.stderr
        assert "tests/test_example.py::test_retry" in retried.stdout
        assert "tests/test_example.py::test_old" not in retried.stdout
    else:
        rows = {row["id"]: row for row in json.loads(result.stdout)["items"]}
        assert len([key for key in rows if key.startswith("saved-")]) == 1200
        assert rows["saved-0"]["title"] == "Current local title"
        assert rows["saved-0"]["total_seconds"] == 20
        assert rows["saved-1199"]["stage"] == "merged"
    # Windows process and filesystem costs have a separate platform allowance.
    budget = 30 if os.name == "nt" else 5
    assert first_elapsed < budget, f"cold {command} took {first_elapsed:.2f}s (budget {budget}s)"
    assert elapsed < budget, f"{command} took {elapsed:.2f}s (budget {budget}s)"
