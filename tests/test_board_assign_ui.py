"""A manager gives a story to a developer from the board. The Assign control in a story's drawer
and on its full page runs `forge assign` through the board's server; a refusal shows its reason
beside the control, in plain words with no command text, and changes nothing. A teammate's live
board shows the new owner once its own fetch brings the assignment. The real command, server and browser are all the test uses."""
from __future__ import annotations

import json
import subprocess
import sys

import pytest

from conftest import REAL_UV
from test_board import DOC
from test_board_server import client, clone, live, pushed, snapshot  # noqa: F401

STORY = "FORGE-BOARD-4"

NO_PLAN = """# Ideas get a home

## What changes for you

Ideas have one place to live.
"""

SCRIPT = r"""
import re, subprocess, sys
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright
url, mate, client, python, forge = sys.argv[1:]
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
                expect(refusal).to_have_text('This story has no plan. Plan it first, then assign it.', timeout=120000)
                assert not COMMAND.search(refusal.inner_text())
                expect(drawer.get_by_label('GitHub username')).to_be_focused()
                scan(page, 'refusal')
                # Escape closes the form first, back on its button; the next Escape closes the drawer.
                page.keyboard.press('Escape')
                expect(drawer.get_by_label('GitHub username')).to_have_count(0)
                expect(drawer.get_by_role('button', name='Assign')).to_be_focused()
                page.keyboard.press('Escape')
                expect(drawer).to_have_count(0)

                # A teammate's board is open on the story before it is given.
                theirs = browser.new_page(viewport={'width': 1440, 'height': 900})
                theirs.goto(mate)
                expect(theirs.get_by_role('status').first).to_have_text('Live', timeout=60000)
                theirs.evaluate("async () => " + BOARD + ".openDrawer('SHOP')")
                their_drawer = theirs.get_by_role('complementary', name='Shoppers can save a basket')
                expect(their_drawer.get_by_text('No owner yet', exact=True)).to_be_visible()
                # Giving the story works from the keyboard, and the drawer then shows its new owner.
                page.evaluate("async () => " + BOARD + ".openDrawer('SHOP')")
                drawer = page.get_by_role('complementary', name='Shoppers can save a basket')
                give(page, drawer, 'alice')
                expect(drawer.get_by_text('Owner alice', exact=True)).to_be_visible(timeout=120000)
                expect(drawer.get_by_role('status')).to_have_text('Assigned the story to alice and published it.')
                expect(drawer.get_by_role('button', name='Assign')).to_be_focused()
                assert not COMMAND.search(drawer.inner_text()), drawer.inner_text()
                page.keyboard.press('Escape')
                # The teammate's board shows the new owner after its own fetch and refresh.
                expect(their_drawer.get_by_text('Owner alice', exact=True)).to_be_visible(timeout=120000)
                theirs.close()
                # Two live redraws in a row while the manager types keep the keyboard in the field.
                give_button = drawer.get_by_role('button', name='Assign')
                give_button.focus()
                page.keyboard.press('Enter')
                field = drawer.get_by_label('GitHub username')
                for owner in ('carol', 'dave'):
                    expect(field).to_be_focused()
                    subprocess.run([python, forge, 'assign', 'SHOP', owner], cwd=client, check=True, capture_output=True)
                    expect(drawer.get_by_text('Owner ' + owner, exact=True)).to_be_visible(timeout=120000)
                    expect(field).to_be_focused()
                page.keyboard.press('Escape')
            # The story's full page carries the same control.
            page.evaluate("async () => " + BOARD + ".openItem('SHOP')")
            full = page.locator('main.item-page')
            expect(full.get_by_role('heading', level=1, name='Shoppers can save a basket')).to_be_visible()
            expect(full.get_by_text('Owner dave', exact=True)).to_be_visible()
            full.get_by_role('button', name='Assign').click()
            expect(full.get_by_label('GitHub username')).to_be_focused()
            scan(page, f'open form on the full page, {scheme}')
            if scheme == 'light':
                # A failed git step reads as plain words with a next step; the detail stays in the terminal.
                remote = subprocess.run(['git', 'remote', 'get-url', 'origin'], cwd=client, check=True,
                                        capture_output=True, text=True).stdout.strip()
                subprocess.run(['git', 'remote', 'set-url', 'origin', remote + '-gone'], cwd=client, check=True)
                try:
                    page.keyboard.type('bob')
                    page.keyboard.press('Enter')
                    refusal = full.get_by_role('alert')
                    expect(refusal).to_have_text('A git step failed. Check the network connection, then try again. '
                                                 'The terminal that runs the board shows the details.', timeout=120000)
                    assert not COMMAND.search(refusal.inner_text())
                finally:
                    subprocess.run(['git', 'remote', 'set-url', 'origin', remote], cwd=client, check=True)
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
    # The teammate's board fetches every few seconds, as a board does every minute.
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url, live(teammate, FORGE_BOARD_FETCH_WAIT="3") as mate:
        assert {"SHOP", "IDEA"} <= {row["id"] for row in snapshot(url)["items"]}
        shown = subprocess.run([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                                "playwright==1.55.0", "--with", "axe-playwright-python==0.1.4", "python", "-c",
                                SCRIPT, url, mate, str(client.path), sys.executable,
                                str(client.bin / "forge")], capture_output=True, text=True,
                               encoding="utf-8", timeout=300)
        assert shown.returncode == 0, shown.stdout + shown.stderr
    # The assignment is published on the story's branch; the refusal changed nothing.
    assert "Owner: dave" in client.git("show", "origin/story/SHOP:plans/SHOP.md")
    assert client.git("ls-remote", "origin", "story/IDEA") == ""
    assert client.git("rev-parse", "origin/main") == main
