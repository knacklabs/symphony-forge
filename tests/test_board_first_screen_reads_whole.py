"""The board's first screen shows what the data knows, on a new and an earlier-adopted repo, in real Chrome
at 1440 and 768 pixels wide. Every card shows its whole title, wrapped, with the full title on hover, so two
long titles never read the same. A part idle for days says how long on its card. A story whose own record
is gone takes its title from its plan file. The Stories rail says "No owner yet" where no owner is set.
A story whose parts merged lists their review rounds, and one plan note reads "1 note". The real command,
server and browser run; only GitHub is a stub."""
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from conftest import REAL_UV
from test_board import DOC
from test_board_item_keyboard_refresh import stop_tree
from test_board_server import client, clone, live, pushed, snapshot  # noqa: F401
from test_story import worktree

STORY = "FIX-BOARD-FIRST-SCREEN-READS-WHOLE"
pytestmark = pytest.mark.platform

LONG = "Readers see the exact basket total after a refund in {} parts"

SCRIPT = r"""
import re, sys
from playwright.sync_api import expect, sync_playwright
url = sys.argv[1]

# A title is whole when the text fits its own box and nothing is cut or hidden by ellipsis.
WHOLE = '''() => [...document.querySelectorAll('.chip-title, .done button')].map((e) => [e.textContent, e.title,
  e.scrollWidth <= e.clientWidth + 1 && e.scrollHeight <= e.clientHeight + 1 && getComputedStyle(e).textOverflow !== 'ellipsis'])'''

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        for width, scheme in ((1440, 'light'), (768, 'dark')):
            where = (width, scheme)
            page = browser.new_page(viewport={'width': width, 'height': 900}, color_scheme=scheme)
            page.set_default_timeout(30000)
            page.goto(url)
            expect(page.get_by_role('status')).to_have_text('Live')
            expect(page.locator('.stage')).to_have_count(5)
            cards = page.evaluate(WHOLE)
            assert any('in two parts' in text for text, _, _ in cards) and any('in three parts' in text for text, _, _ in cards), (where, cards)
            for text, hover, whole in cards:
                assert whole, (where, 'a card title is cut', text)
                assert hover == text, (where, 'the card has no full title on hover', text, hover)
            # The part idle for six days says so on its card, in the tag beside its key.
            idle = page.get_by_role('button', name=re.compile('in two parts.*idle 6 d'))
            expect(idle).to_have_count(1)
            expect(page.get_by_role('button', name=re.compile('in three parts')).first).not_to_contain_text('idle')
            # The story has no owner: the rail says so in words.
            story = page.get_by_role('region', name='Stories').get_by_role('button', name=re.compile('Shoppers can save a basket'))
            expect(story).to_contain_text('No owner yet')
            expect(story).not_to_contain_text('unknown')
            story.click()
            drawer = page.get_by_role('complementary', name='Shoppers can save a basket')
            expect(drawer).to_be_visible()
            expect(drawer).not_to_contain_text('No review rounds yet')
            expect(drawer.locator('.figures div').filter(has_text='review rounds')).to_contain_text('2')
            drawer.get_by_role('link', name='Full history').click()
            page.get_by_role('tab', name='Rounds').click()
            panel = page.get_by_role('tabpanel')
            expect(panel).to_contain_text('Round 1')
            expect(panel).to_contain_text('1 note')
            expect(panel).not_to_contain_text('1 notes')
            page.close()
    finally:
        browser.close()
"""


def _fix(repo, slug, title, started):
    """A real fix, started at this time and working: its record changes only in its own worktree."""
    with pytest.MonkeyPatch.context() as then:
        for name in ("FORGE_NOW", "GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
            then.setenv(name, started)
        made = repo.forge("fix", "start", title, "--done", "The total is right", "--slug", slug, "--kind", "mechanical")
    assert made.returncode == 0, made.stderr
    path = worktree(repo, f"fix/{slug}") / f".factory/fixes/{slug}.json"
    path.write_text(json.dumps({**json.loads(path.read_text("utf-8")), "status": "fixing"}), encoding="utf-8")


def test_1_the_first_screen_shows_whole_titles_idle_time_owners_and_rounds(client, gh, tmp_path):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    six_days = (now - timedelta(days=6)).isoformat()
    _fix(client, "total-2", LONG.format("two"), six_days)
    _fix(client, "total-3", LONG.format("three"), now.isoformat())
    events = [{"id": f"r{n}", "item": "SHOP/SAVE", "event": "review result", "round": n, "review_round": n, "findings": [], "at": six_days}
              for n in (1, 2)]
    part = json.dumps({"status": "merged", "steps": [{"step": "start", "at": six_days}]})
    # LOST has a part but no story record of its own: its title lives in its plan.
    pushed(clone(client, tmp_path), "Plan a basket and add work", {
        "plans/SHOP.md": DOC, "plans/SHOP.read.md": "## Round 1\n\n1. The plan is too long. Disposition: keep because it is clear\n",
        ".factory/stories/SHOP/story.json": json.dumps({"doc": "plans/SHOP.md", "title": "Shoppers can save a basket",
                                                        "status": "approved"}),
        ".factory/stories/SHOP/tasks/SAVE.json": part,
        "plans/LOST.md": DOC.replace("# Shoppers can save a basket", "# Couriers book slots", 1).replace("| SAVE |", "| ONE |", 1),
        ".factory/stories/LOST/tasks/ONE.json": part})
    client.git("fetch", "-q", "origin")
    client.git("merge", "-q", "--ff-only", "origin/main")
    with (client.path / ".git/forge/events.jsonl").open("a", encoding="utf-8") as log:
        log.writelines(json.dumps(event) + "\n" for event in events)
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        # A story with no record of its own takes its title from its plan file.
        titles = {row["id"]: row["title"] for row in snapshot(url)["items"]}
        assert titles["LOST"] == "Couriers book slots", titles
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
