"""The board reads at half a screen. In real Chrome at 768 pixels wide, on a new and an earlier-adopted
repo: the five stages are wide enough for a card title, the Stories rail sits under the stages, a
story's summary stacks above its plan, the plan is at least 600 pixels wide, its tasks table uses the
full sheet, a sub-section heading is smaller than a section heading, the "For the builders" line looks
like a heading, no page scrolls sideways, and every control is at least 24 pixels high. Real command,
server and browser; only GitHub is a stub. The test starts its own processes and stops them."""
import json
import os
import subprocess

import pytest

from conftest import REAL_UV
from test_board_item_keyboard_refresh import stop_tree
from test_board_item_page import PLAN
from test_board_releases_known_issues_fit import FILES, KEPT
from test_board_server import client, clone, live, pushed  # noqa: F401

STORY = "FIX-BOARD-HALF-SCREEN"
pytestmark = pytest.mark.platform

# The plan gets a sub-section under "Why", so there is a section and a sub-section heading to compare.
HALF_PLAN = PLAN.replace("People lose their basket when they leave.\n",
                         "People lose their basket when they leave.\n\n### Who loses work\n\nShoppers on phones.\n", 1)

SCRIPT = r"""
import json, sys
from playwright.sync_api import expect, sync_playwright
url = sys.argv[1]
BOARD = "(await import(new URL('app.js' + location.search, location.href))).Board"

CONTROLS = '''() => [...document.querySelectorAll('a[href], button, summary, [role=tab], [tabindex="0"]')]
  .filter((e) => e.getClientRects().length && getComputedStyle(e).visibility === 'visible')
  .filter((e) => !e.matches('.plan a'))  // a link inside a sentence is exempt from the target size
  .map((e) => [e.textContent.trim().slice(0, 30), e.getBoundingClientRect().height])
  .filter(([, height]) => height < 24)'''

def box(page, selector):
    return page.locator(selector).first.evaluate('e => { const r = e.getBoundingClientRect(); '
        'return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width }; }')

def no_sideways_scroll(page, where):
    width = page.evaluate('[document.documentElement.scrollWidth, innerWidth]')
    assert width[0] == width[1], (where, width)

def small_controls(page, where):
    assert page.evaluate(CONTROLS) == [], (where, page.evaluate(CONTROLS))

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        for scheme in ('light', 'dark'):
            page = browser.new_page(viewport={'width': 768, 'height': 1024}, color_scheme=scheme)
            page.set_default_timeout(30000)

            # The first screen: five stages with room for a title, the rail under them.
            page.goto(url)
            expect(page.get_by_role('status')).to_have_text('Live')
            expect(page.locator('.stage')).to_have_count(5)
            for stage in page.locator('.stage').all():
                assert stage.bounding_box()['width'] >= 180, (scheme, stage.bounding_box())
            assert page.locator('.chip-title').first.evaluate('e => e.clientWidth') >= 150
            assert box(page, '.rail')['top'] >= max(s.bounding_box()['y'] + s.bounding_box()['height']
                                                    for s in page.locator('.stage').all()), scheme
            no_sideways_scroll(page, (scheme, 'now'))
            small_controls(page, (scheme, 'now'))

            # A story's full page: the summary above the plan, a table as wide as the sheet.
            page.goto(url + '#item/SHOP')
            page.get_by_role('tab', name='Plan', exact=True).click()
            plan = page.locator('article.plan')
            expect(plan.get_by_role('heading', name='Who loses work')).to_be_visible()
            assert box(page, '.summary')['bottom'] <= box(page, '.sheet')['top'], scheme
            assert box(page, '.plan')['width'] >= 600, (scheme, box(page, '.plan'))
            fold = plan.locator('details')
            fold.locator('summary').click()
            expect(fold.get_by_role('table')).to_be_visible()
            sheet, table = box(page, '.sheet'), box(page, '.plan .table')
            assert sheet['left'] <= table['left'] and table['right'] <= sheet['right'], (scheme, sheet, table)
            assert table['width'] >= 0.85 * sheet['width'], (scheme, sheet, table)
            size = lambda sel: float(plan.locator(sel).first.evaluate('e => getComputedStyle(e).fontSize').removesuffix('px'))
            assert size('h4') < size('h3'), (scheme, size('h4'), size('h3'))
            look = 'e => { const s = getComputedStyle(e); return [s.fontSize, s.fontWeight, s.color].join(); }'
            assert fold.locator('summary').evaluate(look) == plan.locator('h3').first.evaluate(look), scheme
            no_sideways_scroll(page, (scheme, 'plan'))
            small_controls(page, (scheme, 'item page'))

            # The drawer fits the window and its controls are tall enough.
            page.goto(url)
            page.evaluate("async () => " + BOARD + ".openDrawer('SHOP')")
            drawer = page.get_by_role('complementary', name='Shoppers can save a basket')
            expect(drawer).to_be_visible()
            assert box(page, '.drawer')['left'] >= 0
            small_controls(page, (scheme, 'drawer'))

            # Releases and Insights: no sideways scroll, tall controls.
            for name in ('releases', 'insights'):
                page.goto(url + '#' + name)
                expect(page.locator('.' + name)).to_be_visible()
                no_sideways_scroll(page, (scheme, name))
                small_controls(page, (scheme, name))
            page.close()
    finally:
        browser.close()
"""


def test_1_the_board_reads_at_half_a_screen(client, tmp_path):
    fixes = {f".factory/fixes/build-{n}.json": json.dumps({
        "kind": "fix", "branch": f"fix/build-{n}", "why": f"Readers can open the long titled fix number {n}",
        "done_when": "Parts are fast", "status": "working"}) for n in range(6)}
    fixes[".factory/fixes/old.json"] = json.dumps({"kind": "fix", "branch": "fix/old", "why": "Parts are slow",
                                                   "done_when": "Parts are fast", "status": "merged", "known": KEPT})
    pushed(clone(client, tmp_path), "Plan a basket and add work", {
        "plans/SHOP.md": HALF_PLAN, ".factory/stories/SHOP/story.json":
        json.dumps({"doc": "plans/SHOP.md", "title": "Shoppers can save a basket", "status": "approved"}),
        **{file: "x = 1\n" for file in FILES}, **fixes})
    client.git("fetch", "-q", "origin")
    client.git("merge", "-q", "--ff-only", "origin/main")
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        shown = subprocess.Popen([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                                  "playwright==1.55.0", "python", "-c", SCRIPT, url],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                 start_new_session=os.name != "nt")
        try:
            out, err = shown.communicate(timeout=240)
        finally:
            if shown.poll() is None:
                stop_tree(shown)
                shown.communicate(timeout=30)
        assert shown.returncode == 0, out + err
