"""The live Now screen preserves missing facts, assignment readiness and spoken progress."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from conftest import REAL_UV
from test_board import DOC
from test_board_server import client, clone, live, pushed  # noqa: F401

STORY = "FIX-BOARD-NOW-FACTS"

BROWSER = r"""
import sys
from playwright.sync_api import expect, sync_playwright
url, mode, expected = sys.argv[1:]
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.goto(url)
        expect(page.get_by_role('status')).to_have_text('Live', timeout=60000)
        if mode == 'waiting':
            figures = page.get_by_role('region', name='Figures')
            expect(figures).to_contain_text(expected + ' waiting on people')
        elif mode == 'readiness':
            planned = page.get_by_role('region', name='Planned', exact=True)
            ready = planned.get_by_role('button', name='Save a basket SHOP can start')
            expect(ready).to_be_visible()
            expect(planned.get_by_role('button', name='Show when it was saved SHOP', exact=True)).to_be_visible()
            expect(planned.get_by_role('button', name='Share a basket SHOP', exact=True)).to_be_visible()
        elif mode == 'progress':
            stories = page.get_by_role('region', name='Stories')
            story = stories.get_by_role('button', name='Shoppers can save a basket', exact=False)
            expect(story).to_contain_text('SHOP')
            expect(story).to_contain_text('@page-dev')
            expect(story.get_by_role('img', name='1 of 3 parts merged', exact=True)).to_be_visible()
        elif mode == 'isolation':
            page.get_by_role('link', name='Releases', exact=True).click()
            kept = page.get_by_role('region', name='Known issues by file')
            expect(kept.get_by_role('listitem')).to_contain_text('Basket total rounds down')
            kept.get_by_text('src/basket.py', exact=True).click()
            expect(kept.get_by_text('Basket total rounds down', exact=True)).to_be_visible()
            page.evaluate('Promise.all(document.getAnimations().map(a => a.finished))')
            styles = '''e => [e, ...e.querySelectorAll('*')].map(node => {
                const css = getComputedStyle(node);
                return [css.color, css.fontSize, css.display, css.width, css.height, css.gap];
            })'''
            showing = kept.evaluate(styles)
            page.evaluate("document.querySelector('link[href^=\"now.css\"]').sheet.disabled = true")
            without_now = kept.evaluate(styles)
            assert without_now == showing, ('Now styles change the Releases screen', showing, without_now)
    finally:
        browser.close()
"""


def look(url, mode, expected=""):
    shown = subprocess.run([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                            "playwright==1.55.0", "python", "-c", BROWSER, url, mode, expected],
                           capture_output=True, text=True, encoding="utf-8", timeout=300)
    assert shown.returncode == 0, shown.stdout + shown.stderr


@pytest.mark.parametrize("client, waits, expected", [
    ("new", [None], "unknown"), ("new", [600, None], "unknown"), ("new", [0], "0%"),
    ("adopted-v1.2.2", [None], "unknown"),
], indirect=["client"])
def test_19_waiting_share_stays_unknown_when_a_timed_item_has_no_wait_record(client, tmp_path, waits, expected):
    """Missing wait observations cannot become zero, even beside a known wait; recorded zero can."""
    end = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=1)
    records, events = {}, []
    for n, waited in enumerate(waits, 1):
        slug = f"done-{n}"
        records[f".factory/fixes/{slug}.json"] = json.dumps({
            "kind": "fix", "branch": f"fix/{slug}", "status": "merged", "why": f"Readers see total {n}",
            "done_when": "It shows", "steps": [{"step": "start", "at": (end - timedelta(hours=1)).isoformat()}]})
        if waited is not None:
            events += [{"id": f"wait-{n}", "item": slug, "event": "owner wait start", "reason": "merge",
                        "at": (end - timedelta(seconds=waited)).isoformat()},
                       {"id": f"waited-{n}", "item": slug, "event": "owner wait end", "wait_id": f"wait-{n}",
                        "at": end.isoformat()}]
        events.append({"id": f"end-{n}", "item": slug, "event": "item finished", "at": end.isoformat()})
    pushed(clone(client, tmp_path), "Merge observed fixes", records)
    client.git("fetch", "-q", "origin")
    with (client.path / ".git/forge/events.jsonl").open("a", encoding="utf-8") as log:
        log.writelines(json.dumps(event) + "\n" for event in events)
    with live(client) as url:
        look(url, "waiting", expected)


def assigned_story(client, tmp_path, *, merged=False):
    files = {"plans/SHOP.md": DOC.replace("## Tasks\n", "## Tasks\n\nOwner: page-dev\n", 1),
             ".factory/stories/SHOP/story.json": json.dumps({
                 "doc": "plans/SHOP.md", "title": "Shoppers can save a basket", "status": "approved"})}
    if merged:
        files[".factory/stories/SHOP/tasks/SAVE.json"] = json.dumps({
            "branch": "task/SHOP-SAVE", "status": "merged"})
    pushed(clone(client, tmp_path), "Assign the basket story", files)
    client.git("fetch", "-q", "origin")


def test_20_assigning_an_unstarted_story_keeps_its_ready_part_in_planned(client, tmp_path):
    """An owner brings unstarted parts into item rows without changing their dependency readiness."""
    assigned_story(client, tmp_path)
    with live(client) as url:
        look(url, "readiness")


def test_21_story_progress_has_a_spoken_merged_part_count(client, tmp_path):
    """The coloured progress strip also tells an assistive reader how many parts have merged."""
    assigned_story(client, tmp_path, merged=True)
    with live(client) as url:
        look(url, "progress")


def test_22_now_styles_do_not_change_the_releases_screen(client, tmp_path):
    """Loading Now must not set the type, colour or layout of another screen's issue counts."""
    pushed(clone(client, tmp_path), "Keep a basket follow-up", {"src/basket.py": "total = 0\n",
                                                               ".factory/fixes/old.json": json.dumps({
        "kind": "fix", "branch": "fix/old", "status": "merged", "why": "Readers see old",
        "done_when": "It shows", "known": [{"outcome": "follow-up", "file": "src/basket.py", "line": 3,
            "title": "Basket total rounds down", "gain": 2, "work": 1, "harm": 1}]})})
    client.git("fetch", "-q", "origin")
    with live(client) as url:
        look(url, "isolation")
