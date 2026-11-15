"""A story's review rounds sit on its parts, and the board shows them in real Chrome.

The story has its own review round, one part that merged before the board's seven-day window (the Now
snapshot leaves it out) and one recent part with a reviewed round and a worker turn that was never
reviewed. A third part merged long ago and has no review history on this laptop. The drawer, opened by
clicking the story, and the full page list each part's rounds under its plain title, count only
reviews, say plainly that one history is missing and give the total as "at least". With every history
present the total is exact.
"""
import json
import subprocess
from types import SimpleNamespace

import pytest

from conftest import REAL_UV
from test_board_counts import github
from test_board_item_page import PLAN
from test_board_server import client, clone, get, live, pushed  # noqa: F401

pytestmark = pytest.mark.platform

STORY = "FIX-STORY-ROUNDS"

SCRIPT = r"""
import re, sys
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright
url, total, mode = sys.argv[1], sys.argv[2], sys.argv[3]
gap = mode == 'gap'
axe = Axe()
NOTE = 'Its review history is not on this laptop.'

def scan(page, where, context=None):
    page.evaluate('Promise.all(document.getAnimations().map(a => a.finished))')
    found = axe.run(page, context=context).response['violations']
    assert not found, (where, [(v['id'], [n['target'] for n in v['nodes']]) for v in found])

def shows(scope, counted):
    # Every fact is found by its words: the count by its label, a part's rounds by the part's title.
    expect(scope).not_to_contain_text('No review rounds yet')
    expect(counted.get_by_text('review rounds', exact=True).locator('..')).to_have_text(re.compile('review rounds\\s*' + total + '$'))
    for title, rounds in (('The story itself', 1), ('Save a basket', 2), ('Share a basket', 1)):  # an unreviewed worker turn is no round
        expect(scope.get_by_role('list', name=title).get_by_role('listitem')).to_have_count(rounds)
    expect(scope.get_by_text('Basket total is off by one').first).to_be_visible()
    expect(scope.get_by_text(NOTE)).to_have_count(1 if gap else 0)
    assert 'SAVE' not in scope.inner_text() and 'SHOP/' not in scope.inner_text()

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        for scheme in ('light', 'dark'):
            page = browser.new_page(viewport={'width': 1440, 'height': 900}, color_scheme=scheme)
            page.goto(url)
            expect(page.get_by_role('status')).to_have_text('Live', timeout=60000)
            page.get_by_role('button', name=re.compile('Shoppers can save a basket')).first.click()
            drawer = page.get_by_role('complementary', name='Shoppers can save a basket')
            expect(drawer).to_be_visible()
            if mode == 'nothing':  # three merged parts and no review known anywhere: the total is unknown, not "at least 0"
                expect(drawer.get_by_text('review rounds', exact=True).locator('..')).to_have_text(re.compile('review rounds\\s*unknown$'))
                expect(drawer.get_by_text(NOTE)).to_have_count(3)
                page.close()
                continue
            shows(drawer, drawer)
            if gap:  # the note sits under the part it is about
                expect(drawer.get_by_text('Show when it was saved').locator('..').get_by_text(NOTE)).to_be_visible()
            scan(page, f'story drawer, {scheme}', '.drawer')  # the Now screen under it is another part's

            drawer.get_by_role('link', name='Full history').click()
            expect(page.get_by_role('heading', level=1, name='Shoppers can save a basket')).to_be_visible()
            page.get_by_role('tab', name='Rounds', exact=True).click()
            shows(page.get_by_role('tabpanel'), page)
            scan(page, f'story rounds, {scheme}')
            page.close()
    finally:
        browser.close()
"""


def event(item, round, at, title):
    return {"id": f"{item}-{round}", "item": item, "event": "review result", "round": round, "review_round": round,
            "at": at, "outcome": "findings", "findings": [{"priority": "P2", "file": "basket.py", "title": title}]}


def story_with_rounds(client, gh, tmp_path, monkeypatch, merged_without_history, reviews=True):
    """SAVE merged in October with two reviews; SHARE merged last week with one review and an unreviewed
    worker turn; the story has one review of its own. SHOW merged in October with no record here, or is not started."""
    teammate = clone(client, tmp_path)
    old, recent = "2026-10-01T09:00:00+00:00", "2026-11-13T09:00:00+00:00"
    monkeypatch.setenv("GIT_AUTHOR_DATE", old)
    monkeypatch.setenv("GIT_COMMITTER_DATE", old)
    merged = lambda part: {f".factory/stories/SHOP/tasks/{part}.json":
                           json.dumps({"status": "merged", "branch": f"task/SHOP-{part}"})}
    pushed(teammate, "Plan a basket", {"basket.py": "total = 0\n", "plans/SHOP.md": PLAN,
           ".factory/stories/SHOP/story.json":
           json.dumps({"doc": "plans/SHOP.md", "title": "Shoppers can save a basket", "status": "approved"}),
           **merged("SAVE"), **(merged("SHOW") if merged_without_history else {})})
    monkeypatch.setenv("GIT_AUTHOR_DATE", recent)
    monkeypatch.setenv("GIT_COMMITTER_DATE", recent)
    pushed(teammate, "Share a basket", merged("SHARE"))
    monkeypatch.delenv("GIT_AUTHOR_DATE")
    monkeypatch.delenv("GIT_COMMITTER_DATE")
    client.git("fetch", "-q", "origin")
    # The story's own pull request keeps a time record, so the story has a rounds list of its own.
    github(SimpleNamespace(repo=client, gh=gh), [{
        "number": 7, "headRefName": "story/SHOP", "headRefOid": "0" * 40, "state": "OPEN", "title": "Shoppers can save a basket",
        "isDraft": False, "body": "<!-- forge:begin -->\n<!-- forge:time-record " + json.dumps({"events": [], "timings": []})
        + " -->\n<!-- forge:end -->"}])
    with (client.path / ".git/forge/events.jsonl").open("a", encoding="utf-8") as log:
        for row in () if not reviews else (event("SHOP", 1, "2026-10-02T10:00:00+00:00", "Plan wording is unclear"),
                    event("SHOP/SAVE", 1, "2026-10-01T10:00:00+00:00", "Basket total is off by one"),
                    event("SHOP/SAVE", 2, "2026-10-01T11:00:00+00:00", "Basket total is off by one"),
                    event("SHOP/SHARE", 1, "2026-11-13T10:00:00+00:00", "Shared link shows no basket"),
                    {"id": "turn", "item": "SHOP/SHARE", "event": "work phase", "phase": "building", "round": 2,
                     "at": "2026-11-13T12:00:00+00:00"}):
            log.write(json.dumps(row) + "\n")


def check(client, url, total, gap):
    status, _, body = get(url, "/board.json?page=item&id=SHOP")
    assert status == 200, body
    story = json.loads(body)["item"]
    parts = {part["id"]: part for part in story["children"]}
    assert len(story["rounds"]) == 1  # the story has a record of its own, with one review in it
    assert len(parts["SHOP/SHARE"]["rounds"]) == 2  # a reviewed round and a worker turn that was never reviewed
    assert not parts.get("SHOP/SHOW", {}).get("rounds")  # nothing recorded here about the long-merged part
    shown = subprocess.run([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                            "playwright==1.55.0", "--with", "axe-playwright-python==0.1.4", "python", "-c", SCRIPT,
                            url, total, "gap" if gap else "exact"], capture_output=True, text=True, encoding="utf-8", timeout=300)
    assert shown.returncode == 0, shown.stdout + shown.stderr


def test_1_a_part_merged_long_ago_with_no_history_here_says_so_and_the_total_is_at_least(client, gh, tmp_path, monkeypatch):
    story_with_rounds(client, gh, tmp_path, monkeypatch, merged_without_history=True)
    with live(client, FORGE_BOARD_FETCH_WAIT="3600", FORGE_NOW="2026-11-14T12:00:00+00:00") as url:
        check(client, url, "at least 4", True)


def test_2_a_story_lists_each_reviewed_round_under_its_part_and_counts_only_reviews(client, gh, tmp_path, monkeypatch):
    story_with_rounds(client, gh, tmp_path, monkeypatch, merged_without_history=False)
    with live(client, FORGE_BOARD_FETCH_WAIT="3600", FORGE_NOW="2026-11-14T12:00:00+00:00") as url:
        check(client, url, "4", False)


def test_3_a_story_whose_merged_parts_have_no_known_review_says_unknown(client, gh, tmp_path, monkeypatch):
    story_with_rounds(client, gh, tmp_path, monkeypatch, merged_without_history=True, reviews=False)
    with live(client, FORGE_BOARD_FETCH_WAIT="3600", FORGE_NOW="2026-11-14T12:00:00+00:00") as url:
        shown = subprocess.run([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                                "playwright==1.55.0", "--with", "axe-playwright-python==0.1.4", "python", "-c", SCRIPT,
                                url, "", "nothing"], capture_output=True, text=True, encoding="utf-8", timeout=300)
        assert shown.returncode == 0, shown.stdout + shown.stderr
