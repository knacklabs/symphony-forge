"""`forge board`'s item detail in real Chrome: any item opens in a 480 px drawer beside the cards, and
its full page shows its history, rounds, kept problems and, for a story, its plan as a readable
document. The plan renders inertly: HTML shows as text and only http and https links stay links.
Every control works from the keyboard, the board's own words carry no commands, and axe finds no
violation in light or dark."""
from __future__ import annotations

import json
import subprocess

from conftest import REAL_UV
from test_board import DOC
from test_board_server import client, clone, fix, live, pushed, snapshot  # noqa: F401

STORY = "FORGE-BOARD-4"

# The story's plan, with an Owner line so its parts are on the board, a builders section to fold,
# and hostile markup that must stay inert text.
PLAN = DOC.replace("## Tasks\n", """## For the builders

Builders read [the guide](https://example.com/guide) first.
Hostile: <img src=x onerror="window.pwned=1"> and [run me](javascript:window.pwned=1).

## Tasks

Owner: page-dev
""", 1).replace("## Why\n", "## Why\n\n- Shoppers *lose* work\n- Support gets `calls`\n", 1).replace(
    "`src/share.py`", "`src/" + "share/" * 30 + "basket.py`", 1)  # a table wider than the page scrolls

SCRIPT = r"""
import json, re, sys
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright
url = sys.argv[1]
BOARD = "(await import(new URL('app.js' + location.search, location.href))).Board"
COMMAND = re.compile(r"\bforge [a-z]|--[a-z]|`")
axe = Axe()

def scan(page, where, context=None):
    found = axe.run(page, context=context).response['violations']
    assert not found, (where, [(v['id'], [n['target'] for n in v['nodes']]) for v in found])

def own_words(page):
    # Everything on screen except the rendered plan: no command text, and no gaps shown as code words.
    text = page.evaluate("[...document.body.querySelectorAll(':scope > *')].map(e => { const c = e.cloneNode(true); "
                         "c.querySelectorAll('.plan').forEach(p => p.remove()); return c.innerText; }).join('\\n')")
    assert not COMMAND.search(text), text
    assert not re.search(r"\b(null|undefined|NaN)\b", text), text

def tab_to(page, name):
    for _ in range(40):
        page.keyboard.press('Tab')
        if page.evaluate('document.activeElement.textContent.trim()').startswith(name):
            assert page.evaluate("getComputedStyle(document.activeElement).outlineStyle") != 'none'
            return
    raise AssertionError(f'Tab never reached {name}')

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        for scheme in ('light', 'dark'):
            page = browser.new_page(viewport={'width': 1440, 'height': 900}, color_scheme=scheme)
            broken = []
            page.on('console', lambda m: m.type == 'error' and 'status of 404' not in m.text and broken.append(m.text))  # the unknown item's own 404
            page.on('pageerror', lambda e: broken.append(str(e)))
            page.goto(url)
            expect(page.get_by_role('status')).to_have_text('Live', timeout=60000)

            # A fix opens in the drawer beside the cards, at 480 px, and Escape closes it.
            page.evaluate("async () => " + BOARD + ".openDrawer('alpha')")
            drawer = page.get_by_role('complementary', name='Readers see alpha')
            expect(drawer).to_be_visible()
            assert drawer.evaluate('e => e.offsetWidth') == 480
            expect(drawer).to_contain_text('Fix')
            own_words(page)
            scan(page, f'fix drawer, {scheme}', '.drawer')  # the Now screen under it is another part's
            page.keyboard.press('Escape')
            expect(drawer).to_have_count(0)

            # A part's drawer names its story, and its story's parts open from it.
            page.evaluate("async () => " + BOARD + ".openDrawer('SHOP/SAVE')")
            drawer = page.get_by_role('complementary', name='Save a basket')
            expect(drawer).to_contain_text('Part of Shoppers can save a basket')
            drawer.get_by_role('button', name=re.compile('^Share a basket')).click()
            drawer = page.get_by_role('complementary', name='Share a basket')
            expect(drawer).to_be_visible()

            # The keyboard walk: a story's drawer, its full page, its Plan tab, then back with Escape.
            page.evaluate("async () => " + BOARD + ".openDrawer('SHOP')")
            drawer = page.get_by_role('complementary', name='Shoppers can save a basket')
            expect(drawer).to_contain_text('page-dev')
            tab_to(page, 'Full history')
            page.keyboard.press('Enter')
            assert page.url.endswith('#item/SHOP'), page.url
            expect(page.get_by_role('heading', level=1, name='Shoppers can save a basket')).to_be_visible()
            tabs = page.get_by_role('tablist')
            expect(tabs.get_by_role('tab')).to_have_text(['Overview', 'Plan', 'Rounds', re.compile('^Known issues')])
            expect(tabs.get_by_role('tab', name='Overview')).to_have_attribute('aria-selected', 'true')
            expect(page.get_by_role('tabpanel')).to_contain_text('Save a basket')  # its parts
            own_words(page)
            scan(page, f'story overview, {scheme}')
            tab_to(page, 'Plan')
            page.keyboard.press('Enter')
            expect(tabs.get_by_role('tab', name='Plan')).to_have_attribute('aria-selected', 'true')
            plan = page.get_by_role('tabpanel')
            expect(plan.get_by_role('heading', name='What changes for you')).to_be_visible()
            expect(plan.locator('ol > li')).to_have_count(3)
            expect(plan.locator('ul > li')).to_have_count(2)
            expect(plan.locator('em')).to_have_text('lose')
            # The builders section is folded, and its hostile markup is plain text.
            builders = plan.locator('details')
            expect(builders).not_to_have_attribute('open', '')
            builders.locator('summary').click()
            expect(builders).to_contain_text('<img src=x onerror="window.pwned=1">')
            expect(builders.get_by_role('link', name='the guide')).to_have_attribute('href', 'https://example.com/guide')
            expect(builders.get_by_role('link', name='run me')).to_have_count(0)
            expect(builders).to_contain_text('[run me](javascript:window.pwned=1)')
            assert plan.locator('img').count() == 0
            assert page.evaluate('window.pwned') is None
            scan(page, f'story plan, {scheme}')
            for name in ('Rounds', 'Known issues'):
                tabs.get_by_role('tab', name=re.compile('^' + name)).click()
                expect(page.get_by_role('tabpanel')).to_be_visible()
                own_words(page)
            page.keyboard.press('Escape')
            expect(page.get_by_role('tablist')).to_have_count(0)
            assert page.url.endswith('#now'), page.url

            # A part's full page has no Plan tab; an unknown item says so in plain words.
            page.evaluate("async () => " + BOARD + ".openItem('SHOP/SAVE')")
            expect(page.get_by_role('heading', level=1, name='Save a basket')).to_be_visible()
            expect(page.get_by_role('tab')).to_have_text(['Overview', 'Rounds', re.compile('^Known issues')])
            page.evaluate("async () => " + BOARD + ".openItem('nothing-here')")
            expect(page.get_by_role('alert')).to_have_text(re.compile('No item by that name is on the board'))
            own_words(page)
            page.close()
            assert not broken, broken
    finally:
        browser.close()
"""


def test_11_an_item_opens_in_a_drawer_and_a_full_page_with_an_inert_plan(client, tmp_path):
    pushed(clone(client, tmp_path), "Plan a basket", {"plans/SHOP.md": PLAN, ".factory/stories/SHOP/story.json":
           json.dumps({"doc": "plans/SHOP.md", "title": "Shoppers can save a basket", "status": "approved"})})
    client.git("fetch", "-q", "origin")
    fix(client, "alpha")
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        rows = {row["id"] for parent in snapshot(url)["items"] for row in (parent, *parent["children"])}
        assert {"alpha", "SHOP", "SHOP/SAVE", "SHOP/SHARE"} <= rows, rows
        shown = subprocess.run([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                                "playwright==1.55.0", "--with", "axe-playwright-python==0.1.4", "python", "-c",
                                SCRIPT, url], capture_output=True, text=True, encoding="utf-8", timeout=300)
        assert shown.returncode == 0, shown.stdout + shown.stderr
