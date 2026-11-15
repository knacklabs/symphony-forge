"""A story's review rounds sit on its parts, and the board shows them in real Chrome.

The story has one part that merged before the board's seven-day window (the Now snapshot leaves it
out) and one recent part. Each has review rounds in the local event log. The drawer and the full
page list every round under the part's plain title, and the story's round count adds them up.
"""
import json
import subprocess
from types import SimpleNamespace

import pytest

from conftest import REAL_UV
from test_board_counts import github
from test_board_item_page import PLAN
from test_board_server import client, clone, live, pushed, snapshot  # noqa: F401

pytestmark = pytest.mark.platform

STORY = "FIX-STORY-ROUNDS"

SCRIPT = r"""
import re, sys
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright
url = sys.argv[1]
BOARD = "(await import(new URL('app.js' + location.search, location.href))).Board"

axe = Axe()

def scan(page, where, context=None):
    page.evaluate('Promise.all(document.getAnimations().map(a => a.finished))')
    found = axe.run(page, context=context).response['violations']
    assert not found, (where, [(v['id'], [n['target'] for n in v['nodes']]) for v in found])

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        for scheme in ('light', 'dark'):
            page = browser.new_page(viewport={'width': 1440, 'height': 900}, color_scheme=scheme)
            page.goto(url)
            expect(page.get_by_role('status')).to_have_text('Live', timeout=60000)
            page.evaluate("async () => " + BOARD + ".openDrawer('SHOP')")
            drawer = page.get_by_role('complementary', name='Shoppers can save a basket')
            expect(drawer).to_be_visible()
            expect(drawer).not_to_contain_text('No review rounds yet')
            for part, rounds in (('Save a basket', ['Round 1', 'Round 2']), ('Share a basket', ['Round 1'])):
                group = drawer.get_by_role('list', name=part)
                expect(group.get_by_role('listitem')).to_have_count(len(rounds))
                for text in rounds:
                    expect(group).to_contain_text(text)
            expect(drawer).to_contain_text('Basket total is off by one')  # the older part's own finding
            expect(drawer.locator('.figures div').filter(has_text='review rounds').locator('dd')).to_have_text('3')
            assert 'SAVE' not in drawer.inner_text() and 'SHOP/' not in drawer.inner_text()
            scan(page, f'story drawer, {scheme}', '.drawer')  # the Now screen under it is another part's

            drawer.get_by_role('link', name='Full history').click()
            expect(page.get_by_role('heading', level=1, name='Shoppers can save a basket')).to_be_visible()
            expect(page.locator('.summary .figures div').filter(has_text='review rounds').locator('dd')).to_have_text('3')
            page.get_by_role('tab', name='Rounds', exact=True).click()
            panel = page.get_by_role('tabpanel')
            expect(panel).not_to_contain_text('No review rounds yet')
            expect(panel.get_by_role('list', name='Save a basket').get_by_role('listitem')).to_have_count(2)
            expect(panel.get_by_role('list', name='Share a basket').get_by_role('listitem')).to_have_count(1)
            scan(page, f'story rounds, {scheme}')
            page.close()
    finally:
        browser.close()
"""


def event(item, round, at, title):
    return {"id": f"{item}-{round}", "item": item, "event": "review result", "round": round, "review_round": round,
            "at": at, "outcome": "findings", "findings": [{"priority": "P2", "file": "basket.py", "title": title}]}


def test_1_a_story_whose_parts_merged_lists_their_rounds_and_counts_them(client, gh, tmp_path, monkeypatch):
    teammate = clone(client, tmp_path)
    old, recent = "2026-10-01T09:00:00+00:00", "2026-11-13T09:00:00+00:00"
    monkeypatch.setenv("GIT_AUTHOR_DATE", old)
    monkeypatch.setenv("GIT_COMMITTER_DATE", old)
    pushed(teammate, "Plan a basket", {"basket.py": "total = 0\n", "plans/SHOP.md": PLAN,
           ".factory/stories/SHOP/story.json":
           json.dumps({"doc": "plans/SHOP.md", "title": "Shoppers can save a basket", "status": "approved"}),
           ".factory/stories/SHOP/tasks/SAVE.json": json.dumps({"status": "merged", "branch": "task/SHOP-SAVE"})})
    monkeypatch.setenv("GIT_AUTHOR_DATE", recent)
    monkeypatch.setenv("GIT_COMMITTER_DATE", recent)
    pushed(teammate, "Share a basket", {
        ".factory/stories/SHOP/tasks/SHARE.json": json.dumps({"status": "merged", "branch": "task/SHOP-SHARE"})})
    monkeypatch.delenv("GIT_AUTHOR_DATE")
    monkeypatch.delenv("GIT_COMMITTER_DATE")
    client.git("fetch", "-q", "origin")
    # The story's own pull request keeps a time record with no rounds: an empty list, not a missing one.
    github(SimpleNamespace(repo=client, gh=gh), [{
        "number": 7, "headRefName": "story/SHOP", "headRefOid": "0" * 40, "state": "OPEN", "title": "Shoppers can save a basket",
        "isDraft": False, "body": "<!-- forge:begin -->\n<!-- forge:time-record " + json.dumps({"events": [], "timings": []})
        + " -->\n<!-- forge:end -->"}])
    with (client.path / ".git/forge/events.jsonl").open("a", encoding="utf-8") as log:
        for row in (event("SHOP/SAVE", 1, "2026-10-01T10:00:00+00:00", "Basket total is off by one"),
                    event("SHOP/SAVE", 2, "2026-10-01T11:00:00+00:00", "Basket total is off by one"),
                    event("SHOP/SHARE", 1, "2026-11-13T10:00:00+00:00", "Shared link shows no basket")):
            log.write(json.dumps(row) + "\n")
    with live(client, FORGE_BOARD_FETCH_WAIT="3600", FORGE_NOW="2026-11-14T12:00:00+00:00") as url:
        rows = {row["id"]: row for parent in snapshot(url)["items"] for row in (parent, *parent["children"])}
        assert rows["SHOP"]["rounds"] == [], rows["SHOP"]  # the story has a record of its own, and no rounds in it
        assert "SHOP/SAVE" not in rows and "SHOP/SHARE" in rows, sorted(rows)  # the old part is outside the window
        shown = subprocess.run([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                                "playwright==1.55.0", "--with", "axe-playwright-python==0.1.4", "python", "-c", SCRIPT, url],
                               capture_output=True, text=True, encoding="utf-8", timeout=300)
        assert shown.returncode == 0, shown.stdout + shown.stderr
