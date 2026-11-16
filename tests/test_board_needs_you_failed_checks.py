"""A fix or story part with settled failed checks and no activity for a day or more is in Needs you
with a plain reason, on the list, the count and the item's own flag; checks that run, a day not yet
over, and passing checks are not."""
import json
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from conftest import REAL_UV
from test_board_counts import ONE_PART, board, clock
from test_board_needs_you import FIX, published, share
from test_board_server import client as board_client, live  # noqa: F401
from test_close import CLEAN, STORY_DOC, env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "FIX-FAILED-CHECKS-NEED-YOU"
DAY = timedelta(days=1)


def checks(head, *outcomes):
    """The pull request's last commit with one check run per outcome ('RUNNING' is not finished)."""
    nodes = [{"name": f"job-{n}", "status": "IN_PROGRESS", "conclusion": None} if o == "RUNNING"
             else {"name": f"job-{n}", "status": "COMPLETED", "conclusion": o} for n, o in enumerate(outcomes)]
    return {"nodes": [{"commit": {"oid": head, "statusCheckRollup": {"contexts": {
        "pageInfo": {"hasNextPage": False}, "nodes": nodes}}}}]}


@pytest.mark.parametrize("previous", [False], ids=["new-client"])
def test_1_failed_checks_idle_for_a_day_need_you(env, monkeypatch, previous):
    client(env, previous)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    clock(monkeypatch, now)
    prs = {}
    env.reviews(CLEAN)
    item, _ = env.start_approved_task(STORY_DOC, changes={"app.py": "x = 1\n"})
    cases = [("part", item, "task/SHOP-T1", ("FAILURE",)),
             ("red", "red", "fix/red", ("FAILURE",)),
             ("mixed", "mixed", "fix/mixed", ("FAILURE", "RUNNING")),
             ("green", "green", "fix/green", ("SUCCESS",))]
    for number, (name, ident, branch, outcomes) in enumerate(cases, 1):
        if name not in ("part",):
            env.start(ident, branch, f".factory/fixes/{ident}.json", {**FIX, "why": name}, {f"{name}.py": "x\n"})
        assert env.close(ident).returncode == 0
        share(env, prs, ident, number, branch=branch)
        prs[ident]["commits"] = checks(prs[ident]["headRefOid"], *outcomes)
        published(env, prs)

    def listed():
        data = board(env.repo)
        flags = {row["id"]: row["needs_person"] for parent in data["items"] for row in (parent, *parent["children"])}
        found = {e["id"]: (e["reason"], e["detail"]) for e in data["team"]["needs_you"]
                 if e["id"] in prs and e["reason"] == "checks failed"}
        assert all(flags[key] for key in found), (found, flags)  # the item's page agrees with the list
        return found, data["team"]["sentence"], flags

    clock(monkeypatch, now + timedelta(hours=2))
    assert listed()[0] == {}  # failed, but active within the day
    clock(monkeypatch, now + DAY - timedelta(minutes=5))
    assert listed()[0] == {}  # not yet a day
    clock(monkeypatch, now + 7 * DAY)
    found, _, flags = listed()
    reason = ("checks failed", "Checks failed, no activity for 7 days")
    assert found == {item: reason, "red": reason}, found  # the mixed one runs; the green one passes
    assert not flags["mixed"]  # running checks are not an idle failure
    clock(monkeypatch, now + DAY + timedelta(minutes=5))  # just over a day
    assert set(listed()[0]) == {item, "red"}


BROWSER = r"""
import json, sys
from playwright.sync_api import expect, sync_playwright
url, mine, theirs = sys.argv[1], json.loads(sys.argv[2]), sys.argv[3]
REASON = 'Checks failed, no activity for 7 days'
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        for width, height in ((1440, 900), (768, 900)):
            page = browser.new_page(viewport={'width': width, 'height': height})
            page.goto(url)
            needs = page.get_by_role('region', name='Needs you')
            expect(needs).to_contain_text('6 need you')
            expect(needs.get_by_text(REASON).first).to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'{width}: sideways scroll'
            if width == 1440:
                assert page.evaluate('document.documentElement.scrollHeight <= innerHeight'), 'the page scrolls'
            needs.get_by_role('button', name='and 3 more').click()
            full = page.get_by_role('dialog', name='Needs you, all 6')
            expect(full.get_by_role('button', name='Fix')).to_have_count(6)
            for title in [*mine, theirs]:  # each title once, each with its reason
                entry = full.get_by_role('button').filter(has=page.get_by_text(title, exact=True))
                expect(entry).to_have_count(1)
                expect(entry).to_contain_text(REASON)
            page.keyboard.press('Escape')
            page.get_by_role('button', name='Me', exact=True).click()
            me = page.get_by_role('region', name='Needs you')
            expect(me).to_contain_text('@asha')
            expect(me).to_contain_text('5 need you')
            me.get_by_role('button', name='and 2 more').click()
            full = page.get_by_role('dialog', name='Needs you, all 5')
            for title in mine:
                expect(full.get_by_text(title, exact=True)).to_have_count(1)
            expect(page.get_by_text(theirs, exact=True)).to_have_count(0)  # another person's item stays out
    finally:
        browser.close()
"""


def test_2_six_idle_failed_fixes_fit_the_first_screen_and_me_shows_only_the_viewers(board_client, gh):
    client = board_client
    titles = ["Basket totals", "Delivery slots", "Saved baskets", "Courier map", "Receipt emails", "Refund page"]
    slugs = [f"red-{n}" for n in range(6)]
    for slug, title in zip(slugs, titles):
        started = client.forge("fix", "start", title, "--done", "The board agrees", "--slug", slug, "--kind", "backend")
        assert started.returncode == 0, started.stderr

    def opened(n, slug, title):
        head = client.git("rev-parse", f"fix/{slug}")
        return {"number": 20 + n, "headRefName": f"fix/{slug}", "headRefOid": head, "state": "OPEN",
                "title": title, "body": "", "isDraft": False,
                "author": {"login": "ben" if n == 5 else "asha"},  # the last one is another person's
                "url": f"https://github.com/acme/shop/pull/{20 + n}", "commits": checks(head, "FAILURE")}

    gh.respond("api", "graphql", stdout=json.dumps({"data": {"repository": {"pullRequests": {"nodes": [
        opened(n, slug, title) for n, (slug, title) in enumerate(zip(slugs, titles))]}}}}))
    gh.respond("api", "user", stdout="asha\n")
    week = (datetime.now(timezone.utc) + 7 * DAY).isoformat()
    with live(client, FORGE_NOW=week) as url:
        shown = subprocess.run([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                                "playwright==1.55.0", "python", "-c", BROWSER, url, json.dumps(titles[:5]),
                                titles[5]], capture_output=True, text=True, encoding="utf-8", timeout=300)
        assert shown.returncode == 0, shown.stdout + shown.stderr
