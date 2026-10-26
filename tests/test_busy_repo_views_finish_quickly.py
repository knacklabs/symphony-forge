"""Busy views keep their output and finish within the interactive time budget.

Audit: the public commands own this performance contract. Many retained branch
copies of long-lived fixes expose repeated work over identical state. Existing
Git-call caps cannot detect that CPU cost. This uses real Git and needs no
production test seam. Only GitHub is replaced at its external boundary.
"""
import json
import os
import time

import pytest

from test_machine_views_recent_finished_items import NOW, client, finished_fix, landed

STORY = "the-busy-repo-takes-about-8-seconds-for"


@pytest.mark.platform
@pytest.mark.parametrize("history,command", [
    ("new", "next"), ("new", "next-json"), ("new", "board"), ("adopted-v1.2.2", "board")])
def test_1_busy_views_finish_within_five_seconds(repo, gh, monkeypatch, history, command):
    client(repo, gh, history)
    monkeypatch.setenv("FORGE_NOW", NOW)
    steps = [{"step": "worker round", "at": NOW} for _ in range(500)]
    files = {f".factory/fixes/saved-{n}.json": {
        **finished_fix(f"saved-{n}"), "steps": steps} for n in range(1200)}
    landed(repo, monkeypatch, NOW, files)
    repo.git("push", "-q", "origin", *(
        f"HEAD:refs/heads/fix/saved-{n}" for n in range(80)))
    repo.git("fetch", "-q", "origin")
    repo.git("switch", "-qc", "fix/saved-0")
    # Prime external caches separately. The measured view still derives all
    # current repository facts, including the changed title below.
    args = ["next"] if command == "next" else [command.removesuffix("-json"), "--json"]
    first = repo.forge(*args, timeout=120)
    assert first.returncode == 0, first.stderr
    repo.write(".factory/fixes/saved-0.json", json.dumps({
        **files[".factory/fixes/saved-0.json"], "why": "Current local title"}))
    start = time.monotonic()
    result = repo.forge(*args, timeout=120)
    elapsed = time.monotonic() - start
    assert result.returncode == 0, result.stderr
    if command == "next":
        assert result.stdout == first.stdout
        assert "Next: forge close saved-0" in result.stdout
    else:
        rows = {row["id"]: row for row in json.loads(result.stdout)["items"]}
        assert len([key for key in rows if key.startswith("saved-")]) == 1200
        assert rows["saved-0"]["title"] == "Current local title"
        assert rows["saved-1199"]["stage"] == "merged"
    # Windows process and filesystem costs have a separate platform allowance.
    budget = 30 if os.name == "nt" else 5
    assert elapsed < budget, f"{command} took {elapsed:.2f}s (budget {budget}s)"
