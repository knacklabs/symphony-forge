"""The board's item page keeps its open tab in the address, and Escape closes only the drawer.

A reload, a link, Back and Forward each show the tab the address names. Escape on a full item page
does nothing; Escape on a drawer closes it and, also after a refresh drew the cards again, puts the
keyboard focus back on the card that opened it.

Test audit: each Done-when item is one journey in real Chrome against the real `forge board` server,
on a new repo and on a repo adopted on an earlier release. The refresh in test 3 changes the board's own
answer at the browser's network edge, as the refresh tests do, so the card is drawn again for certain.
No production test seam.
"""
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
        # A link to a tab opens it, also on a page that was not open. A tab the item has not is Overview.
        other = browser.new_page(viewport={'width': 1440, 'height': 900})
        other.goto(url + '#item/SHOP?tab=known-issues')
        expect(other.get_by_role('tab', name=re.compile('^Known issues'))).to_have_attribute('aria-selected', 'true')
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
    finally:
        browser.close()
"""


@pytest.mark.timeout(300)
def test_2_escape_does_nothing_on_a_full_item_page_and_closes_only_the_drawer(client, gh, tmp_path):
    teammate = shop(client, gh, tmp_path, PLAN)
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        shown(ESCAPE, url, teammate, client)


FOCUS = r"""
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        later = []

        def snapshot(route):
            # The board's own answer for the first screen. Once the reader has opened the drawer, the part's
            # stage reads "reviewing", so the next refresh draws its card again.
            answer = route.fetch()
            body = answer.json()
            if later:
                for parent in body['items']:
                    for row in (parent, *parent['children']):
                        if row['id'] == 'SHOP/SAVE':
                            row['stage'] = 'reviewing'
            route.fulfill(response=answer, json=body)
        context.route(lambda address: '/board.json' in address and 'page=' not in address, snapshot)
        page = context.new_page()
        page.goto(url)
        expect(page.get_by_role('status')).to_have_text('Live', timeout=60000)
        card = page.locator('[data-focus="card:SHOP/SAVE"]')
        card.focus()
        page.keyboard.press('Enter')
        drawer = page.get_by_role('complementary', name='Save a basket')
        expect(drawer).to_be_visible()
        watch(page)
        page.evaluate('window.__card = document.querySelector(\'[data-focus="card:SHOP/SAVE"]\')')
        later.append(True)
        refresh(page, [])
        assert page.evaluate('!window.__card.isConnected'), 'the refresh did not draw the card again'
        page.keyboard.press('Escape')
        expect(drawer).to_have_count(0)
        expect(card).to_be_focused()
    finally:
        browser.close()
"""


@pytest.mark.timeout(300)
def test_3_after_a_refresh_escape_on_the_drawer_returns_focus_to_its_card(client, gh, tmp_path):
    teammate = shop(client, gh, tmp_path, PLAN)
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        shown(FOCUS, url, teammate, client)
