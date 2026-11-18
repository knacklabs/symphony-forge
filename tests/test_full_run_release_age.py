"""Release advice uses complete full runs, rather than only failures.

Audit: protects next and board facts against missing, stale, queued and cancelled
full runs. Existing failure tests cannot detect absent or old green proof.
Round 2 audit: queued reruns must retain their complete attempts, custom
workflows must use their posted test result, and overdue rows must retain the
sorted wait contract. The first-round fixture missed those service states.
Only GitHub is faked at gh. No production-only test seam is needed.
"""
import json
import subprocess

import pytest

from test_board_dependency_timelines import _client
from test_failed_full_run_needs_you import NIGHTLY, answer, configure, run
from conftest import REAL_UV
from test_board_server import live

STORY = "full-run-age"
pytestmark = pytest.mark.platform


def test_1_next_and_board_show_full_run_age_before_release(repo, gh, tmp_path, monkeypatch):
    _client(repo, gh, tmp_path, "new")
    gh.respond("pr", "list", stdout="[]")
    gh.respond("api", "graphql", stdout=json.dumps({"data": {"repository": {"pullRequests": {"nodes": []}}}}))
    green = {**run(41, conclusion="success"), "created_at": "2030-01-01T01:00:00Z",
             "updated_at": "2030-01-01T02:00:00Z", "status": "completed"}
    cancelled = {**run(42, conclusion="cancelled"), "created_at": "2030-01-02T01:00:00Z",
                 "updated_at": "2030-01-02T02:00:00Z", "status": "completed"}
    queued = {**run(43, conclusion=None), "created_at": "2030-01-01T01:00:00Z", "status": "queued"}
    red = {**run(44), "created_at": "2030-01-02T06:00:00Z",
           "updated_at": "2030-01-02T07:00:00Z", "status": "completed"}
    recent_green = {**green, "created_at": "2030-01-03T02:00:00Z", "updated_at": "2030-01-03T03:00:00Z"}
    recent_cancelled = {**cancelled, "created_at": "2030-01-03T03:00:00Z", "updated_at": "2030-01-03T04:00:00Z"}
    gh.respond("api", "repos/{owner}/{repo}/actions/runs/41/attempts/1", stdout=json.dumps(green))
    cases = [([], "No complete full test run on main.", True),
             ([green], "Last complete full test run on main passed 2 hours ago.", False),
             ([{**queued, "created_at": "2030-01-01T04:00:00Z"}, green],
              "Last complete full test run on main passed 3 hours ago. Latest full test run is queued for 1 hour.", False),
             ([{**green, "conclusion": None, "run_attempt": 2, "status": "queued"}],
              "Last complete full test run on main passed 4 hours ago. Latest full test run is queued for 5 hours.", False),
             ([green], "Last complete full test run on main passed 24 hours ago.", False),
             ([green], "Last complete full test run on main passed 26 hours ago.", True),
             ([cancelled, green], "Last complete full test run on main was cancelled 3 hours ago.", True),
             ([red, green], "Last complete full test run on main failed 1 hour ago.", True),
             ([recent_cancelled, recent_green], "Last complete full test run on main was cancelled 1 hour ago.", False),
             ([recent_green, queued],
              "Last complete full test run on main passed 3 hours ago. A full test run is queued for 53 hours.", False),
             ([queued], "No complete full test run on main. Latest full test run is queued for 100 hours.", True),
             ([{**queued, "created_at": "2030-01-02T09:00:00Z"}, green,
               {**recent_green, "event": "pull_request"}, {**recent_green, "head_branch": "feature"}],
              "Last complete full test run on main passed 100 hours ago. Latest full test run is queued for 69 hours.", True)]
    for index, (runs, line, needs) in enumerate(cases):
        monkeypatch.setenv("FORGE_NOW", ["2030-01-01T03:00:00+00:00", "2030-01-01T04:00:00+00:00",
                                        "2030-01-01T05:00:00+00:00", "2030-01-01T06:00:00+00:00",
                                        "2030-01-02T02:00:00+00:00",
                                        "2030-01-02T04:00:00+00:00", "2030-01-02T05:00:00+00:00",
                                        "2030-01-02T08:00:00+00:00", "2030-01-03T05:00:00+00:00",
                                        "2030-01-03T06:00:00+00:00", "2030-01-05T05:00:00+00:00",
                                        "2030-01-05T06:00:00+00:00"][index])
        answer(gh, schedule=runs)
        said = repo.forge("next")
        assert said.returncode == 0, said.stderr
        assert line in said.stdout
        board = repo.forge("board", "--json")
        assert board.returncode == 0, board.stderr
        team = json.loads(board.stdout)["team"]
        assert team["full_run"]["line"] == line
        asks = [entry for entry in team["needs_you"] if entry["reason"] == "full run due"]
        assert bool(asks) == needs
        if needs:
            assert "Needs you: No green full test run in the last 24 hours. Run the full suite before a release." in said.stdout
            assert asks[0]["title"] == "No green full test run in the last 24 hours"
            assert "waited_seconds" in asks[0] and "seconds" not in asks[0]
            waits = [entry["since"] for entry in team["needs_you"] if entry["since"] is not None]
            assert waits == sorted(waits)

    # The real page shows the same server-derived facts, including a missing run.
    script = '''
import sys
from playwright.sync_api import expect, sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox"])
    try:
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(sys.argv[1])
        needs = page.get_by_role("region", name="Needs you")
        expect(needs).to_contain_text("Latest full test run is queued for 69 hours.", timeout=60000)
        expect(needs).to_contain_text("Last complete full test run on main passed 100 hours ago.")
        expect(needs).to_contain_text("No green full test run in the last 24 hours")
    finally:
        browser.close()
'''
    with live(repo) as url:
        shown = subprocess.run([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                                "playwright==1.55.0", "python", "-c", script, url],
                               capture_output=True, text=True, encoding="utf-8", timeout=120)
        assert shown.returncode == 0, shown.stdout + shown.stderr

    # A custom workflow can finish successfully while its required full-suite
    # status reports failure. The test result, not the workflow shell, decides.
    settings = repo.path / "forge.toml"
    configure(repo, settings.read_text("utf-8"), 'full_suite_workflow = "nightly.yml"')
    answer(gh, schedule=[{**recent_green, "head_sha": "custom-head", "created_at": "2030-01-05T03:00:00Z",
                          "updated_at": "2030-01-05T05:00:00Z"}], file=NIGHTLY)
    def status_history(state, at, *, more=False):
        return json.dumps({"data": {"repository": {
            "pullRequests": {"nodes": []}, "ref": {"target": {"history": {
                "nodes": [{"status": {"contexts": [{"context": "forge-full-suite", "state": state,
                                                       "createdAt": at}]}}],
                "pageInfo": {"hasNextPage": more, "endCursor": "older" if more else None}}}}}}})
    gh.respond("api", "graphql", stdout=status_history("FAILURE", "2030-01-05T04:00:00Z"))
    said = repo.forge("next")
    assert "Last complete full test run on main failed 2 hours ago." in said.stdout
    assert "Needs you: No green full test run in the last 24 hours." in said.stdout
    custom = repo.forge("board", "--json")
    assert custom.returncode == 0, custom.stderr
    assert any(row["reason"] == "full run due" for row in json.loads(custom.stdout)["team"]["needs_you"])

    # Laptop full runs publish statuses instead of workflow runs. They use the
    # same release advice and completion age on both command surfaces.
    configure(repo, settings.read_text("utf-8"), 'test_place = "local"')
    gh.respond("api", "graphql", stdout=json.dumps({"data": {"repository": {
        "pullRequests": {"nodes": []}, "ref": {"target": {"history": {"nodes": [
            {"status": {"contexts": [{"context": "forge-full-suite", "state": "SUCCESS",
                                       "createdAt": "2030-01-04T04:00:00Z"}]}}]}}}}}}))
    said = repo.forge("next")
    assert said.returncode == 0, said.stderr
    line = "Last complete full test run on main passed 26 hours ago."
    assert line in said.stdout
    board = repo.forge("board", "--json")
    assert board.returncode == 0, board.stderr
    team = json.loads(board.stdout)["team"]
    assert team["full_run"]["line"] == line
    assert any(row["reason"] == "full run due" for row in team["needs_you"])
    # The first page has 30 newer commits with no status. The prior complete
    # failure is on the next page, and remains a failure rather than a live run.
    monkeypatch.setenv("FORGE_NOW", "2030-01-05T07:00:00+00:00")
    empty_page = json.loads(status_history("FAILURE", "2030-01-04T04:00:00Z", more=True))
    empty_page["data"]["repository"]["ref"]["target"]["history"]["nodes"] = [{"status": None}] * 30
    gh.respond("api", "graphql", stdout=json.dumps(empty_page))
    gh.respond("api", "graphql", "-f", 'after=older', stdout=status_history("FAILURE", "2030-01-04T04:00:00Z"))
    said = repo.forge("next")
    assert "Last complete full test run on main failed 27 hours ago." in said.stdout
    board = repo.forge("board", "--json")
    assert board.returncode == 0, board.stderr
    team = json.loads(board.stdout)["team"]
    assert team["full_run"]["line"] == "Last complete full test run on main failed 27 hours ago."
    assert any(row["reason"] == "full run due" for row in team["needs_you"])
