"""`forge board`'s Releases page keeps its known issues to one laptop screen: at 1440x900 it shows the
10 files with the most kept problems, then an "and N more" button that opens all of them in the
drawer area, closes with Escape and gives focus back. Files gone from the default branch are left
out. Real Chrome on a new and an earlier-adopted repo; only GitHub is a stub."""
from __future__ import annotations

import json
import subprocess

from conftest import REAL_UV
from test_board_server import client, clone, live, pushed  # noqa: F401

STORY = "FIX-RELEASES-KNOWN-ISSUES-CAP"

# File n has n kept problems, so the order is fixed; the deleted file has the most of all.
FILES = [f"src/part{n:02}.py" for n in range(1, 41)]
GONE = "src/gone.py"
KEPT = [{"outcome": "follow-up", "file": file, "line": line, "title": f"Problem {line} in {file}",
         "gain": 1, "work": 1, "harm": 1}
        for n, file in enumerate([*FILES, GONE], 1) for line in range(1, (n if file != GONE else 50) + 1)]

FITS = r"""
import json, sys
from playwright.sync_api import expect, sync_playwright
from axe_playwright_python.sync_playwright import Axe
url, files, gone = sys.argv[1], json.loads(sys.argv[2]), sys.argv[3]
top = list(reversed(files))  # the file with most kept problems first

def settled(page):
    page.evaluate('Promise.all(document.getAnimations().map(a => a.finished))')

def clean(page, why):
    settled(page)
    found = Axe().run(page).response['violations']
    assert not found, (why, [(v['id'], v['nodes'][0]['target']) for v in found])

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        for scheme in ('light', 'dark'):
            page = browser.new_page(viewport={'width': 1440, 'height': 900}, color_scheme=scheme)
            page.set_default_timeout(30000)
            page.goto(url + '#releases')
            expect(page.get_by_role('status')).to_have_text('Live')
            kept = page.get_by_role('region', name='Known issues by file')
            rows = kept.locator('summary')
            expect(rows).to_have_count(10)
            assert [rows.nth(n).locator('.file').inner_text().strip() for n in range(10)] == top[:10]
            assert gone not in page.locator('main').inner_text()
            more = kept.get_by_role('button', name=f'and {len(files) - 10} more')
            expect(more).to_be_visible()
            height = page.evaluate('document.documentElement.scrollHeight')
            assert height <= 900, height
            clean(page, (scheme, 'short list'))

            # From the keyboard: the button opens the whole list in the drawer area, Escape closes it.
            more.focus()
            page.keyboard.press('Enter')
            full = page.get_by_role('dialog', name=f'Known issues by file, all {len(files)}')
            expect(full).to_be_visible()
            expect(full.locator('summary')).to_have_count(len(files))
            assert [t.strip() for t in full.locator('summary .file').all_inner_texts()] == top
            assert gone not in page.locator('main').inner_text()
            assert page.evaluate('document.activeElement.textContent').startswith('Known issues by file, all')
            assert page.evaluate('document.documentElement.scrollHeight') <= 900
            clean(page, (scheme, 'full list'))
            # A file inside the list still opens with Enter and closes with Escape before the list does.
            full.locator('summary').last.focus()
            page.keyboard.press('Enter')
            expect(full.get_by_text(f'Problem 1 in {top[-1]}')).to_be_visible()
            page.keyboard.press('Escape')
            expect(full.get_by_text(f'Problem 1 in {top[-1]}')).to_be_hidden()
            expect(full).to_be_visible()
            page.keyboard.press('Escape')
            expect(full).to_be_hidden()
            expect(page.get_by_role('button', name=f'and {len(files) - 10} more')).to_be_focused()
            # The Close button closes it too.
            page.keyboard.press('Enter')
            full.get_by_role('button', name='Close').click()
            expect(full).to_be_hidden()
            expect(page.get_by_role('button', name=f'and {len(files) - 10} more')).to_be_focused()
            page.close()
    finally:
        browser.close()
"""


def test_1_releases_show_ten_files_then_all_on_request_and_leave_out_deleted_files(client, tmp_path):
    teammate = clone(client, tmp_path)
    pushed(teammate, "Add the parts and a file that goes away", {
        **{file: "x = 1\n" for file in FILES}, GONE: "x = 1\n",
        ".factory/fixes/old.json": json.dumps({"kind": "fix", "branch": "fix/old", "why": "Parts are slow",
                                               "done_when": "Parts are fast", "status": "merged", "known": KEPT})})
    teammate.git("rm", "-q", GONE)
    teammate.git("commit", "-qm", "Remove the file that goes away")
    teammate.git("push", "-q", "origin", "HEAD:main")
    client.git("fetch", "-q", "origin")
    client.git("merge", "-q", "--ff-only", "origin/main")
    with live(client) as url:
        shown = subprocess.run([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with", "playwright==1.55.0",
                                "--with", "axe-playwright-python==0.1.8", "python", "-c", FITS, url,
                                json.dumps(FILES), GONE],
                               capture_output=True, text=True, encoding="utf-8", timeout=120)
        assert shown.returncode == 0, shown.stdout + shown.stderr
