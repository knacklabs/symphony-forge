"""A failed latest full test run shows under Needs you on the live board page, and a click on its
row opens the run on GitHub. While a fix for it is in progress, the same row says so.

Real `forge board` and real Chrome (run the way test_board_now_screen.look runs it). Only GitHub is
faked: the stub gh lists 100 passing runs of another workflow in the shared request, so the row
can come only from the full workflow's own scheduled-runs request.
"""
STORY = "FORGE-NIGHTLY-1"

import json
import shlex
import subprocess

import pytest

from conftest import REAL_UV
from test_board_server import client, live, snapshot  # noqa: F401

pytestmark = pytest.mark.platform

URL = "https://github.com/acme/shop/actions/runs/41"
TITLE = "The latest full test run on main failed"
FORGE_RUNS = ("api", "repos/{owner}/{repo}/actions/workflows/forge.yml/runs", "--method", "GET", "--raw-field")
WHY = "The scheduled forge (forge.yml) run fails on main"

BROWSER = r"""
import json, re, sys
from playwright.sync_api import expect, sync_playwright
url, mode, run_url = sys.argv[1], sys.argv[2], sys.argv[3]
title = "The latest full test run on main failed"
words = "Fix in progress" if mode == "fixing" else "Full test run"
with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox"])
    try:
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        context.route("https://github.com/**", lambda route: route.fulfill(
            status=200, content_type="text/html", body="<title>The run</title>"))
        page = context.new_page()
        page.goto(url)
        expect(page.get_by_role("status")).to_have_text("Live", timeout=60000)
        needs = page.get_by_role("region", name="Needs you")
        row = needs.get_by_role("button", name=f"Fix {words} {title}")
        expect(row).to_be_visible()
        if mode == "fixing":
            expect(needs).not_to_contain_text("Full test run")
        else:
            # The keyboard reaches the row, and a click opens the run in a new page, not a drawer.
            page.evaluate("async () => { const Board = (await import(new URL('app.js' + location.search, location.href))).Board;"
                          " Board.openDrawer = id => { window.drawer = id; }; }")
            row.focus()
            with context.expect_page() as opened:
                page.keyboard.press("Enter")
            opened.value.wait_for_load_state()
            assert opened.value.url == run_url, opened.value.url
            assert page.evaluate("window.drawer") is None, "the row opened a drawer"
            with context.expect_page() as clicked:
                row.click()
            clicked.value.wait_for_load_state()
            assert clicked.value.url == run_url, clicked.value.url
        page.get_by_role("button", name="Me", exact=True).click()
        expect(page.get_by_role("region", name="Needs you").get_by_role("button", name=f"Fix {words} {title}")).to_be_visible()
    finally:
        browser.close()
"""


def look(url, mode):
    shown = subprocess.run([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with", "playwright==1.55.0",
                            "python", "-c", BROWSER, url, mode, URL], capture_output=True, text=True,
                           encoding="utf-8", timeout=300)
    assert shown.returncode == 0, shown.stdout + shown.stderr


def test_1_a_failed_full_test_run_shows_under_needs_you_and_opens_the_run(client, gh):
    busy = [{"id": 1000 + n, "workflow_id": 9, "name": "backup", "event": "schedule", "conclusion": "success",
             "head_branch": "main", "path": ".github/workflows/backup.yml",
             "created_at": f"2025-01-0{1 + n // 24}T{n % 24:02d}:30:00Z"} for n in range(100)]
    failed = {"id": 41, "workflow_id": 1, "name": "forge", "event": "schedule", "conclusion": "failure",
              "run_attempt": 1, "head_branch": "main", "path": ".github/workflows/forge.yml",
              "created_at": "2026-01-01T03:00:00Z", "html_url": URL}
    gh.respond("api", "repos/{owner}/{repo}/actions/runs", "--method", "GET", stdout=json.dumps({"workflow_runs": busy}))
    gh.respond(*FORGE_RUNS, "event=schedule", stdout=json.dumps({"workflow_runs": [failed]}))
    gh.respond(*FORGE_RUNS, "event=workflow_dispatch", stdout=json.dumps({"workflow_runs": []}))
    gh.respond("run", "view", "41", stdout="full suite\tRun tests\t2030-01-01T03:40:00Z FAILED tests/test_a.py::test_one - boom")
    with live(client) as url:
        team = snapshot(url)["team"]
        runs = [entry for entry in team["needs_you"] if entry["kind"] == "run"]
        assert len(runs) == 1
        assert {key: runs[0][key] for key in ("id", "title", "reason", "kind", "detail", "url", "fixing")} == {
            "id": "run:forge.yml", "title": TITLE, "reason": "failed run", "kind": "run", "detail": "full suite",
            "url": URL, "fixing": False}
        assert runs[0]["waited_seconds"] > 0
        count = len(team["needs_you"])
        assert f", {count} need{'s' if count == 1 else ''} you," in team["sentence"]
        look(url, "failed")

        # A fix for it is in progress: the same row stays, with other words.
        done = "full suite of the scheduled forge (forge.yml) workflow pass again on the next scheduled run on main"
        started = client.forge(*shlex.split(f'fix start "{WHY}" --done "{done}" --kind mechanical'))
        assert started.returncode == 0, started.stdout + started.stderr
        runs = [entry for entry in snapshot(url)["team"]["needs_you"] if entry["kind"] == "run"]
        assert [(entry["title"], entry["fixing"]) for entry in runs] == [(TITLE, True)]
        look(url, "fixing")
