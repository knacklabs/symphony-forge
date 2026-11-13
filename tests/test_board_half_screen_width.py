"""The board reads at half a screen. In real Chrome, on a new and an earlier-adopted repo, on a long plan
with a wide table, long code in a list and in prose, and a word longer than the page: below 1,100 pixels
the five stages are wide enough for a card title, the Stories rail sits under them and a story's summary
stacks above its plan; from 1,100 pixels the summary stands beside a plan that is at least 600 pixels
wide. The plan's tasks table is inside the sheet and as wide as it, no screen scrolls sideways, every
control (links in a plan too, the Assign form, the full lists and each tab) is at least 24 pixels high,
and the Close buttons show a pressed state. Real command, server and browser; only GitHub is a stub.
The test starts its own processes and stops them."""
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

# Code and words that are longer than a half-screen page, in the visible plan and under "For the builders".
CODE = "test_" + "_".join(["the_board_reads"] * 7)
WORD = "Supercali" + "fragilistic" * 12
HALF_PLAN = PLAN.replace(
    "People lose their basket when they leave.\n",
    "People lose their basket when they leave. See [the basket guide](https://example.com/basket) first.\n\n"
    f"### Who loses work\n\nShoppers on phones, and {WORD}.\n\n- Support runs `{CODE}`\n", 1).replace(
    "## Tasks\n", f"- Builders run `{CODE}`\n\n{WORD}\n\n## Tasks\n", 1)

SCRIPT = r"""
import json, re, sys
from playwright.sync_api import expect, sync_playwright
url = sys.argv[1]

CONTROLS = '''() => [...document.querySelectorAll('a[href], button, input, select, textarea, summary, [role=tab], [tabindex="0"]')]
  .filter((e) => e.getClientRects().length && getComputedStyle(e).visibility === 'visible')
  .map((e) => [(e.textContent || e.name || e.type).trim().slice(0, 30), e.getBoundingClientRect().height])
  .filter(([, height]) => height < 24)'''

def box(page, selector):
    return page.locator(selector).first.evaluate('e => { const r = e.getBoundingClientRect(); '
        'return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width }; }')

def check(page, where):
    width = page.evaluate('[document.documentElement.scrollWidth, innerWidth]')
    wide = page.evaluate('''() => [...document.querySelectorAll('body *')].filter((e) => e.getBoundingClientRect().right > innerWidth + 0.5)
      .map((e) => e.tagName + '.' + e.className).slice(0, 5)''')
    assert width[0] == width[1], (where, 'the page scrolls sideways', width, wide)
    assert page.evaluate(CONTROLS) == [], (where, 'a control is under 24 pixels', page.evaluate(CONTROLS))

def pressed(page, button, where):
    # While the mouse is down the button shows its pressed state; moving away first cancels the click.
    spot = button.bounding_box()
    page.mouse.move(spot['x'] + spot['width'] / 2, spot['y'] + spot['height'] / 2)
    page.mouse.down()
    page.evaluate('Promise.all(document.getAnimations().map(a => a.finished))')
    assert button.evaluate('e => getComputedStyle(e).transform') != 'none', (where, 'no pressed state')
    page.mouse.move(1, 1)
    page.mouse.up()

def story_page(page, where, width):
    page.goto(url + '#item/SHOP')
    summary_above = lambda: box(page, '.summary')['bottom'] <= box(page, '.sheet')['top']
    for tab in ('Overview', 'Plan', 'Rounds', 'Known issues'):
        page.get_by_role('tab', name=re.compile('^' + tab)).click()
        expect(page.get_by_role('tabpanel')).to_be_visible()
        if tab == 'Plan':
            plan = page.locator('article.plan')
            expect(plan.get_by_role('heading', name='Who loses work')).to_be_visible()
            fold = plan.locator('details')
            fold.locator('summary').click()
            expect(fold.get_by_role('table')).to_be_visible()
            sheet, table = box(page, '.sheet'), box(page, '.plan table')
            assert sheet['left'] <= table['left'] and table['right'] <= sheet['right'], (where, sheet, table)
            assert table['width'] >= 0.85 * sheet['width'], (where, sheet, table)
            assert box(page, '.plan')['width'] >= (600 if width >= 768 else 0), (where, box(page, '.plan'))
            size = lambda sel: float(plan.locator(sel).first.evaluate('e => getComputedStyle(e).fontSize').removesuffix('px'))
            assert size('h4') < size('h3'), (where, size('h4'), size('h3'))
            look = 'e => { const s = getComputedStyle(e); return [s.fontSize, s.fontWeight, s.color].join(); }'
            assert fold.locator('summary').evaluate(look) == plan.locator('h3').first.evaluate(look), where
        check(page, (where, tab))
        assert summary_above() == (width < 1100), (where, tab, 'summary and plan are in the wrong places')

def now_screen(page, where, width):
    page.goto(url)
    expect(page.locator('.stage')).to_have_count(5)
    stages = [s.bounding_box() for s in page.locator('.stage').all()]
    if width < 1100:
        assert all(s['width'] >= 180 for s in stages), (where, stages)
        assert page.locator('.chip-title').first.evaluate('e => e.clientWidth') >= 150
        assert box(page, '.rail')['top'] >= max(s['y'] + s['height'] for s in stages), where
    check(page, (where, 'now'))
    # The user's way to the drawer: the story's own row in the rail.
    page.get_by_role('button', name='Shoppers can save a basket').click()
    drawer = page.get_by_role('complementary', name='Shoppers can save a basket')
    expect(drawer).to_be_visible()
    page.evaluate('Promise.all(document.getAnimations().map(a => a.finished))')
    assert box(page, '.drawer')['left'] >= 0, where
    check(page, (where, 'drawer'))
    drawer.get_by_role('button', name='Assign').click()
    expect(drawer.get_by_label('GitHub username')).to_be_visible()
    check(page, (where, 'assign form'))
    page.keyboard.press('Escape')
    pressed(page, drawer.get_by_role('button', name='Close'), (where, 'drawer close'))
    drawer.get_by_role('button', name='Close').click()
    expect(drawer).to_be_hidden()
    # The full list behind "and N more".
    page.locator('.stage .now-more').first.click()
    close = page.locator('.now-close')
    expect(close).to_be_visible()
    check(page, (where, 'full list'))
    pressed(page, close, (where, 'list close'))
    close.click()

def releases_and_insights(page, where):
    page.goto(url + '#releases')
    more = page.get_by_role('region', name='Known issues by file').get_by_role('button', name=re.compile(r'^and \d+ more'))
    more.click()
    full = page.get_by_role('dialog', name=re.compile('^Known issues by file, all'))
    expect(full).to_be_visible()
    check(page, (where, 'releases full list'))
    pressed(page, full.get_by_role('button', name='Close'), (where, 'releases close'))
    full.get_by_role('button', name='Close').click()
    expect(full).to_be_hidden()
    check(page, (where, 'releases'))
    page.goto(url + '#insights')
    expect(page.locator('.insights')).to_be_visible()
    check(page, (where, 'insights'))

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        for width, scheme in ((768, 'light'), (768, 'dark'), (600, 'light'), (1000, 'light'), (1099, 'light'), (1100, 'light')):
            where = (width, scheme)
            page = browser.new_page(viewport={'width': width, 'height': 1024}, color_scheme=scheme)
            page.set_default_timeout(30000)
            page.goto(url)
            expect(page.get_by_role('status')).to_have_text('Live')
            now_screen(page, where, width)
            story_page(page, where, width)
            # A fix with a pull request: the link in its facts is a control too.
            page.goto(url + '#item/build-0')
            expect(page.get_by_role('link', name='Pull request 7')).to_be_visible()
            check(page, (where, 'pull request'))
            releases_and_insights(page, where)
            page.close()
    finally:
        browser.close()
"""


def test_1_the_board_reads_at_half_a_screen(client, gh, tmp_path):
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
    gh.respond("pr", "list", stdout=json.dumps([{
        "number": 7, "headRefName": "fix/build-0", "state": "OPEN", "title": "Open the long titled fix",
        "body": "", "isDraft": False, "url": "https://github.com/acme/shop/pull/7"}]))
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        shown = subprocess.Popen([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                                  "playwright==1.55.0", "python", "-c", SCRIPT, url],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                 start_new_session=os.name != "nt")
        try:
            out, err = shown.communicate(timeout=360)
        finally:
            if shown.poll() is None:
                stop_tree(shown)
                shown.communicate(timeout=30)
        assert shown.returncode == 0, out + err
