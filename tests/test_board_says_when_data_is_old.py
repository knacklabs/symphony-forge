"""The board page says when its data is old, in real Chrome on `forge board`'s live page: one line under
the header gives the reason and the next step when the server has stopped, and a different line when the
server answers but cannot read the work; the line goes away by itself when data comes back.
The records are real; the server is stopped, or made to fail, the way a person would.
"""
from __future__ import annotations

import json
import subprocess

from conftest import REAL_UV
from test_board_server import client, get, live  # noqa: F401

import pytest

pytestmark = pytest.mark.platform

STORY = "fix-the-board-looks-live-when-its-data-is-ol"

# The page tells the test when it is ready for the next step; the test answers with the line to expect.
SCRIPT = r"""
import json, sys
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright
url, mode = sys.argv[1], sys.argv[2]

def step(name):
    print(name, flush=True)
    return json.loads(sys.stdin.readline())

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        page = browser.new_page(viewport={'width': 1440, 'height': 900}, color_scheme='dark')
        if mode == 'failed':
            # With the events stream down, the page asks again every 10 seconds, so it meets the failure.
            page.route('**/events*', lambda route: route.abort())
        page.goto(url)
        status = page.get_by_role('status')
        expect(status).to_have_text('Live', timeout=60000)
        line = page.locator('.stale')
        expect(line).to_be_hidden()
        expected = step('loaded')
        expect(page.get_by_text(expected, exact=True)).to_be_visible(timeout=60000)
        expect(line).to_have_text(expected)
        shown = page.locator('body').inner_text()
        if mode == 'failed':
            assert 'offline' not in shown.lower(), shown
            expect(status).to_have_text('Not updating')
            assert not Axe().run(page, options={'runOnly': ['wcag2aa']}).response['violations']
            assert page.evaluate('document.querySelector(".bar").nextElementSibling === document.querySelector(".stale")')
            step('shown')
            expect(line).to_be_hidden(timeout=60000)
            expect(status).to_have_text('Live')
        else:
            expect(status).to_have_text('Offline')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    finally:
        browser.close()
"""


def look(url, mode, act, restore=lambda: None):
    """Open the page, run `act` (it returns the line to expect), then `restore` once the line shows."""
    page = subprocess.Popen([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with", "playwright==1.55.0",
                             "--with", "axe-playwright-python==0.1.8", "python", "-c", SCRIPT, url, mode],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8")
    try:
        assert page.stdout.readline().strip() == "loaded", page.stderr.read()
        page.stdin.write(json.dumps(act()) + "\n")
        page.stdin.flush()
        if mode == "failed":
            assert page.stdout.readline().strip() == "shown", page.stderr.read()
            restore()
            page.stdin.write("null\n")
            page.stdin.flush()
        out, err = page.communicate(timeout=240)
        assert page.returncode == 0, out + err
    finally:
        page.kill()
        page.wait()


def test_1_a_stopped_board_says_it_stopped_and_how_to_open_it_again(client):
    with live(client) as url:
        def stop():
            url.process.terminate()
            url.process.wait(timeout=30)
            return ("The board has stopped, so this page may be old. "
                    "Start the board again from the terminal, then open its new link.")
        look(url, "stopped", stop)


def test_2_a_failed_read_says_the_work_could_not_be_read_and_goes_away_with_new_data(client):
    branch = client.path / ".git/refs/heads/main"
    good = branch.read_text(encoding="utf-8")
    with live(client) as url:
        def break_the_work():
            # A damaged branch pointer: git cannot say where the work is, so the board cannot read it.
            branch.write_text("garbage\n", encoding="utf-8")
            status, _, body = get(url, "/board.json")
            assert status == 500, body
            reason = json.loads(body)["error"]
            return f"The server could not read the work, so this page may be old. It said: “{reason}” The page tries again."
        try:
            look(url, "failed", break_the_work, lambda: branch.write_text(good, encoding="utf-8"))
        finally:
            branch.write_text(good, encoding="utf-8")
