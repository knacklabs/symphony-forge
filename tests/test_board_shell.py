"""`forge board`'s page shell in real Chrome: the live server serves the page, its styles and its
script under the run's token and the page's strict policy, the page shows the snapshot's updating
mark until the rebuild is done, and the pinned `Board` interfaces carry the server's snapshot."""
from __future__ import annotations

import json
import subprocess
from pathlib import PurePath

from conftest import REAL_UV
from test_board_server import client, commit, fix, get, live, snapshot  # noqa: F401

STORY = "FORGE-BOARD-4"

SCRIPT = r"""
import json, sys
from playwright.sync_api import expect, sync_playwright
url, expected = sys.argv[1], json.loads(sys.argv[2])
BOARD = "(await import(new URL('app.js' + location.search, location.href))).Board"
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        page = browser.new_page(viewport={'width': 1440, 'height': 900}, color_scheme='light')
        broken = []
        page.on('console', lambda m: 'Content Security Policy' in m.text and broken.append(m.text))
        page.on('pageerror', lambda e: broken.append(str(e)))
        page.goto(url)
        status = page.get_by_role('status')
        # The commit before the page opened is still being read: the last snapshot, marked as updating.
        expect(status).to_have_text('Updating')
        expect(status).to_have_text('Live', timeout=60000)
        assert expected['repo'] in page.locator('header').inner_text()
        # One crossing of the pinned interfaces: the snapshot the server serves reaches onSnapshot.
        seen = page.evaluate("async () => { const Board = " + BOARD + ''';
            const snapshot = await new Promise(resolve => Board.onSnapshot(resolve));
            const answer = await Board.api.assign('SHOP', 'page-dev');
            return {version: snapshot.snapshot.version, updating: !!snapshot.snapshot.updating,
                    ids: snapshot.items.map(item => item.id), answer,
                    stubs: ['select', 'openDrawer', 'openItem', 'navigate'].every(n => typeof Board[n] === 'function')}; }''')
        assert seen['version'] == expected['version'] + 1 and not seen['updating'], seen
        assert 'alpha' in seen['ids'] and seen['stubs'], seen
        assert seen['answer']['ok'] is False and seen['answer']['message'], seen
        assert 'forge ' not in seen['answer']['message'].lower(), seen
        # Board.navigate and the keyboard both move between pages, and the address keeps the page.
        page.evaluate("async () => " + BOARD + ".navigate('releases')")
        expect(page.get_by_role('link', name='Releases')).to_have_attribute('aria-current', 'page')
        assert page.url.endswith('#releases')
        for _ in range(10):
            page.keyboard.press('Tab')
            if page.evaluate('document.activeElement.textContent.trim()') == 'Insights':
                break
        assert page.evaluate("getComputedStyle(document.activeElement).outlineStyle") != 'none'
        page.keyboard.press('Enter')
        expect(page.get_by_role('link', name='Insights')).to_have_attribute('aria-current', 'page')
        expect(page.get_by_role('link', name='Releases')).not_to_have_attribute('aria-current', 'page')
        light = page.evaluate('getComputedStyle(document.body).backgroundColor')
        page.close()
        page = browser.new_page(viewport={'width': 1440, 'height': 900}, color_scheme='dark')
        page.goto(url)
        expect(page.get_by_role('status')).to_have_text('Live')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert page.evaluate('getComputedStyle(document.body).backgroundColor') != light
        page.close()
        assert not broken, broken
    finally:
        browser.close()
"""


def test_9_the_board_serves_its_page_shell_and_shows_when_it_is_updating(client):
    alpha = fix(client, "alpha")
    with live(client, FORGE_BOARD_REBUILD_WAIT="0", FORGE_BOARD_FETCH_WAIT="3600") as url:
        status, headers, page = get(url)
        assert status == 200 and "default-src 'none'" in headers["Content-Security-Policy"]
        for path, kind in (("/tokens.css", "text/css"), ("/app.js", "text/javascript")):
            status, headers, _ = get(url, path)
            assert status == 200 and headers["Content-Type"].startswith(kind), (path, status)
            assert get(url, path, False)[0] == 403
        assert get(url, "/../board_server.py")[0] == 404
        first = snapshot(url)
        commit(alpha, "alpha.txt")  # nothing reads the board until the page opens
        expected = {"version": first["snapshot"]["version"], "repo": PurePath(first["repo_root"]).name}
        shown = subprocess.run([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                                "playwright==1.55.0", "python", "-c", SCRIPT, url, json.dumps(expected)],
                               capture_output=True, text=True, encoding="utf-8", timeout=240)
        assert shown.returncode == 0, shown.stdout + shown.stderr
