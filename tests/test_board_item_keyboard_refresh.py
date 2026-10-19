"""Live item updates keep the keyboard on the same control in drawers and full pages.

The item journey checks keyboard navigation on a static snapshot. This regression changes
an owner's recorded assignment through git while a control has focus, then uses Enter.
"""
import json
import subprocess

from conftest import REAL_UV
from test_board_item_page import PLAN
from test_board_server import client, clone, live, pushed  # noqa: F401

STORY = "FIX-ITEM-FACTS"

SCRIPT = r"""
import re, subprocess, sys
from pathlib import Path
from playwright.sync_api import expect, sync_playwright
url, teammate, client = sys.argv[1:]
BOARD = "(await import(new URL('app.js' + location.search, location.href))).Board"
failures = []
revision = 0

def git(cwd, *args):
    subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True, encoding='utf-8')

def update(page, container, control):
    global revision
    revision += 1
    control.focus()
    expect(control).to_be_focused()
    # A real assignment lands and is fetched while the browser stays on the item.
    # Its changed owner proves the event stream refreshed this view before focus is checked.
    owner = 'keyboard-dev-' + str(revision)
    path = Path(teammate) / 'plans' / 'SHOP.md'
    path.write_text(re.sub(r'Owner: [^\n]+', 'Owner: ' + owner, path.read_text(encoding='utf-8')), encoding='utf-8')
    git(teammate, 'add', '-A')
    git(teammate, 'commit', '-qm', 'Assign the basket to ' + owner)
    git(teammate, 'push', '-q', 'origin', 'HEAD:main')
    git(client, 'fetch', '-q', 'origin')
    expect(container.get_by_text('Owner ' + owner, exact=True)).to_be_visible(timeout=60000)
    try:
        expect(control).to_be_focused(timeout=1000)
    except AssertionError as error:
        failures.append(str(error))
        # Keep checking the other refresh boundaries after recording this failure.
        control.focus()
    page.keyboard.press('Enter')

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.goto(url)
        expect(page.get_by_role('status')).to_have_text('Live', timeout=60000)
        page.evaluate("async () => " + BOARD + ".openDrawer('SHOP')")
        drawer = page.get_by_role('complementary', name='Shoppers can save a basket')
        expect(drawer).to_be_visible()
        update(page, drawer, drawer.get_by_role('link', name='Full history'))
        expect(page.get_by_role('heading', level=1, name='Shoppers can save a basket')).to_be_visible()
        expect(page).to_have_url(re.compile(r'#item/SHOP$'))

        full = page.get_by_role('main').filter(has=page.get_by_role('heading', level=1, name='Shoppers can save a basket'))
        update(page, full, page.get_by_role('tab', name='Rounds', exact=True))
        expect(page.get_by_role('tab', name='Rounds', exact=True)).to_have_attribute('aria-selected', 'true')
        expect(page.get_by_role('tabpanel').get_by_role('heading', name='Review rounds')).to_be_visible()
        page.get_by_role('tab', name='Overview', exact=True).click()
        update(page, full, full.get_by_role('button', name=re.compile('^Save a basket')))
        expect(page.get_by_role('complementary', name='Save a basket')).to_be_visible()
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')
        expect(page).to_have_url(re.compile(r'#now$'))

        page.evaluate("async () => " + BOARD + ".openDrawer('SHOP')")
        drawer = page.get_by_role('complementary', name='Shoppers can save a basket')
        expect(drawer).to_be_visible()
        update(page, drawer, drawer.get_by_role('button', name=re.compile('^Share a basket')))
        expect(page.get_by_role('complementary', name='Share a basket')).to_be_visible()
        page.close()
    finally:
        browser.close()
assert not failures, failures
"""


def test_2_live_item_updates_keep_keyboard_focus_and_navigation(client, tmp_path):
    teammate = clone(client, tmp_path)
    pushed(teammate, "Plan a basket", {"plans/SHOP.md": PLAN, ".factory/stories/SHOP/story.json":
           json.dumps({"doc": "plans/SHOP.md", "title": "Shoppers can save a basket", "status": "approved"})})
    client.git("fetch", "-q", "origin")
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        shown = subprocess.run([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                                "playwright==1.55.0", "python", "-c", SCRIPT, url,
                                str(teammate.path), str(client.path)], capture_output=True, text=True,
                               encoding="utf-8", timeout=300)
        assert shown.returncode == 0, shown.stdout + shown.stderr
