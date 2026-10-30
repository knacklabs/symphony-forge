"""The drawer and item page styles change only those views, never the other board screens.

Their short class names (more, tag, close, figures, who) are common words another
screen may use. This loads the real board, adds one element per name outside the item views,
and compares it with the drawer's own copy after the item styles load. The probes sit
outside main, which the Now screen redraws on every live refresh.
"""
import json
import subprocess

from conftest import REAL_UV
from test_board_item_page import PLAN
from test_board_server import client, clone, live, pushed  # noqa: F401

STORY = "FIX-ITEM-FACTS"

SCRIPT = r"""
import sys
from playwright.sync_api import expect, sync_playwright
url = sys.argv[1]
BOARD = "(await import(new URL('app.js' + location.search, location.href))).Board"
NAMES = ['more', 'tag', 'close', 'figures', 'who']
LOOK = "e => { const s = getComputedStyle(e), a = getComputedStyle(e, '::after'); return [s.fontWeight, s.backgroundColor, s.display, a.content].join('|'); }"

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.goto(url)
        expect(page.get_by_role('status')).to_have_text('Live', timeout=60000)
        page.evaluate("names => { const box = document.createElement('div'); box.id = 'elsewhere'; "
                      "for (const name of names) { const e = document.createElement('a'); e.className = name; "
                      "e.textContent = name; box.append(e); } document.body.append(box); }", NAMES)
        plain = page.evaluate("() => { const e = document.createElement('a'); e.textContent = 'plain'; "
                              "document.getElementById('elsewhere').append(e); return (" + LOOK + ")(e); }")
        page.evaluate("async () => " + BOARD + ".openDrawer('SHOP')")
        drawer = page.get_by_role('complementary', name='Shoppers can save a basket')
        expect(drawer).to_be_visible()
        assert drawer.locator('.more').evaluate(LOOK) != plain, 'the drawer lost its own styles'
        for name in NAMES:
            assert page.locator('#elsewhere .' + name).evaluate(LOOK) == plain, name
        page.close()
    finally:
        browser.close()
"""


def test_18_item_styles_change_only_the_drawer_and_item_page(client, tmp_path):
    teammate = clone(client, tmp_path)
    pushed(teammate, "Plan a basket", {"plans/SHOP.md": PLAN, ".factory/stories/SHOP/story.json":
           json.dumps({"doc": "plans/SHOP.md", "title": "Shoppers can save a basket", "status": "approved"})})
    client.git("fetch", "-q", "origin")
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        shown = subprocess.run([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                                "playwright==1.55.0", "python", "-c", SCRIPT, url], capture_output=True,
                               text=True, encoding="utf-8", timeout=300)
        assert shown.returncode == 0, shown.stdout + shown.stderr
