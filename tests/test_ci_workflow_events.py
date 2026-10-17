"""The pane's command feed names a completed workflow once for each commit."""
import copy

import pytest

from test_board_dependency_timelines import _client, _land_fixture
from test_close import env  # noqa: F401
from test_machine_views import github, pull, view
from test_story import worktree

STORY = "FIX-FRESH-PANE-EVENTS"


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_3_ci_events_name_each_workflow_and_result_once_per_commit(
        repo, gh, tmp_path, monkeypatch, history, env):
    configured = (repo.path / "forge.toml").read_text("utf-8")
    _client(repo, gh, tmp_path, history)
    env.commit(repo.path, "forge.toml", configured, "Configure checks")
    _land_fixture(repo)
    made = repo.forge("fix", "start", "The basket saves", "--done", "It saves", "--slug", "basket")
    assert made.returncode == 0, made.stderr
    folder = worktree(repo, "fix/basket")
    env.commit(folder, "README.md", "Save the basket.\n")
    for _ in range(2):
        closed = env.close("basket")
        assert closed.returncode == 0, closed.stderr
    pr = pull(1, "fix/basket")
    pr["headRefOid"] = repo.git("rev-parse", "fix/basket")
    contexts = pr["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]
    job = contexts["nodes"][0]
    contexts["nodes"] = []
    for number, (workflow, name, conclusion) in enumerate([
            ("Client tests", "tests (Linux)", "SUCCESS"),
            ("Client tests", "tests (Windows)", "SUCCESS"),
            ("Pull request", "forge-pr-check", "FAILURE")]):
        contexts["nodes"].append({**job, "databaseId": number + 100, "name": name,
            "conclusion": conclusion,
            "checkSuite": {"status": "COMPLETED", "conclusion": conclusion,
                           "workflowRun": {"workflow": {"id": workflow, "name": workflow}}}})

    def delivered():
        current = next(row for row in view(repo, "board")["items"] if row["id"] == "basket")
        assert all(event["title"] != "Ci finished" for event in current["occurrences"])
        return [event for event in current["occurrences"]
                if event["title"].startswith(("Client tests ", "Pull request "))]

    github(gh, [pr])
    monkeypatch.setenv("FORGE_NOW", "2026-10-17T10:00:00+00:00")
    first = delivered()
    assert sorted(event["title"] for event in first) == ["Client tests passed", "Pull request failed"]
    assert len({event["id"] for event in first}) == 2

    # A same-commit rerun supplies new check ids and times, but does not announce
    # either workflow twice. A later push is a new occurrence of each workflow.
    for job in contexts["nodes"]:
        job.update(databaseId=job["databaseId"] + 100, completedAt="2026-10-17T10:01:00Z")
    github(gh, [pr])
    monkeypatch.setenv("FORGE_NOW", "2026-10-17T10:01:00+00:00")
    assert delivered() == first
    next_pr = copy.deepcopy(pr)
    next_pr["headRefOid"] = "next-commit"
    github(gh, [next_pr])
    monkeypatch.setenv("FORGE_NOW", "2026-10-17T10:02:00+00:00")
    second = delivered()
    assert sorted(event["title"] for event in second) == ["Client tests passed", "Pull request failed"]
    assert {event["id"] for event in first}.isdisjoint(event["id"] for event in second)
