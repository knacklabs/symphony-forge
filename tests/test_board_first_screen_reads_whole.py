"""The board's first screen shows what the data knows, on a new and an earlier-adopted repo, in real Chrome
at half a screen and at 1,100, 1,150, 1,280 and 1,440 pixels wide. Every card, a Needs you card and a story
in the Stories rail too, shows its whole title, wrapped, with the full title on hover. No other region covers
any corner of a title, even when four cards have 60-character titles, and the 1,440 by 900 screen still fits
without scrolling. A fix and a story part idle for days each say how long on their card. A story whose own
record is gone shows the title of its plan file. The Stories rail says "No owner yet" where no owner is set,
and one plan note reads "1 note". The real command, server and browser run; only GitHub is a stub."""
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from conftest import REAL_UV
from test_board import DOC
from test_board_item_keyboard_refresh import stop_tree
from test_board_server import client, clone, live, pushed  # noqa: F401
from test_story import worktree

STORY = "FIX-BOARD-FIRST-SCREEN-READS-WHOLE"
pytestmark = pytest.mark.platform

LONG = "Readers see the exact basket total after a refund in {} parts"  # 60 characters
PART = "Share a saved basket with a friend by email or message"
STORY_TITLE = "Forge v1: a lean rebuild that both coordinators and workers can follow end to end"

SCRIPT = r"""
import json, re, sys
from playwright.sync_api import expect, sync_playwright
url, expected = sys.argv[1], json.loads(sys.argv[2])

# A title is whole when its text fits its own box with no ellipsis, it is on hover too, and no other
# element covers any of the four corners of its box.
WHOLE = '''(e) => {
  const box = e.getBoundingClientRect();
  const corners = [[box.left + 1, box.top + 1], [box.right - 1, box.top + 1], [box.left + 1, box.bottom - 1], [box.right - 1, box.bottom - 1]];
  const covered = corners.filter(([x, y]) => { const top = document.elementFromPoint(x, y); return !(top && (e.contains(top) || top.contains(e))); });
  return { whole: e.scrollWidth <= e.clientWidth + 1 && e.scrollHeight <= e.clientHeight + 1
      && getComputedStyle(e).textOverflow !== 'ellipsis',
    hover: e.title || e.closest('[title]')?.title, covered: covered.length };
}'''
# Every button's box, cut to the scrolling boxes around it, against the figures box [left, top, right, bottom].
OVER = '''([left, top, right, bottom]) => [...document.querySelectorAll('main button')].filter((button) => {
  let box = button.getBoundingClientRect(), [l, t, r, b] = [box.left, box.top, box.right, box.bottom];
  for (let at = button.parentElement; at && at !== document.body; at = at.parentElement) {
    if (getComputedStyle(at).overflowY === 'visible') continue;
    const clip = at.getBoundingClientRect();
    [l, t, r, b] = [Math.max(l, clip.left), Math.max(t, clip.top), Math.min(r, clip.right), Math.min(b, clip.bottom)];
  }
  return r > l && b > t && r > left && l < right && b > top + 0.5 && t < bottom;
}).map((button) => button.textContent)'''

def reach(page, name, where):
    # A keyboard-only person can focus the named region (it scrolls), and sees a focus ring on it.
    for _ in range(150):
        page.keyboard.press('Tab')
        if page.evaluate('document.activeElement.getAttribute("aria-label")') == name:
            assert page.evaluate('getComputedStyle(document.activeElement).outlineStyle') != 'none', (where, name, 'no focus ring')
            return
    raise AssertionError((where, 'Tab never reached the region', name))

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        # The last two run at 110% zoom: larger text on any font must not push a region into the figures.
        for width, scheme, zoom in ((768, 'dark', 1), (1100, 'light', 1), (1150, 'dark', 1), (1280, 'light', 1), (1440, 'dark', 1),
                                    (1280, 'dark', 1.1), (1440, 'light', 1.1)):
            where = (width, scheme, zoom)
            page = browser.new_page(viewport={'width': width, 'height': 900}, color_scheme=scheme)
            page.set_default_timeout(30000)
            page.goto(url)
            expect(page.get_by_role('status')).to_have_text('Live')
            expect(page.get_by_role('region', name='In flight')).to_be_visible()
            if zoom != 1:
                page.evaluate('z => { document.documentElement.style.zoom = z; }', zoom)
            # Each title is found inside its own region: the Needs you card, a card in Building, the Stories rail.
            for region, titles in expected['titles']:
                for title in titles:
                    found = page.get_by_role('region', name=region, exact=True).get_by_text(title, exact=True)
                    assert found.count() == 1, (where, region, 'does not show exactly one', title, found.count())
                    found.scroll_into_view_if_needed()
                    seen = found.evaluate(WHOLE)
                    assert seen['whole'], (where, region, 'a title is cut', title)
                    assert seen['hover'] == title, (where, region, 'no full title on hover', title, seen)
                    assert not seen['covered'], (where, region, 'another region covers a title', title, seen)
            page.evaluate('window.scrollTo(0, 0)')
            if width == 1440 and zoom == 1:
                assert page.evaluate('document.documentElement.scrollHeight <= innerHeight'), (where, 'the first screen scrolls')
            # No region of the stages or the rail reaches into the figures, and no card is painted over them.
            figures = page.get_by_role('region', name='Figures').bounding_box()
            for region in ('In flight', 'Stories', 'Planned', 'Building', 'Review', 'Ready', 'Merged'):
                box = page.get_by_role('region', name=region, exact=True).bounding_box()
                assert box['y'] + box['height'] <= figures['y'] + 0.5, (where, region, 'reaches into the figures', box, figures)
            # The visible part of every card (clipped by any scrolling box around it) stays out of the figures.
            over = page.evaluate(OVER, [figures['x'], figures['y'], figures['x'] + figures['width'], figures['y'] + figures['height']])
            assert over == [], (where, 'a card reaches into the figures', over)
            # A fix and a story part idle for six days say so on their cards; a fresh fix does not.
            expect(page.get_by_role('button', name=re.compile(expected['idle_fix'] + '.*idle 6 d'))).to_have_count(1)
            expect(page.get_by_role('button', name=re.compile(expected['idle_part'] + '.*idle 6 d'))).to_have_count(1)
            expect(page.get_by_role('button', name=re.compile(expected['fresh'])).first).not_to_contain_text('idle')
            # The story has no owner: the rail says so in words.
            story = page.get_by_role('region', name='Stories').get_by_role('button', name=re.compile('Shoppers can save a basket'))
            expect(story).to_contain_text('No owner yet')
            expect(story).not_to_contain_text('unknown')
            # The story that lost its own record shows its plan's title, and one plan note reads "1 note".
            page.goto(url + '#item/LOST')
            expect(page.get_by_role('heading', name='Couriers book slots')).to_be_visible()
            expect(page.get_by_text('A story with missing state')).to_have_count(0)
            page.goto(url + '#item/SHOP')
            page.get_by_role('tab', name='Rounds').click()
            panel = page.get_by_role('tabpanel')
            expect(panel).to_contain_text('1 note')
            expect(panel).not_to_contain_text('1 notes')
            if width == 1440 and zoom == 1:
                page.goto(url)
                expect(page.get_by_role('region', name='Stories')).to_be_visible()
                reach(page, 'Stories', where)
                page.get_by_role('button', name='Me', exact=True).click()
                expect(page.get_by_role('region', name='Live')).to_be_visible()
                reach(page, 'Live', where)
            page.close()
    finally:
        browser.close()
"""


def _dated(started):
    """The environment of a record made at this time, the way Forge dates its records."""
    return {name: started for name in ("FORGE_NOW", "GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE")}


def _fix(repo, slug, title, started, **more):
    """A real fix, started at this time and working: its record changes only in its own worktree."""
    with pytest.MonkeyPatch.context() as then:
        for name, value in _dated(started).items():
            then.setenv(name, value)
        made = repo.forge("fix", "start", title, "--done", "The total is right", "--slug", slug, "--kind", "mechanical")
    assert made.returncode == 0, made.stderr
    path = worktree(repo, f"fix/{slug}") / f".factory/fixes/{slug}.json"
    path.write_text(json.dumps({**json.loads(path.read_text("utf-8")), "status": "fixing", **more}), encoding="utf-8")


def _part(repo, tmp_path, started):
    """SHOP's part SHARE, working on its own branch since this time and not merged."""
    branch, folder = "task/SHOP-SHARE", tmp_path / "share-part"
    repo.git("worktree", "add", "-q", "-b", branch, str(folder), "main")
    record = folder / ".factory/stories/SHOP/tasks/SHARE.json"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps({"status": "working", "branch": branch, "steps": [{"step": "start", "at": started}]}),
                      encoding="utf-8")
    with pytest.MonkeyPatch.context() as then:
        for name, value in _dated(started).items():
            then.setenv(name, value)
        repo.git("add", "-A", cwd=folder)
        repo.git("commit", "-qm", "Start sharing", cwd=folder)


def test_1_the_first_screen_shows_whole_titles_idle_time_owners_and_plan_titles(client, gh, tmp_path):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    six_days = (now - timedelta(days=6)).isoformat()
    # Four cards in Building with 60-character titles: two fixes, one that asks a question, and a story part.
    _fix(client, "total-two", LONG.format("two"), six_days)
    _fix(client, "total-three", LONG.format("three"), now.isoformat())
    _fix(client, "total-four", LONG.format("four"), now.isoformat(), stop={"question": "Which total?", "at": now.isoformat()})
    # LOST has a part but no story record of its own: its title lives in its plan.
    part = json.dumps({"status": "merged", "steps": [{"step": "start", "at": six_days}]})
    pushed(clone(client, tmp_path), "Plan a basket and add work", {
        "plans/SHOP.md": DOC.replace("Share a basket", PART),
        "plans/SHOP.read.md": "## Round 1\n\n1. The plan is too long. Disposition: keep because it is clear\n",
        ".factory/stories/SHOP/story.json": json.dumps({"doc": "plans/SHOP.md", "title": "Shoppers can save a basket",
                                                        "status": "approved"}),
        "plans/LEAN.md": DOC.replace("# Shoppers can save a basket", f"# {STORY_TITLE}", 1),
        ".factory/stories/LEAN/story.json": json.dumps({"doc": "plans/LEAN.md", "title": STORY_TITLE, "status": "approved"}),
        "plans/LOST.md": DOC.replace("# Shoppers can save a basket", "# Couriers book slots", 1).replace("| SAVE |", "| ONE |", 1),
        ".factory/stories/LOST/tasks/ONE.json": part})
    client.git("fetch", "-q", "origin")
    client.git("merge", "-q", "--ff-only", "origin/main")
    _part(client, tmp_path, six_days)
    expected = {"titles": [["Needs you", [LONG.format("four")]], ["Stories", [STORY_TITLE]],
                           ["Building", [LONG.format(word) for word in ("two", "three", "four")] + [PART]]],
                "idle_fix": "in two parts", "idle_part": "Share a saved basket", "fresh": "in three parts"}
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        shown = subprocess.Popen([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                                  "playwright==1.55.0", "python", "-c", SCRIPT, url, json.dumps(expected)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                 start_new_session=os.name != "nt")
        try:
            out, err = shown.communicate(timeout=360)
        finally:
            if shown.poll() is None:
                stop_tree(shown)
                shown.communicate(timeout=30)
        assert shown.returncode == 0, out + err
