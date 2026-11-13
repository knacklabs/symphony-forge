"""The board page says when its data is old, in real Chrome on `forge board`'s live page: one line under
the header gives the reason and the next step when the server has stopped, and a different line when the
server answers but cannot read the work; the line goes away by itself when data comes back.
The records are real; the server is stopped, or made to fail, the way a person would. Only the one
read that a test names is refused at the browser, to reach a state the real server cannot be put in.
The page asks again every 10 seconds, so the test moves the page's clock on instead of waiting.
"""
from __future__ import annotations

import os
import subprocess
import threading

import pytest

from conftest import REAL_UV
from test_board_item_keyboard_refresh import stop_tree
from test_board_server import client, fix, live  # noqa: F401

pytestmark = pytest.mark.platform

STORY = "fix-the-board-looks-live-when-its-data-is-ol"
# The browser gets its own budget, below pytest's, so a slow run fails here and stops every process
# it started, instead of pytest's timeout ending the worker before any cleanup runs.
BROWSER_SECONDS = 240

SCRIPT = r"""
import json, os, re, signal, sys
from pathlib import Path
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright
url, mode, pid, branch, item = sys.argv[1:]
base, query = url.split('?')
query = '?' + query
NOW = re.compile(r'/board\.json\?token=[\w-]+$')  # the Now read; the other pages add &page=
STOPPED = 'The board has stopped, so this page may be old. Start the board again from the terminal, then open its new link.'
OPEN = "async (id) => (await import(new URL('app.js' + location.search, location.href))).Board.openDrawer(id)"

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        context = browser.new_context(viewport={'width': 1440, 'height': 900}, color_scheme='dark')
        context.clock.install()  # time still runs; the test can also jump it past the page's 10 second wait

        def later(check):
            # The page asks again every 10 seconds: move its clock on until the check passes.
            for _ in range(20):
                context.clock.fast_forward(10000)
                try:
                    return check()
                except AssertionError:
                    pass
            check()

        def look(page, path=''):
            page.goto(url + path)
            return page.get_by_role('status'), page.locator('.stale')

        def refuse(route):
            route.fulfill(status=500, content_type='application/json', body=json.dumps({'error': 'The work could not be read.'}))

        if mode == 'stopped':
            status, line = look(context.new_page())
            expect(status).to_have_text('Live', timeout=60000)
            expect(line).to_be_hidden()
            os.kill(int(pid), signal.SIGTERM)
            expect(line).to_have_text(STOPPED, timeout=60000)
            expect(status).to_have_text('Offline')
            assert context.pages[0].evaluate('document.documentElement.scrollWidth <= innerWidth')

        elif mode == 'failed':
            # Nothing is blocked: the page keeps its events stream, which says nothing about a failed rebuild,
            # and the server waits for a rebuild as long as it does for everyone.
            page = context.new_page()
            status, line = look(page)
            expect(status).to_have_text('Live', timeout=60000)
            expect(line).to_be_hidden()
            good = page.evaluate("async () => (await import(new URL('app.js' + location.search, location.href))).Board.snapshot")
            good_branch = Path(branch).read_text(encoding='utf-8')
            try:
                # A damaged branch pointer: git cannot say where the work is, so the board cannot read it.
                Path(branch).write_text('garbage\n', encoding='utf-8')
                refused = page.request.get(base + 'board.json' + query)
                assert refused.status == 500, refused.text()
                expected = ('The server could not read the work, so this page may be old. '
                            f'It said: “{refused.json()["error"]}” The page tries again.')
                later(lambda: expect(line).to_have_text(expected, timeout=2000))
                assert 'offline' not in page.locator('body').inner_text().lower()
                expect(status).to_have_text('Not updating')
                assert not Axe().run(page, options={'runOnly': ['wcag2aa']}).response['violations']
                assert page.evaluate('document.querySelector(".bar").nextElementSibling === document.querySelector(".stale")')
                # The server answers while it rebuilds with the old snapshot marked as updating: no new data.
                page.route(NOW, lambda route: route.fulfill(content_type='application/json', body=json.dumps(
                    {**good, 'snapshot': {**good['snapshot'], 'updating': True}})))
                for _ in range(2):
                    with page.expect_request(NOW):
                        context.clock.fast_forward(10000)
                expect(line).to_have_text(expected)
                expect(status).to_have_text('Not updating')
                page.unroute(NOW)
            finally:
                Path(branch).write_text(good_branch, encoding='utf-8')
            later(lambda: expect(line).to_be_hidden(timeout=2000))
            expect(status).to_have_text('Live')

        elif mode == 'page':
            # The Now read is fine; only the Releases read is refused.
            page = context.new_page()
            status, line = look(page)
            expect(status).to_have_text('Live', timeout=60000)
            page.route(re.compile(r'page=releases'), refuse)
            page.get_by_role('link', name='Releases').click()
            expect(line).to_have_text('The server could not read the work, so this page may be old. '
                                      'It said: “The work could not be read.” The page tries again.')
            expect(status).to_have_text('Not updating')
            page.unroute(re.compile(r'page=releases'))
            later(lambda: expect(line).to_be_hidden(timeout=2000))
            expect(page.locator('.releases')).to_be_visible()
            expect(status).to_have_text('Live')

        else:  # 'fits': each changed screen with the line showing, and the drawer open at a narrow window
            screens = {'now': '', 'releases': '#releases', 'insights': '#insights', 'item': '#item/' + item}
            pages = {}
            for name, path in screens.items():
                pages[name] = context.new_page()
                look(pages[name], path)
            expect(pages['now'].get_by_role('status')).to_have_text('Live', timeout=60000)
            for name, shown in {'releases': '.releases', 'insights': '.insights', 'item': '.item-page h1'}.items():
                expect(pages[name].locator(shown)).to_be_visible(timeout=60000)
            os.kill(int(pid), signal.SIGTERM)
            for name, page in pages.items():
                expect(page.locator('.stale')).to_have_text(STOPPED, timeout=60000)
                for scheme in ('light', 'dark'):
                    page.emulate_media(color_scheme=scheme)
                    where = f'{name} {scheme}'
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), where + ' scrolls sideways'
                    assert page.evaluate('document.documentElement.scrollHeight <= innerHeight'), where + ' scrolls down'
                    assert not Axe().run(page, options={'runOnly': ['wcag2aa']}).response['violations'], where + ' contrast'
            page = pages['now']
            page.set_viewport_size({'width': 768, 'height': 900})
            page.evaluate(OPEN, item)
            drawer = page.get_by_role('complementary')
            expect(drawer).to_be_visible()
            line = page.locator('.stale').bounding_box()
            assert drawer.bounding_box()['y'] >= line['y'] + line['height'] - 0.5, 'the drawer covers the line'
            assert page.evaluate('([x, y]) => document.elementFromPoint(x, y).closest(".stale") !== null',
                                 [line['x'] + line['width'] - 8, line['y'] + line['height'] / 2]), 'the drawer covers the line'
    finally:
        browser.close()
"""


def look(url, mode, repo=None, item=""):
    """Open the page in real Chrome and run one scenario. The browser and everything it starts stop with
    the test, even when it fails or the run is too slow."""
    branch = (repo.path / ".git/refs/heads/main") if repo else ""
    page = subprocess.Popen([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with", "playwright==1.55.0",
                             "--with", "axe-playwright-python==0.1.8", "python", "-c", SCRIPT, url, mode,
                             str(url.process.pid), str(branch), item],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                            start_new_session=os.name != "nt")  # its own process group, so a stop also ends the browser
    ran_out = threading.Timer(BROWSER_SECONDS, stop_tree, [page])
    ran_out.start()
    try:
        out, err = page.communicate()
        assert page.returncode == 0, out + err
    finally:
        ran_out.cancel()
        if page.poll() is None:
            stop_tree(page)
            page.wait(timeout=30)
        page.stdout.close()
        page.stderr.close()


@pytest.mark.timeout(BROWSER_SECONDS + 120)
def test_1_a_stopped_board_says_it_stopped_and_how_to_open_it_again(client):
    with live(client) as url:
        look(url, "stopped")


@pytest.mark.timeout(BROWSER_SECONDS + 120)
def test_2_a_failed_read_says_the_work_could_not_be_read_and_goes_away_with_new_data(client):
    with live(client, FORGE_BOARD_REBUILD_WAIT="0.5") as url:
        look(url, "failed", client)


@pytest.mark.timeout(BROWSER_SECONDS + 120)
def test_3_a_failed_read_on_another_page_shows_the_line_and_the_page_tries_again(client):
    with live(client) as url:
        look(url, "page")


@pytest.mark.timeout(BROWSER_SECONDS + 120)
def test_4_the_line_fits_on_every_board_screen_and_stays_clear_of_the_drawer(client):
    fix(client, "line-fits")
    with live(client) as url:
        look(url, "fits", item="line-fits")
