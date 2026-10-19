"""A manager gives a story to a developer from the board. The Assign control in a story's drawer
and on its full page runs `forge assign` through the board's server; a refusal shows its reason
beside the control, in plain words with no command text, and changes nothing. A teammate's clone
sees the new owner once it fetches. The real command, server and browser are all the test uses."""
from __future__ import annotations

import json
import subprocess

import pytest

from conftest import REAL_UV
from test_board import DOC
from test_board_counts import board, rows
from test_board_server import client, clone, live, pushed, snapshot  # noqa: F401

STORY = "FORGE-BOARD-4"

NO_PLAN = """# Ideas get a home

## What changes for you

Ideas have one place to live.
"""

SCRIPT = r"""
import re, sys
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright
url = sys.argv[1]
BOARD = "(await import(new URL('app.js' + location.search, location.href))).Board"
COMMAND = re.compile(r"\bforge [a-z]|--[a-z]|`|Next:")
axe = Axe()

def scan(page, where):
    # The control and what it opened; the screens around it have their own scans.
    page.evaluate('Promise.all(document.getAnimations().map(a => a.finished))')
    found = axe.run(page, context='.assign').response['violations']
    assert not found, (where, [(v['id'], [n['target'] for n in v['nodes']]) for v in found])

def give(page, place, login):
    button = place.get_by_role('button', name='Assign')
    button.focus()
    page.keyboard.press('Enter')
    expect(button).to_have_attribute('aria-expanded', 'true')
    field = place.get_by_label('GitHub username')
    expect(field).to_be_focused()
    page.keyboard.type(login)
    page.keyboard.press('Enter')

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        for scheme in ('light', 'dark'):
            page = browser.new_page(viewport={'width': 1440, 'height': 900}, color_scheme=scheme)
            page.goto(url)
            expect(page.get_by_role('status').first).to_have_text('Live', timeout=60000)
            if scheme == 'light':
                # A refusal says why beside the control, in plain words, and the drawer stays open.
                page.evaluate("async () => " + BOARD + ".openDrawer('IDEA')")
                drawer = page.get_by_role('complementary', name='Ideas get a home')
                give(page, drawer, 'alice')
                refusal = drawer.get_by_role('alert')
                expect(refusal).to_have_text('This story has no plan.', timeout=120000)
                assert not COMMAND.search(refusal.inner_text())
                expect(drawer.get_by_label('GitHub username')).to_be_focused()
                scan(page, 'refusal')
                # Escape closes the form first, back on its button; the next Escape closes the drawer.
                page.keyboard.press('Escape')
                expect(drawer.get_by_label('GitHub username')).to_have_count(0)
                expect(drawer.get_by_role('button', name='Assign')).to_be_focused()
                page.keyboard.press('Escape')
                expect(drawer).to_have_count(0)

                # Giving the story works from the keyboard, and the drawer then shows its new owner.
                page.evaluate("async () => " + BOARD + ".openDrawer('SHOP')")
                drawer = page.get_by_role('complementary', name='Shoppers can save a basket')
                give(page, drawer, 'alice')
                expect(drawer.get_by_text('Owner alice', exact=True)).to_be_visible(timeout=120000)
                expect(drawer.get_by_role('status')).to_have_text('Assigned the story to alice and published it.')
                expect(drawer.get_by_role('button', name='Assign')).to_be_focused()
                assert not COMMAND.search(drawer.inner_text()), drawer.inner_text()
                page.keyboard.press('Escape')
            # The story's full page carries the same control.
            page.evaluate("async () => " + BOARD + ".openItem('SHOP')")
            full = page.locator('main.item-page')
            expect(full.get_by_role('heading', level=1, name='Shoppers can save a basket')).to_be_visible()
            expect(full.get_by_text('Owner alice', exact=True)).to_be_visible()
            full.get_by_role('button', name='Assign').click()
            expect(full.get_by_label('GitHub username')).to_be_focused()
            scan(page, f'open form on the full page, {scheme}')
            page.close()
    finally:
        browser.close()
"""


@pytest.mark.timeout(400)
def test_19_a_manager_gives_a_story_from_the_board_and_a_teammate_sees_the_owner(client, tmp_path):
    teammate = clone(client, tmp_path)
    pushed(teammate, "Plan a basket and an idea", {
        "plans/SHOP.md": DOC,
        ".factory/stories/SHOP/story.json": json.dumps(
            {"doc": "plans/SHOP.md", "title": "Shoppers can save a basket", "status": "approved"}),
        "plans/IDEA.md": NO_PLAN,
        ".factory/stories/IDEA/story.json": json.dumps(
            {"doc": "plans/IDEA.md", "title": "Ideas get a home", "status": "draft"})})
    client.git("fetch", "-q", "origin")
    main = client.git("rev-parse", "origin/main")
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        assert {"SHOP", "IDEA"} <= {row["id"] for row in snapshot(url)["items"]}
        shown = subprocess.run([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                                "playwright==1.55.0", "--with", "axe-playwright-python==0.1.4", "python", "-c",
                                SCRIPT, url], capture_output=True, text=True, encoding="utf-8", timeout=300)
        assert shown.returncode == 0, shown.stdout + shown.stderr
    # The assignment is published on the story's branch; the refusal changed nothing.
    assert "Owner: alice" in client.git("show", "origin/story/SHOP:plans/SHOP.md")
    assert client.git("ls-remote", "origin", "story/IDEA") == ""
    assert client.git("rev-parse", "origin/main") == main
    teammate.git("fetch", "-q", "origin")
    assert rows(board(teammate))["SHOP"]["owner"] == "alice"
