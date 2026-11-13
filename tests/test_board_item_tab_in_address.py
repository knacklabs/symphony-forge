"""The board's item page keeps its open tab in the address, and Escape closes only the drawer.

A reload, a link, Back and Forward each show the tab the address names. Escape on a full item page
does nothing; Escape on a drawer closes only the drawer and, also after a refresh drew the list again,
puts the keyboard focus back on the card in the place that opened it.

Test audit: each Done-when item is one journey in real Chrome against the real `forge board` server,
on a new repo and on a repo adopted on an earlier release. Test 3 changes the board's data the real
way: a teammate's commit on a part's own branch records the owner's choice, so the part's ask goes. Only GitHub's
answers are fixtures. No production test seam.
"""
import json

import pytest

from test_board_plan_stays_open import shop, shown
from test_board_item_page import PLAN
from test_board_server import client, live  # noqa: F401

STORY = "FIX-ITEM-PAGE-KEEPS-ITS-TAB"
pytestmark = pytest.mark.platform

TABS = r"""
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        def tab(name):
            return page.get_by_role('tab', name=re.compile('^' + name))
        def on(name):
            expect(tab(name)).to_have_attribute('aria-selected', 'true')
        page.goto(url + '#item/SHOP')
        expect(page.get_by_role('status')).to_have_text('Live', timeout=60000)
        on('Overview')
        # A tab the reader picks is in the address, and a reload keeps it.
        tab('Plan').click()
        on('Plan')
        expect(page).to_have_url(re.compile(r'#item/SHOP\?tab=plan$'))
        page.reload()
        on('Plan')
        expect(page.get_by_role('tabpanel').get_by_role('heading', name='What changes for you')).to_be_visible()
        # Back and Forward return to the tab that was open.
        tab('Rounds').click()
        on('Rounds')
        page.go_back()
        on('Plan')
        page.go_back()
        on('Overview')
        page.go_forward()
        on('Plan')
        page.go_forward()
        on('Rounds')
        # A link to a tab opens it in a fresh browser tab that has never shown the Plan. A tab the item does
        # not have is Overview.
        fresh = browser.new_page(viewport={'width': 1440, 'height': 900})
        fresh.goto(url + '#item/SHOP?tab=plan')
        expect(fresh.get_by_role('tab', name='Plan')).to_have_attribute('aria-selected', 'true')
        expect(fresh.get_by_role('tabpanel').get_by_role('heading', name='What changes for you')).to_be_visible()
        other = browser.new_page(viewport={'width': 1440, 'height': 900})
        other.goto(url + '#item/SHOP/SAVE?tab=plan')
        expect(other.get_by_role('heading', level=1, name='Save a basket')).to_be_visible()
        expect(other.get_by_role('tab', name='Overview')).to_have_attribute('aria-selected', 'true')
        expect(other.get_by_role('tab', name='Plan')).to_have_count(0)
    finally:
        browser.close()
"""


@pytest.mark.timeout(300)
def test_1_a_reload_a_link_back_and_forward_show_the_tab_the_address_names(client, gh, tmp_path):
    teammate = shop(client, gh, tmp_path, PLAN)
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        shown(TABS, url, teammate, client)


# The plan with four more parts, so each ask has a title of its own.
FOUR = PLAN.replace("| SHOW |", "".join(
    f"| {part} | Choose {part} | {part} is chosen | 1 | `src/{part.lower()}.py` | `tests/test_{part.lower()}.py` | none | no |\n"
    for part in "ABCD") + "| SHOW |", 1)


def waiting_for_a_choice(client, gh, tmp_path):
    """The shop story, and four more parts under way that each stopped on a question for the owner. That is four
    asks: Needs you shows three, and the fourth is behind its "and 1 more" list."""
    teammate = shop(client, gh, tmp_path, FOUR)
    for number, part in enumerate("ABCD", 1):
        teammate.git("switch", "-qc", f"task/SHOP-{part}")
        teammate.write(f".factory/stories/SHOP/tasks/{part}.json", json.dumps({
            "status": "working", "branch": f"task/SHOP-{part}",
            "stop": {"at": f"2026-11-0{number}T09:00:00+00:00", "question": f"Part {part} needs a choice", "wait_id": part}}))
        teammate.git("add", "-A")
        teammate.git("commit", "-qm", f"Part {part}")
        teammate.git("push", "-q", "origin", f"task/SHOP-{part}")
        teammate.git("switch", "-q", "main")
    client.git("fetch", "-q", "origin")
    return teammate


ESCAPE = r"""
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.goto(url + '#item/SHOP')
        expect(page.get_by_role('status')).to_have_text('Live', timeout=60000)
        heading = page.get_by_role('heading', level=1, name='Shoppers can save a basket')
        expect(heading).to_be_visible()
        # This listener runs after the board's own, so it sees where the board's Escape left the address.
        page.evaluate("addEventListener('keydown', (e) => { if (e.key === 'Escape') window.__left = location.hash; })")
        page.keyboard.press('Escape')
        assert page.evaluate('window.__left') == '#item/SHOP', page.evaluate('window.__left')
        expect(heading).to_be_visible()
        # A drawer opened over the page closes alone: the page stays.
        page.get_by_role('tabpanel').get_by_role('button', name=re.compile('^Save a basket')).click()
        drawer = page.get_by_role('complementary', name='Save a basket')
        expect(drawer).to_be_visible()
        page.keyboard.press('Escape')
        expect(drawer).to_have_count(0)
        assert page.evaluate('window.__left') == '#item/SHOP', page.evaluate('window.__left')
        expect(heading).to_be_visible()
        # One Escape closes one thing: with a list and its drawer open, the drawer goes first, also when the
        # keyboard is back in the list.
        page.goto(url)
        page.get_by_role('region', name='Needs you').get_by_role('button', name=re.compile('^and 1 more')).click()
        dialog = page.get_by_role('dialog', name=re.compile('^Needs you, all'))
        entry = dialog.get_by_role('button', name=re.compile('^Decide')).first
        entry.focus()
        page.keyboard.press('Enter')
        drawer = page.locator('aside.drawer')
        expect(drawer).to_be_visible()
        entry.focus()
        page.keyboard.press('Escape')
        expect(drawer).to_have_count(0)
        expect(dialog).to_be_visible()
        page.keyboard.press('Escape')
        expect(dialog).to_have_count(0)
    finally:
        browser.close()
"""


@pytest.mark.timeout(300)
def test_2_escape_does_nothing_on_a_full_item_page_and_closes_only_the_drawer(client, gh, tmp_path):
    teammate = waiting_for_a_choice(client, gh, tmp_path)
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        shown(ESCAPE, url, teammate, client)


FOCUS = r"""
def advance(page, part):
    # A real change: the owner's choice is recorded on the part's own branch, so its ask goes. The board reads
    # it from the repo, and the page takes the new snapshot.
    before = page.evaluate('window.__version')
    git(teammate, 'switch', '-q', 'task/SHOP-' + part)
    Path(teammate, '.factory/stories/SHOP/tasks/' + part + '.json').write_text(
        json.dumps({'status': 'working', 'branch': 'task/SHOP-' + part,
                    'stop': {'at': '2026-11-01T09:00:00+00:00', 'question': 'A choice', 'wait_id': part, 'choice': 'more'}}),
        encoding='utf-8')
    for args in (['add', '-A'], ['commit', '-qm', 'Work on ' + part], ['push', '-q', 'origin', 'task/SHOP-' + part]):
        git(teammate, *args)
    git(teammate, 'switch', '-q', 'main')
    git(client, 'fetch', '-q', 'origin')
    page.wait_for_function('(n) => window.__version > n', arg=before, timeout=60000)
    page.evaluate('new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))')

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.goto(url)
        expect(page.get_by_role('status')).to_have_text('Live', timeout=60000)
        strip = page.get_by_role('region', name='Needs you')
        strip.get_by_role('button', name=re.compile('^and 1 more')).click()
        dialog = page.get_by_role('dialog', name=re.compile('^Needs you, all'))
        asks = dialog.get_by_role('button', name=re.compile('^Decide'))
        expect(asks).to_have_count(4)
        names = [asks.nth(n).inner_text() for n in range(4)]
        parts = [re.search(r'Choose ([A-D])', name)[1] for name in names]
        watch(page)
        # The second ask shows in the strip too. Open its drawer from the list; a teammate's change takes the
        # first ask away, so the list draws its buttons again. Escape puts focus on that ask in the list, not
        # on its copy in the strip.
        asks.nth(1).focus()
        page.keyboard.press('Enter')
        drawer = page.locator('aside.drawer')
        expect(drawer).to_be_visible()
        advance(page, parts[0])
        expect(asks).to_have_count(3)
        page.keyboard.press('Escape')
        expect(drawer).to_have_count(0)
        expect(dialog.get_by_role('button', name=names[1])).to_be_focused()
        # Open it again, then the part itself leaves the list. The list is still the place the reader came
        # from, so focus lands on a control in it, not on the page.
        dialog.get_by_role('button', name=names[1]).focus()
        page.keyboard.press('Enter')
        expect(drawer).to_be_visible()
        advance(page, parts[1])
        expect(dialog.get_by_role('button', name=names[1])).to_have_count(0)
        page.keyboard.press('Escape')
        expect(drawer).to_have_count(0)
        expect(dialog.locator(':focus')).to_have_count(1)
    finally:
        browser.close()
"""


@pytest.mark.timeout(480)
def test_3_after_a_refresh_escape_on_the_drawer_returns_focus_to_the_place_it_came_from(client, gh, tmp_path):
    teammate = waiting_for_a_choice(client, gh, tmp_path)
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        shown(FOCUS, url, teammate, client)
