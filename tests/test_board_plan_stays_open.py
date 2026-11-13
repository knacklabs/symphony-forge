"""A board refresh leaves the reader's place alone. An open plan survives changed snapshots until the
reader closes it; a plan, the Releases page and the first screen keep their scroll, selection and
open sections through refreshes that change nothing they show.

Test audit: replacing native details loses reading state. Existing keyboard tests
restore focused links and miss reading without focus inside the fold. This uses
the real command, server and browser, with no new production test seam.
"""
import json
import os
import subprocess
from types import SimpleNamespace

import pytest

from conftest import REAL_UV
from test_board import DOC
from test_board_counts import github
from test_board_item_page import PLAN
from test_board_item_keyboard_refresh import stop_tree
from test_board_releases_known_issues_fit import FILES, KEPT
from test_board_server import client, clone, live, pushed  # noqa: F401

STORY = "FIX-BOARD-FOLD-STAYS-OPEN"
pytestmark = pytest.mark.platform

SCRIPT = r"""
import re, subprocess, sys
from pathlib import Path
from playwright.sync_api import expect, sync_playwright
url, teammate, client = sys.argv[1:]
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.goto(url + '#item/SHOP')
        page.get_by_role('tab', name='Plan', exact=True).click()
        fold = page.locator('article.plan details')
        expect(fold).not_to_have_attribute('open', '')
        for owner, opened in [('reader-one', True), ('reader-two', False)]:
            fold.locator('summary').click()
            page.get_by_role('tab', name='Plan', exact=True).focus()
            path = Path(teammate) / 'plans' / 'SHOP.md'
            path.write_text(re.sub(r'Owner: [^\n]+', 'Owner: ' + owner,
                                  path.read_text(encoding='utf-8')), encoding='utf-8')
            for cwd, args in [(teammate, ['add', '-A']), (teammate, ['commit', '-qm', 'Change owner']),
                              (teammate, ['push', '-q', 'origin', 'HEAD:main']), (client, ['fetch', '-q', 'origin'])]:
                subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True)
            expect(page.get_by_text('Owner ' + owner, exact=True)).to_be_visible(timeout=60000)
            expect(page.get_by_role('link', name='the guide', include_hidden=True)).to_have_count(1)
            if opened:
                expect(fold).to_have_attribute('open', '')
            else:
                expect(fold).not_to_have_attribute('open', '')
    finally:
        browser.close()
"""


@pytest.mark.timeout(240)
def test_1_open_builders_section_stays_open_until_person_closes_it(client, tmp_path):
    teammate = clone(client, tmp_path)
    pushed(teammate, "Plan a basket", {"plans/SHOP.md": PLAN, ".factory/stories/SHOP/story.json":
           json.dumps({"doc": "plans/SHOP.md", "title": "Shoppers can save a basket", "status": "approved"})})
    client.git("fetch", "-q", "origin")
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        shown = subprocess.Popen([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                                "playwright==1.55.0", "python", "-c", SCRIPT, url,
                                str(teammate.path), str(client.path)], stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                 start_new_session=os.name != "nt")
        try:
            out, err = shown.communicate(timeout=180)
        finally:
            if shown.poll() is None:
                stop_tree(shown)
                shown.communicate(timeout=30)
        assert shown.returncode == 0, out + err


# The refresh tests share one browser harness. A refresh is a teammate's commit that the board reads.
# It changes no file the board shows, so the page must keep everything the reader is doing.
PRELUDE = r"""
import re, subprocess, sys
from pathlib import Path
from playwright.sync_api import expect, sync_playwright
url, teammate, client = sys.argv[1:4]
step = 0

def git(cwd, *args):
    subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True, encoding='utf-8')

def watch(page):
    # Counts the board's snapshots and finished reads, and notes any loading line that shows.
    page.evaluate('''async () => {
      const { Board } = await import(new URL('app.js' + location.search, location.href));
      window.__version = 0; window.__reads = []; window.__loading = [];
      Board.onSnapshot((snapshot) => { window.__version = snapshot.snapshot.version; });
      new PerformanceObserver((list) => list.getEntries().forEach((e) => window.__reads.push(e.name))).observe({ type: 'resource' });
      new MutationObserver(() => {
        for (const one of document.querySelectorAll('.quiet, .note')) {
          if (/^Reading /.test(one.textContent)) window.__loading.push(one.textContent);
        }
      }).observe(document.body, { childList: true, subtree: true, characterData: true });
    }''')

def refresh(page, reads, files=None):
    # Lands one commit, then waits until the page has taken the new snapshot and drawn each answer it asked for.
    global step
    step += 1
    before, seen = page.evaluate('window.__version'), page.evaluate('window.__reads.length')
    for name, text in (files or {'notes.txt': 'note ' + str(step) + chr(10)}).items():
        Path(teammate, name).write_text(text, encoding='utf-8')
    for args in (['add', '-A'], ['commit', '-qm', 'Change ' + str(step)], ['push', '-q', 'origin', 'HEAD:main']):
        git(teammate, *args)
    git(client, 'fetch', '-q', 'origin')
    page.wait_for_function('(n) => window.__version > n', arg=before, timeout=60000)
    for name in reads:
        page.wait_for_function('([n, name]) => window.__reads.slice(n).some((u) => u.includes(name))', arg=[seen, name], timeout=60000)
    page.evaluate('new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))')

def stays(page, same, scrolls, open_sections, words=None):
    # The same elements, the same scroll, the open sections still open, the selection still selected.
    assert page.evaluate('(keys) => keys.every((key) => window[key] && window[key].isConnected)', same), 'an element was replaced'
    for selector, top in scrolls.items():
        now = page.evaluate('(s) => Math.round(s === "window" ? scrollY : document.querySelector(s).scrollTop)', selector)
        assert now == top, (selector, top, now)
    for selector in open_sections:
        expect(page.locator(selector)).to_have_attribute('open', '')
    if words is not None:
        assert page.evaluate('getSelection().toString()') == words, 'the selection changed'
    assert page.evaluate('window.__loading') == [], 'a loading line showed over the page'
"""


def shown(script, url, teammate, client):
    # Its own process group, so a stop also ends uv's Python and the browser it started.
    process = subprocess.Popen([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                                "playwright==1.55.0", "python", "-c", PRELUDE + script, url,
                                str(teammate.path), str(client.path)], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, encoding="utf-8",
                               start_new_session=os.name != "nt")
    try:
        out, err = process.communicate(timeout=300)
    finally:
        if process.poll() is None:
            stop_tree(process)
            process.communicate(timeout=30)
    assert process.returncode == 0, out + err


def story_json(title):
    return json.dumps({"doc": "plans/SHOP.md", "title": title, "status": "approved"})


def shop(client, gh, tmp_path, plan):
    """A story with one part under way, as a teammate planned and started it."""
    teammate = clone(client, tmp_path)
    pushed(teammate, "Plan a basket", {"plans/SHOP.md": plan,
                                       ".factory/stories/SHOP/story.json": story_json("Shoppers can save a basket")})
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
    return teammate


# A plan long enough to read far down, with a builders section that folds.
LONG = PLAN.replace("Hostile:", "\n\n".join(f"Builder note {n}. " + "It says what to build. " * 20 for n in range(1, 61))
                    + "\n\nHostile:", 1)

PLAN_PAGE = r"""
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.goto(url + '#item/SHOP')
        expect(page.get_by_role('status')).to_have_text('Live', timeout=60000)
        page.get_by_role('tab', name='Plan', exact=True).click()
        fold = page.locator('article.plan details')
        fold.locator('summary').click()
        expect(fold).to_have_attribute('open', '')
        watch(page)
        # Far down inside the builders section, with one paragraph of it selected.
        words = page.evaluate('''() => {
          const note = document.querySelectorAll('article.plan details p')[40];
          note.scrollIntoView({ block: 'start' });
          getSelection().selectAllChildren(note);
          window.__plan = document.querySelector('article.plan');
          window.__panel = document.querySelector('[role=tabpanel]');
          window.__fold = document.querySelector('article.plan details');
          return getSelection().toString();
        }''')
        top = page.evaluate('Math.round(scrollY)')
        assert top > 2000 and words.startswith('Builder note'), (top, words)
        same, folds = ['__plan', '__panel', '__fold'], ['article.plan details']
        for _ in range(3):
            refresh(page, ['plan/SHOP'])
            stays(page, same, {'window': top}, folds, words)
        # A real change: the plan names a new owner. The summary follows it and the plan is read again,
        # but the plan page, its tab and the open section stay where the reader left them.
        plan = Path(teammate, 'plans', 'SHOP.md')
        refresh(page, ['plan/SHOP'], {'plans/SHOP.md': re.sub('Owner: [^' + chr(10) + ']+', 'Owner: reader-one', plan.read_text(encoding='utf-8'))})
        expect(page.get_by_text('Owner reader-one', exact=True)).to_be_visible()
        stays(page, ['__plan', '__panel'], {'window': top}, folds)
    finally:
        browser.close()
"""


@pytest.mark.timeout(480)
def test_2_a_plan_keeps_its_scroll_selection_and_open_section_through_refreshes(client, gh, tmp_path):
    teammate = shop(client, gh, tmp_path, LONG)
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        shown(PLAN_PAGE, url, teammate, client)


OPENS = r"""
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        asked = []
        page.on('request', lambda request: asked.append(request.url))
        page.goto(url)
        expect(page.get_by_role('status')).to_have_text('Live', timeout=60000)
        watch(page)
        # From the first screen: a card opens the drawer, and its history link opens the full page.
        page.get_by_role('button', name=re.compile('^Save a basket')).first.click()
        page.get_by_role('link', name='Full history').click()
        expect(page.get_by_role('heading', level=1, name='Save a basket')).to_be_visible()
        assert not [one for one in asked if 'page=item' in one], 'the page asked the server for an item it already held'
        assert page.evaluate('window.__loading') == [], 'a loading line showed'
    finally:
        browser.close()
"""


@pytest.mark.timeout(300)
def test_3_the_full_item_page_opens_from_the_item_the_page_holds(client, gh, tmp_path):
    teammate = shop(client, gh, tmp_path, PLAN)
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        shown(OPENS, url, teammate, client)


RELEASES = r"""
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.goto(url + '#releases')
        expect(page.get_by_role('status')).to_have_text('Live', timeout=60000)
        kept = page.get_by_role('region', name='Known issues by file')
        expect(kept).to_be_visible()
        watch(page)
        kept.get_by_role('button', name=re.compile('^and \\d+ more')).click()
        full = page.get_by_role('dialog', name=re.compile('^Known issues by file, all'))
        expect(full).to_be_visible()
        # Far down the list of files, with one file open.
        page.evaluate('document.querySelector("section.known.list").scrollTop = 600')
        full.locator('summary').nth(14).click()
        selector = 'section.known.list li:nth-child(15) details'
        expect(page.locator(selector)).to_have_attribute('open', '')
        top = page.evaluate('Math.round(document.querySelector("section.known.list").scrollTop)')
        assert top > 0, top
        page.evaluate('''() => {
          window.__list = document.querySelector('section.known.list');
          window.__file = document.querySelector('section.known.list li:nth-child(15) details');
        }''')
        for _ in range(3):
            refresh(page, ['page=releases'])
            stays(page, ['__list', '__file'], {'section.known.list': top}, [selector])
    finally:
        browser.close()
"""


@pytest.mark.timeout(300)
def test_4_the_releases_page_keeps_its_open_file_and_scroll_through_refreshes(client, tmp_path):
    teammate = clone(client, tmp_path)
    pushed(teammate, "Add the parts and their kept problems", {
        **{file: "x = 1\n" for file in FILES},
        ".factory/fixes/old.json": json.dumps({"kind": "fix", "branch": "fix/old", "why": "Parts are slow",
                                               "done_when": "Parts are fast", "status": "merged", "known": KEPT})})
    client.git("fetch", "-q", "origin")
    client.git("merge", "-q", "--ff-only", "origin/main")
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        shown(RELEASES, url, teammate, client)


# A story with thirty parts nobody started, so Planned is a long list on the first screen.
MANY = DOC.replace("## Tasks\n", "## Tasks\n\nOwner: page-dev\n", 1)
MANY = MANY[:MANY.index("| SAVE |")] + "\n".join(
    f"| T{n:02} | Part {n} | Delivers {n} | 1 | `src/t{n}.py` | `tests/test_t{n}.py` | none | no |"
    for n in range(1, 31)) + "\n" + MANY[MANY.index("\nNew moving parts"):]

FIRST_SCREEN = r"""
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.goto(url)
        expect(page.get_by_role('status')).to_have_text('Live', timeout=60000)
        watch(page)
        page.get_by_role('region', name='Planned').get_by_role('button', name=re.compile('^and \\d+ more')).click()
        full = page.get_by_role('dialog', name=re.compile('^Planned, all'))
        expect(full).to_be_visible()
        page.evaluate('document.querySelector(".now .list ul").scrollTop = 500')
        top = page.evaluate('Math.round(document.querySelector(".now .list ul").scrollTop)')
        assert top > 0, top
        page.evaluate('window.__now = document.querySelector(".now"); window.__list = document.querySelector(".now .list ul")')
        for _ in range(3):
            refresh(page, [])
            stays(page, ['__now', '__list'], {'.now .list ul': top}, [])
    finally:
        browser.close()
"""


@pytest.mark.timeout(300)
def test_5_the_first_screen_keeps_the_scroll_of_its_long_list_through_refreshes(client, tmp_path):
    teammate = clone(client, tmp_path)
    pushed(teammate, "Plan thirty parts", {"plans/SHOP.md": MANY, ".factory/stories/SHOP/story.json":
                                           story_json("Shoppers can save a basket")})
    client.git("fetch", "-q", "origin")
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        shown(FIRST_SCREEN, url, teammate, client)
