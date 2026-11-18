"""Release advice uses complete full runs, rather than only failures.

Audit: protects next and board facts against missing, stale, queued and cancelled
full runs. Existing failure tests cannot detect absent or old green proof.
Only GitHub is faked at gh. No production-only test seam is needed.
"""
import json
import subprocess

import pytest

from test_board_dependency_timelines import _client
from test_failed_full_run_needs_you import answer, configure, run
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
    cases = [([], "No complete full test run on main.", True),
             ([green], "Last complete full test run on main passed 2 hours ago.", False),
             ([green], "Last complete full test run on main passed 24 hours ago.", False),
             ([green], "Last complete full test run on main passed 26 hours ago.", True),
             ([cancelled, green], "Last complete full test run on main was cancelled 3 hours ago.", True),
             ([red, green], "Last complete full test run on main failed 1 hour ago.", True),
             ([recent_cancelled, recent_green], "Last complete full test run on main was cancelled 1 hour ago.", False),
             ([queued], "No complete full test run on main. Latest full test run is queued for 100 hours.", True),
             ([{**queued, "created_at": "2030-01-02T09:00:00Z"}, green,
               {**recent_green, "event": "pull_request"}, {**recent_green, "head_branch": "feature"}],
              "Last complete full test run on main passed 100 hours ago. Latest full test run is queued for 69 hours.", True)]
    for index, (runs, line, needs) in enumerate(cases):
        monkeypatch.setenv("FORGE_NOW", ["2030-01-01T03:00:00+00:00", "2030-01-01T04:00:00+00:00",
                                        "2030-01-02T02:00:00+00:00",
                                        "2030-01-02T04:00:00+00:00", "2030-01-02T05:00:00+00:00",
                                        "2030-01-02T08:00:00+00:00", "2030-01-03T05:00:00+00:00",
                                        "2030-01-05T05:00:00+00:00", "2030-01-05T06:00:00+00:00"][index])
        answer(gh, schedule=runs)
        said = repo.forge("next")
        assert said.returncode == 0, said.stderr
        assert line in said.stdout
        board = repo.forge("board", "--json")
        assert board.returncode == 0, board.stderr
        team = json.loads(board.stdout)["team"]
        assert team["full_run"]["line"] == line
        asks = [entry for entry in team["needs_you"] if entry["kind"] == "run"]
        assert bool(asks) == needs
        if needs:
            assert "Needs you: No green full test run in the last 24 hours. Run the full suite before a release." in said.stdout
            assert asks[0]["title"] in ("No green full test run in the last 24 hours",
                                         "The latest full test run on main failed")

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

    # Laptop full runs publish statuses instead of workflow runs. They use the
    # same release advice and completion age on both command surfaces.
    settings = repo.path / "forge.toml"
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
    assert any(row["kind"] == "run" for row in team["needs_you"])
