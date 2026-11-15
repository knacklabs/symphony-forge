"""A fix with failed checks and no activity for a day or more is in Needs you with a plain reason;
the same fix that was active in the last day, or whose checks pass, is not."""
import json
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from conftest import REAL_UV
from test_board_counts import board, clock, github
from test_board_server import client as board_client, fix, live  # noqa: F401
from test_board_needs_you import FIX, published, share
from test_close import CLEAN, env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "FIX-FAILED-CHECKS-NEED-YOU"


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "earlier-adoption"])
def test_1_failed_checks_idle_for_a_day_need_you(env, monkeypatch, previous):
    client(env, previous)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    clock(monkeypatch, now)
    prs = {}
    env.reviews(CLEAN)
    for name, outcome in (("red", "FAILURE"), ("green", "SUCCESS")):
        env.start(name, f"fix/{name}", f".factory/fixes/{name}.json", {**FIX, "why": name}, {f"{name}.py": "x\n"})
        assert env.close(name).returncode == 0
        share(env, prs, name, len(prs) + 1)
        head = prs[name]["headRefOid"]
        prs[name]["commits"] = {"nodes": [{"commit": {"oid": head, "statusCheckRollup": {"contexts": {
            "pageInfo": {"hasNextPage": False}, "nodes": [{"name": "tests", "status": "COMPLETED",
                                                            "conclusion": outcome}]}}}}]}
        published(env, prs)

    def asks():
        team = board(env.repo)["team"]
        return [(e["id"], e["reason"], e["detail"]) for e in team["needs_you"] if e["id"] in prs and e["reason"] != "merge"], team["sentence"]

    clock(monkeypatch, now + timedelta(hours=2))
    assert asks()[0] == []  # failed, but active within the day
    clock(monkeypatch, now + timedelta(days=7))
    found, sentence = asks()
    assert found == [("red", "checks failed", "Checks failed, no activity for 7 days")], found
    assert "2 need you" in sentence  # the red fix and the green fix's merge


BROWSER = r"""
import sys
from playwright.sync_api import expect, sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch()
    try:
        for width, height in ((1440, 900), (768, 900)):
            page = browser.new_page(viewport={'width': width, 'height': height})
            page.goto(sys.argv[1])
            needs = page.get_by_role('region', name='Needs you')
            expect(needs).to_contain_text('5 need you')
            expect(needs.get_by_role('button', name='Fix Fix').first).to_be_visible()
            expect(needs.get_by_text('Checks failed, no activity for 7 days').first).to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'{width}: sideways scroll'
            if width == 1440:
                assert page.evaluate('document.documentElement.scrollHeight <= innerHeight'), 'the page scrolls'
    finally:
        browser.close()
"""


def test_2_five_idle_failed_fixes_fit_the_first_screen(board_client, gh):
    client = board_client
    def opened(slug):
        head = client.git("rev-parse", f"fix/{slug}")
        return {"number": len(slug) + hash(slug) % 50, "headRefName": f"fix/{slug}", "headRefOid": head,
                "state": "OPEN", "title": f"Readers see {slug}", "body": "", "isDraft": False,
                "author": {"login": "asha"}, "url": f"https://github.com/acme/shop/pull/{slug}",
                "commits": {"nodes": [{"commit": {"oid": head, "statusCheckRollup": {"contexts": {
                    "pageInfo": {"hasNextPage": False}, "nodes": [
                        {"name": "tests", "status": "COMPLETED", "conclusion": "FAILURE"}]}}}}]}}

    slugs = [f"red-{n}" for n in range(5)]
    for slug in slugs:
        fix(client, slug)
    gh.respond("api", "graphql", stdout=json.dumps({"data": {"repository": {"pullRequests": {"nodes": [
        opened(slug) for slug in slugs]}}}}))
    week = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    with live(client, FORGE_NOW=week) as url:
        shown = subprocess.run([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                                "playwright==1.55.0", "python", "-c", BROWSER, url],
                               capture_output=True, text=True, encoding="utf-8", timeout=300)
        assert shown.returncode == 0, shown.stdout + shown.stderr
