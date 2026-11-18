"""One bounded workflow read supplies release advice to next and the board.

Audit: this owns the owner's replacement contract: fresh green plus queued has
no warning on either surface, stale or missing green does, and custom workflows
use their own run list. The earlier test missed next's negative assertion and
did not bound history requests. Only GitHub is faked. No test seam is needed.
"""
import json
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from conftest import REAL_UV
from test_board_dependency_timelines import _client
from test_board_server import live
from test_failed_full_run_needs_you import configure, run

STORY = "full-run-age"
pytestmark = pytest.mark.platform
WARNING = "Needs you: No green full test run in the last 24 hours. Run the full suite before a release."


def test_1_next_and_board_show_full_run_age_before_release(repo, gh, tmp_path, monkeypatch):
    _client(repo, gh, tmp_path, "new")
    gh.respond("pr", "list", stdout="[]")
    gh.respond("api", "graphql", stdout=json.dumps({"data": {"repository": {"pullRequests": {"nodes": []}}}}))
    settings = (repo.path / "forge.toml").read_text("utf-8")
    now = datetime(2030, 1, 5, 6, tzinfo=timezone.utc)

    for workflow in ("forge.yml", "nightly.yml"):
        if workflow == "nightly.yml":
            configure(repo, settings, 'full_suite_workflow = "nightly.yml"')
        endpoint = f"repos/{{owner}}/{{repo}}/actions/workflows/{workflow}/runs"
        def calls():
            return [call for call in gh.calls() if call[:2] == ["api", endpoint]]

        for green_age, newer, wait, needs in ((2, "queued", 1, False),
                                             (2, "cancelled", 1, False), (30, "cancelled", 1, True),
                                             (24, None, 0, True), (None, None, 0, True),
                                             (30, "queued", 25, True)):
            now += timedelta(hours=2)
            monkeypatch.setenv("FORGE_NOW", now.isoformat())
            def record(number, conclusion, hours):
                at = (now - timedelta(hours=hours)).isoformat()
                return {**run(number, file=workflow, conclusion=conclusion),
                        "status": "completed" if conclusion else "queued",
                        "created_at": at, "updated_at": at}
            runs = [record(41, "success", green_age)] if green_age is not None else []
            line = (f"Last green full test run on main passed {green_age} hours ago."
                    if runs else "No green full test run on main.")
            if newer:
                runs.insert(0, record(42, None if newer == "queued" else newer, wait))
                line += (f" Newer full test run is queued for {wait} hour{'s' if wait != 1 else ''}."
                         if newer == "queued" else " Newer full test run was cancelled.")
            gh.respond("api", endpoint, stdout=json.dumps({"total_count": 10000, "workflow_runs": runs}))
            before = len(calls())
            said = repo.forge("next")
            assert said.returncode == 0, said.stderr
            assert line in said.stdout
            assert (WARNING in said.stdout) == needs
            board = repo.forge("board", "--json")
            assert board.returncode == 0, board.stderr
            team = json.loads(board.stdout)["team"]
            assert team["full_run"]["line"] == line
            asks = [entry for entry in team["needs_you"] if entry["reason"] == "full run due"]
            assert bool(asks) == needs
            if needs:
                assert asks[0]["title"] == "No green full test run in the last 24 hours"
                assert "waited_seconds" in asks[0] and "seconds" not in asks[0]
            assert repo.forge("next").returncode == 0
            assert len(calls()) == before + 1, "next and board share the 60-second result"
            assert all("per_page=20" in call and "branch=main" in call and "--paginate" not in call
                       for call in calls())
            assert not any("/attempts/" in " ".join(call) or "history(first:" in " ".join(call)
                           for call in gh.calls())

    before = len(calls())
    monkeypatch.setenv("FORGE_NOW", (now + timedelta(seconds=59)).isoformat())
    assert repo.forge("next").returncode == 0
    assert len(calls()) == before
    monkeypatch.setenv("FORGE_NOW", (now + timedelta(seconds=60)).isoformat())
    assert repo.forge("board", "--json").returncode == 0
    assert len(calls()) == before + 1

    script = '''
import sys
from playwright.sync_api import expect, sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox"])
    try:
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(sys.argv[1])
        needs = page.get_by_role("region", name="Needs you")
        expect(needs).to_contain_text(sys.argv[2], timeout=60000)
        expect(needs).to_contain_text("No green full test run in the last 24 hours")
    finally:
        browser.close()
'''
    with live(repo) as url:
        shown = subprocess.run([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                                "playwright==1.55.0", "python", "-c", script, url, line],
                               capture_output=True, text=True, encoding="utf-8", timeout=120)
        assert shown.returncode == 0, shown.stdout + shown.stderr
