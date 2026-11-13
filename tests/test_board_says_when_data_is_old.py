"""The board page says when its data is old, in real Chrome on `forge board`'s live page: one line under
the header gives the reason and the next step when the server has stopped, and a different line when the
server answers but cannot read the work; the line goes away by itself when data comes back.
The records are real; the server is stopped, or made to fail, the way a person would. Only the one
read that a test names is refused at the browser, to reach a state the real server cannot be put in.
The events stream, not a timer, tells the page that a rebuild failed; a page read that failed is asked again
after 10 seconds, so the test moves the page's clock on instead of waiting.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
from datetime import datetime, timedelta, timezone

import pytest

from conftest import REAL_UV
from test_board_item_keyboard_refresh import stop_tree
from test_board import DOC
from test_board_server import client, clone, fix, get, live, pushed  # noqa: F401

pytestmark = pytest.mark.platform

STORY = "fix-the-board-looks-live-when-its-data-is-ol"
# The browser gets its own budget, below pytest's, so a slow run fails here and stops every process
# it started, instead of pytest's timeout ending the worker before any cleanup runs.
BROWSER_SECONDS = 240

SCRIPT = r"""
import json, os, re, signal, subprocess, sys, time
from pathlib import Path
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import TimeoutError as PlaywrightTimeout, expect, sync_playwright
url, mode, pid, branch, item, marker = sys.argv[1:]
# The suite finds and ends a process that outlives a crashed worker by this record, which Windows needs.
Path(marker + '.tmp').write_text(json.dumps({'pid': os.getpid(), 'at_ns': time.time_ns()}), encoding='utf-8')
os.replace(marker + '.tmp', marker)
base, query = url.split('?')
query = '?' + query
NOW = re.compile(r'/board\.json\?token=[\w-]+$')  # the Now read; the other pages add &page=
STOPPED = 'The board has stopped, so this page may be old. Start the board again from the terminal, then open its new link.'
BOARD = "(await import(new URL('app.js' + location.search, location.href))).Board"
OPEN = f"async (id) => {BOARD}.openDrawer(id)"
UNREAD = 'The server could not read the work, so this page may be old. It said: \u201c'

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

        def until(page, condition):
            # Waits for something this script's own handlers do, without sleeping a fixed time.
            for _ in range(600):
                if condition():
                    return
                page.wait_for_timeout(100)
            raise AssertionError('timed out')

        def note(words):
            # Said on stderr, which the test prints when the run fails: where a slow or different machine got to.
            print(words, file=sys.stderr, flush=True)

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
            assert context.pages[-1].evaluate('document.documentElement.scrollWidth <= innerWidth')

        elif mode in ('failed', 'down'):
            # 'failed': nothing is blocked. The page keeps its events stream, and the server waits for a rebuild
            # as long as it does for everyone. 'down': the stream cannot connect while the server runs.
            page = context.new_page()
            full, asked = [], []  # reads of the whole board (the first included) and of the small status answer

            def counted(request):
                if NOW.search(request.url):
                    full.append(request.url)
                elif 'page=status' in request.url:
                    asked.append(request.url)

            page.on('request', counted)
            if mode == 'down':
                page.route(re.compile(r'/events'), lambda route: route.abort())
                with page.expect_response(re.compile(r'page=status')):
                    status, line = look(page)
            else:
                # The page is connected, and the status answer that the stream's opening asks has come back,
                # before anything fails: only a "failed" event can then tell the page.
                with page.expect_response(re.compile(r'/events')), page.expect_response(re.compile(r'page=status')):
                    status, line = look(page)
            expect(status).to_have_text('Live', timeout=60000)
            expect(line).to_be_hidden()
            held = lambda: page.evaluate(f"async () => {BOARD}.snapshot.snapshot.version")
            reads, probes, version = len(full), len(asked), held()
            context.clock.run_for(60000)  # a minute passes on the page's clock
            # Only a new snapshot makes the page read the whole board again.
            assert len(full) - reads <= held() - version, f'{len(full) - reads} reads of the whole board in a minute'
            good_branch = Path(branch).read_bytes()  # bytes both ways: no line ending is changed on Windows
            try:
                # A damaged branch pointer: git cannot say where the work is, so the board cannot read it.
                Path(branch).write_bytes(b'garbage\n')
                expect(line).to_contain_text(UNREAD, timeout=60000)
                if mode == 'failed':
                    assert (len(full), len(asked)) == (reads, probes), 'the page read the server after the failure began'
                else:
                    assert len(full) - reads <= held() - version, 'the page read the whole board while the work could not be read'
                # What the server says the failure is, asked after the check. Its status answer is immediate; a read
                # of the whole board may instead get the old snapshot marked updating while a slow rebuild runs.
                said = page.request.get(base + 'board.json' + query + '&page=status').json()['reason']
                assert said, 'the server does not say that a rebuild failed'
                expect(line).to_have_text(f'{UNREAD}{said}\u201d The page tries again.')
                assert 'offline' not in page.locator('body').inner_text().lower()
                expect(status).to_have_text('Not updating')
                assert not Axe().run(page, options={'runOnly': ['wcag2aa']}).response['violations']
                assert page.evaluate('document.querySelector(".bar").nextElementSibling === document.querySelector(".stale")')
            finally:
                Path(branch).write_bytes(good_branch)
            expect(line).to_be_hidden(timeout=60000)
            expect(status).to_have_text('Live')

        elif mode == 'late':
            # Two reads of the whole board begin, a rebuild then fails, and only afterwards the reads' answers
            # arrive: an answer marked updating, and an answer that is final but began before the failure.
            page = context.new_page()
            with page.expect_response(re.compile(r'/events')), page.expect_response(re.compile(r'page=status')):
                status, line = look(page)
            expect(status).to_have_text('Live', timeout=60000)
            good = page.evaluate(f"async () => {BOARD}.snapshot")
            number = good['snapshot']['version']
            answers = []  # the reads of the whole board that the page has begun and this script has not answered
            page.route(NOW, lambda route: answers.append(route))
            for name in ('late-a', 'late-b'):
                begun = len(answers)
                subprocess.run(['git', 'branch', name], cwd=Path(branch).parents[3], check=True, capture_output=True)  # a new snapshot
                until(page, lambda: len(answers) > begun)  # a slow machine may begin more than one read for a snapshot
                note(f'{name}: {len(answers)} reads of the whole board have begun')
            held = list(answers)  # only reads that began before the failure
            good_branch = Path(branch).read_bytes()  # bytes both ways: no line ending is changed on Windows
            try:
                Path(branch).write_bytes(b'garbage\n')
                expect(line).to_contain_text(UNREAD, timeout=60000)
                note('the line shows the failure')
                for route, extra in zip(held, [{'version': number + 1, 'updating': True}] + [{'version': number + 2}] * (len(held) - 1)):
                    route.fulfill(content_type='application/json', body=json.dumps(
                        {**good, 'snapshot': {**good['snapshot'], **extra}}))
                page.wait_for_function(f"async () => {BOARD}.snapshot.snapshot.version === {number + 2}")
                note('the page has taken both answers')
                expect(line).to_contain_text(UNREAD)
                expect(status).to_have_text('Not updating')
                page.unroute(NOW)
            finally:
                Path(branch).write_bytes(good_branch)
            expect(line).to_be_hidden(timeout=60000)
            expect(status).to_have_text('Live')

        elif mode == 'narrow':
            # Half a screen, short window, no line showing: Releases and Insights are as tall as what they hold and the
            # page scrolls, instead of keeping the height of a laptop window and squeezing their panels.
            page = context.new_page()
            page.set_viewport_size({'width': 768, 'height': 400})
            for name, path in (('releases', '#releases'), ('insights', '#insights')):
                status, line = look(page, path)
                expect(status).to_have_text('Live', timeout=60000)
                expect(line).to_be_hidden()
                expect(page.locator('.' + name)).to_be_visible(timeout=60000)
                held, height = page.evaluate(f'''() => {{ const page = document.querySelector('.{name}');
                    return [page.scrollHeight, page.getBoundingClientRect().height]; }}''')
                # Taller than its content leaves a gap, shorter squeezes the panels: the window is 400 pixels high.
                assert abs(held - height) <= 1, f'{name} is {height} pixels tall and holds {held}'
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), name + ' scrolls sideways'

        elif mode == 'items':
            # A story's page cannot be read; opening an older part, which is read separately, works.
            page = context.new_page()
            status, line = look(page)
            expect(status).to_have_text('Live', timeout=60000)
            page.route(re.compile(r'page=item&id=SHOP'), refuse)
            page.evaluate("location.hash = 'item/SHOP'")
            expect(line).to_have_text(f'{UNREAD}The work could not be read.\u201d The page tries again.')
            page.evaluate(OPEN, item)
            expect(page.get_by_role('complementary').locator('h2')).to_be_visible(timeout=60000)
            expect(line).to_contain_text(UNREAD)
            expect(status).to_have_text('Not updating')

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
            clear = '''() => document.querySelector('.drawer').getBoundingClientRect().top
                >= document.querySelector('.stale').getBoundingClientRect().bottom - 0.5'''
            # The drawer stays open as the window narrows: at 520 the header wraps to two rows and the line to more lines.
            for width in (768, 520):
                page.set_viewport_size({'width': width, 'height': 900})
                try:  # the page sizes itself once it has laid out for this width: wait for that fact, not for a time
                    page.wait_for_function(clear, polling=50, timeout=10000)
                except PlaywrightTimeout:
                    raise AssertionError(f'at {width} pixels the drawer covers the line')
                line = page.locator('.stale').bounding_box()
                assert page.evaluate('([x, y]) => document.elementFromPoint(x, y).closest(".stale") !== null',
                                     [line['x'] + line['width'] - 8, line['y'] + line['height'] / 2]), f'at {width} pixels the drawer covers the line'
    finally:
        browser.close()
"""


def look(url, mode, tmp_path, repo=None, item=""):
    """Open the page in real Chrome and run one scenario. Every browser run goes through here: the browser and
    everything it starts stop with the test, even when it fails or the run is too slow, and the script records
    its process so the suite also ends it when a worker crashes."""
    branch = (repo.path / ".git/refs/heads/main") if repo else ""
    page = subprocess.Popen([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with", "playwright==1.55.0",
                             "--with", "axe-playwright-python==0.1.8", "python", "-c", SCRIPT, url, mode,
                             str(url.process.pid), str(branch), item, str(tmp_path / "browser.owned-process.json")],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                            env={**os.environ, "PYTHONUTF8": "1"},  # Windows would write its messages in another encoding
                            start_new_session=os.name != "nt")  # its own process group, so a stop also ends the browser
    ran_out = threading.Timer(BROWSER_SECONDS, stop_tree, [page])
    ran_out.start()
    try:
        out, err = page.communicate()
        assert page.returncode == 0, f"{out or ''}{err or ''}"  # a stopped run on Windows can leave one of them None
    finally:
        ran_out.cancel()
        if page.poll() is None:
            stop_tree(page)
            page.wait(timeout=30)
        page.stdout.close()
        page.stderr.close()


@pytest.mark.timeout(BROWSER_SECONDS + 120)
def test_1_a_stopped_board_says_it_stopped_and_how_to_open_it_again(client, tmp_path):
    with live(client) as url:
        look(url, "stopped", tmp_path)


@pytest.mark.timeout(BROWSER_SECONDS + 120)
def test_2_a_failed_read_says_the_work_could_not_be_read_and_goes_away_with_new_data(client, tmp_path):
    with live(client, FORGE_BOARD_REBUILD_WAIT="0.5") as url:
        look(url, "failed", tmp_path, client)


@pytest.mark.timeout(BROWSER_SECONDS + 120)
def test_3_a_failed_read_on_another_page_shows_the_line_and_the_page_tries_again(client, tmp_path):
    with live(client) as url:
        look(url, "page", tmp_path)


@pytest.mark.timeout(BROWSER_SECONDS + 120)
def test_4_the_line_fits_on_every_board_screen_and_stays_clear_of_the_drawer(client, tmp_path):
    fix(client, "line-fits")
    with live(client) as url:
        look(url, "fits", tmp_path, item="line-fits")


@pytest.mark.timeout(BROWSER_SECONDS + 120)
def test_5_a_failed_read_shows_the_line_when_the_events_stream_is_down(client, tmp_path):
    with live(client, FORGE_BOARD_REBUILD_WAIT="0.5") as url:
        look(url, "down", tmp_path, client)


@pytest.mark.timeout(BROWSER_SECONDS + 120)
def test_6_a_successful_read_of_one_item_does_not_clear_the_failed_read_of_another(client, tmp_path, monkeypatch):
    # A story, and a fix that finished 9 days ago: the Now snapshot leaves it out, so opening it reads it.
    at = datetime.now(timezone.utc) - timedelta(days=9)
    with monkeypatch.context() as dated:
        dated.setenv("GIT_AUTHOR_DATE", at.isoformat())
        dated.setenv("GIT_COMMITTER_DATE", at.isoformat())
        pushed(clone(client, tmp_path), "Plan a basket and an old fix", {
            "plans/SHOP.md": DOC, "plans/roadmap.json": json.dumps({"items": [{"key": "SHOP"}]}),
            ".factory/fixes/old.json": json.dumps({"kind": "fix", "branch": "fix/old", "why": "Readers see old",
                                                   "done_when": "Readers see it", "status": "merged"})})
    client.git("fetch", "-q", "origin")
    client.git("merge", "-q", "--ff-only", "origin/main")
    with live(client) as url:
        look(url, "items", tmp_path, item="old")


@pytest.mark.timeout(BROWSER_SECONDS + 120)
def test_7_an_answer_that_began_before_a_failure_does_not_clear_it(client, tmp_path):
    with live(client, FORGE_BOARD_REBUILD_WAIT="0.5") as url:
        look(url, "late", tmp_path, client)


@pytest.mark.timeout(300)
def test_8_failures_that_come_and_go_cannot_fill_the_error_output_so_the_board_can_recover(client):
    # The board's error output can be a pipe that nobody reads (an agent's, or a test's). A Windows pipe holds about
    # four kilobytes. If printing a failure could fill it, the builder would block on its next failure, never rebuild,
    # and the page would show the failure for good. Six different failures in a row, each after a rebuild that worked,
    # must leave the output small and the board able to recover.
    branch = client.path / ".git/refs/heads/main"
    good = branch.read_bytes()
    with live(client) as url:
        assert get(url, "/board.json")[0] == 200
        for _ in range(6):
            try:
                branch.write_bytes(b"garbage\n")
                assert get(url, "/board.json")[0] == 500
            finally:
                branch.write_bytes(good)
            assert get(url, "/board.json")[0] == 200  # the board recovers each time
        url.process.terminate()
        url.process.wait(timeout=30)
        said = url.process.stderr.read()
        assert 0 < len(said) < 4096, f"the board wrote {len(said)} bytes of errors"


@pytest.mark.timeout(BROWSER_SECONDS + 120)
def test_9_half_a_screen_keeps_releases_and_insights_as_tall_as_what_they_hold(client, tmp_path):
    with live(client) as url:
        look(url, "narrow", tmp_path)
