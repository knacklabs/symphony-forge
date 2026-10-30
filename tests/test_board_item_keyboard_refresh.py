"""Live item updates keep the keyboard on the same control in drawers and full pages.

The item journey checks keyboard navigation on a static snapshot. This regression changes
an owner's recorded assignment through git while a control has focus, then uses Enter.
It covers keyed controls and plain links: the breadcrumb, the pull request, and the plan's
fold and links, which load after the page redraws. Only GitHub's answers are fixtures.
"""
import json
import os
import signal
import subprocess
from types import SimpleNamespace

import pytest

from conftest import REAL_UV
from test_board_item_page import PLAN
from test_board_counts import github
from test_board_server import client, clone, live, pushed  # noqa: F401

pytestmark = pytest.mark.platform

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
        # Outside links stay on the board: Enter on one is proven by its request.
        page.route(re.compile(r'^https://'), lambda route: route.fulfill(status=204))
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
        page.get_by_role('tab', name='Plan', exact=True).click()
        update(page, full, full.locator('summary', has_text='For the builders'))
        expect(full.locator('details')).to_have_attribute('open', '')
        with page.expect_request('https://example.com/guide', timeout=120000):
            update(page, full, full.get_by_role('link', name='the guide'))
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
        page.keyboard.press('Escape')

        page.evaluate("async () => " + BOARD + ".openItem('SHOP/SAVE')")
        full = page.get_by_role('main').filter(has=page.get_by_role('heading', level=1, name='Save a basket'))
        with page.expect_request('https://github.com/shop/basket/pull/7', timeout=120000):
            update(page, full, full.get_by_role('link', name='Pull request 7'))
        update(page, full, page.get_by_role('navigation', name='Breadcrumb').get_by_role('link', name='Now'))
        expect(page).to_have_url(re.compile(r'#now$'))
        page.close()
    finally:
        browser.close()
assert not failures, failures
"""

# Eight live refreshes can take minutes on a loaded machine. The browser gets its own
# budget below pytest's, so a slow run fails with this message and every process stops,
# instead of pytest's timeout ending the worker before any cleanup runs.
BROWSER_SECONDS = 420


def stop_tree(process):
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True, timeout=30)
    else:
        os.killpg(process.pid, signal.SIGKILL)


@pytest.mark.timeout(BROWSER_SECONDS + 180)
def test_2_live_item_updates_keep_keyboard_focus_and_navigation(client, gh, tmp_path):
    teammate = clone(client, tmp_path)
    pushed(teammate, "Plan a basket", {"plans/SHOP.md": PLAN, ".factory/stories/SHOP/story.json":
           json.dumps({"doc": "plans/SHOP.md", "title": "Shoppers can save a basket", "status": "approved"})})
    teammate.git("switch", "-qc", "task/SHOP-SAVE")
    teammate.write(".factory/stories/SHOP/tasks/SAVE.json", json.dumps({
        "status": "waiting for checks", "branch": "task/SHOP-SAVE"}))
    teammate.git("add", "-A")
    teammate.git("commit", "-qm", "Save a basket")
    teammate.git("push", "-q", "origin", "task/SHOP-SAVE")
    github(SimpleNamespace(repo=client, gh=gh), [{"number": 7, "headRefName": "task/SHOP-SAVE",
        "headRefOid": teammate.git("rev-parse", "HEAD"), "state": "OPEN", "title": "Save a basket",
        "isDraft": False, "url": "https://github.com/shop/basket/pull/7", "body": ""}])
    teammate.git("switch", "-q", "main")
    client.git("fetch", "-q", "origin")
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        # Its own process group, so a stop also ends uv's Python and the browser it started.
        shown = subprocess.Popen([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                                  "playwright==1.55.0", "python", "-c", SCRIPT, url,
                                  str(teammate.path), str(client.path)], stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                 start_new_session=os.name != "nt")
        try:
            out, err = shown.communicate(timeout=BROWSER_SECONDS)
        except subprocess.TimeoutExpired:
            stop_tree(shown)
            out, err = shown.communicate(timeout=30)
            pytest.fail(f"The browser journey ran past {BROWSER_SECONDS} s and was stopped.\n{out}{err}")
        finally:
            if shown.poll() is None:
                stop_tree(shown)
                shown.wait(timeout=30)
        assert shown.returncode == 0, out + err
