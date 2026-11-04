"""An open plan survives changed snapshots, until the reader closes it.

Test audit: replacing native details loses reading state. Existing keyboard tests
restore focused links and miss reading without focus inside the fold. This uses
the real command, server and browser, with no new production test seam.
"""
import json
import os
import subprocess

import pytest

from conftest import REAL_UV
from test_board_item_page import PLAN
from test_board_item_keyboard_refresh import stop_tree
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
