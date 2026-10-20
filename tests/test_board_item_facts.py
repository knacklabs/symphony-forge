"""Live detail regressions for missing merger facts, compacted rounds and story readiness.

The original detail journey owns the inert plan and keyboard contract. These cases use
the real server and renderer; only GitHub's published history and receipts are fixtures.
"""
import json
import subprocess
from types import SimpleNamespace

from conftest import REAL_UV
from test_board_counts import github
from test_board_item_page import PLAN
from test_board_server import client, clone, fix, live, pushed, snapshot  # noqa: F401

STORY = "FIX-ITEM-FACTS"

SCRIPT = r"""
import re, sys
from playwright.sync_api import expect, sync_playwright
from axe_playwright_python.sync_playwright import Axe
url = sys.argv[1]
BOARD = "(await import(new URL('app.js' + location.search, location.href))).Board"
failures = []
def check(name, assertion):
    try:
        assertion()
    except AssertionError as error:
        failures.append((name, str(error)))
def scan(page, context='.item-page'):
    violations = Axe().run(page, context=context).response['violations']
    assert not violations, violations
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        for scheme in ('light', 'dark'):
            page = browser.new_page(color_scheme=scheme, viewport={'width': 1440, 'height': 900})
            page.goto(url)
            expect(page.get_by_role('status')).to_have_text('Live', timeout=60000)
            # Hold any entry animation near its start. Text must keep its contrast
            # while the drawer enters, as well as after it settles.
            page.evaluate('''async () => {
                const board = ''' + BOARD + ''';
                await board.openDrawer('SHOP');
                for (const animation of document.querySelector('.drawer').getAnimations()) {
                    animation.pause();
                    animation.currentTime = animation.effect.getTiming().duration / 10;
                }
            }''')
            drawer = page.get_by_role('complementary', name='Shoppers can save a basket')
            expect(drawer).to_be_visible()
            check('drawer entry contrast', lambda: scan(page, '.drawer'))
            check('ready story drawer', lambda: expect(drawer.locator('.tag')).to_have_text('Ready', timeout=1000))
            page.evaluate("async () => " + BOARD + ".openDrawer('alpha')")
            drawer = page.get_by_role('complementary', name='Readers see alpha')
            expect(drawer).to_be_visible()
            check('drawer status without terminal advice', lambda: expect(drawer.locator('.state-line')).to_have_text('Needs fixes', timeout=1000))
            check('plain drawer copy', lambda: expect(drawer).not_to_contain_text(re.compile(r'\bforge [a-z]|--[a-z]|`'), timeout=1000))
            page.evaluate("async () => " + BOARD + ".openDrawer('SHOP/SAVE')")
            drawer = page.get_by_role('complementary', name='Save a basket')
            expect(drawer).to_be_visible()
            measured = drawer.locator('.rounds li').filter(has_text='Round 10:')
            check('recorded drawer review', lambda: expect(measured).to_contain_text('review clean (2 minutes)'))
            check('measured drawer review', lambda: expect(measured.locator('.took')).to_have_text('2 m'))
            check('plain recorded drawer review', lambda: expect(drawer).not_to_contain_text(re.compile(r'\bforge [a-z]|--[a-z]|`'), timeout=1000))
            page.evaluate("async () => " + BOARD + ".openItem('SHOP')")
            expect(page.get_by_role('heading', level=1, name='Shoppers can save a basket')).to_be_visible()
            check('ready story page', lambda: expect(page.locator('.summary .tag')).to_have_text('Ready', timeout=1000))
            page.get_by_role('tab', name=re.compile('^Known issues')).click()
            check('known issues accessible name', lambda: expect(page.get_by_role('tabpanel', name=re.compile('^Known issues'))).to_be_visible(timeout=1000))
            panel = page.get_by_role('tabpanel')
            check('kept issue content', lambda: expect(panel).to_contain_text('Basket title wraps'))
            check('kept issue reason', lambda: expect(panel).to_contain_text('The next page change owns the repair'))
            check('kept issue rows', lambda: expect(panel.locator('.issues li')).to_have_count(2))
            check('plain kept issues', lambda: expect(panel).not_to_contain_text(re.compile(r'\bforge [a-z]|--[a-z]|`'), timeout=1000))
            check('known issues axe', lambda: scan(page))
            for item, title, expected in [('OLD', 'Older change', 'unknown'), ('alpha', 'Readers see alpha', 'not yet')]:
                page.evaluate("async () => " + BOARD + ".openItem(" + repr(item) + ")")
                expect(page.get_by_role('heading', level=1)).to_have_text(title)
                check('merger ' + item, lambda: expect(page.locator('.facts div').filter(has=page.get_by_text('Merged by', exact=True)).locator('dd')).to_have_text(expected, timeout=1000))
            page.evaluate("async () => " + BOARD + ".openItem('SHOP/SAVE')")
            expect(page.get_by_role('heading', level=1, name='Save a basket')).to_be_visible()
            check('compacted round count', lambda: expect(page.locator('.figures div').filter(has=page.get_by_text('review rounds', exact=True)).locator('dd')).to_have_text('10', timeout=1000))
            check('populated history', lambda: expect(page.locator('.events')).to_contain_text('A worker asked a technical question.'))
            check('plain history', lambda: expect(page.get_by_role('tabpanel')).not_to_contain_text(re.compile(r'\bforge [a-z]|--[a-z]|`'), timeout=1000))
            page.get_by_role('tab', name='Rounds', exact=True).click()
            measured = page.get_by_role('tabpanel').locator('.rounds li').filter(has_text='Round 10:')
            check('recorded full-page review', lambda: expect(measured).to_contain_text('review clean (2 minutes)'))
            check('measured full-page review', lambda: expect(measured.locator('.took')).to_have_text('2 m'))
            check('plain full-page reviews', lambda: expect(page.get_by_role('tabpanel')).not_to_contain_text(re.compile(r'\bforge [a-z]|--[a-z]|`'), timeout=1000))
            page.close()
    finally:
        browser.close()
assert not failures, failures
"""


def test_1_item_details_keep_recorded_facts_and_accessible_plain_words(client, gh, tmp_path):
    teammate = clone(client, tmp_path)
    plan = "\n".join(line for line in PLAN.split("\n") if not line.startswith(("| SHARE |", "| SHOW |")))
    kept = [{"file": "basket.py", "line": 1, "outcome": "follow-up",
             "title": "Run `forge test --pytest main` before review", "reason": "Use forge close SHOP/SAVE"},
            {"file": "basket.py", "line": 2, "outcome": "follow-up",
             "title": "Basket title wraps", "reason": "The next page change owns the repair"}]
    pushed(teammate, "Plan a basket", {"basket.py": "total = 0\n", "plans/SHOP.md": plan, ".factory/stories/SHOP/story.json":
           json.dumps({"doc": "plans/SHOP.md", "title": "Shoppers can save a basket", "status": "approved", "known": kept}),
           ".factory/stories/OLD/story.json": json.dumps({"title": "Older change", "status": "done"})})
    teammate.git("switch", "-qc", "task/SHOP-SAVE")
    teammate.write(".factory/stories/SHOP/tasks/SAVE.json", json.dumps({
        "status": "waiting for checks", "branch": "task/SHOP-SAVE"}))
    teammate.git("add", "-A")
    teammate.git("commit", "-qm", "Save a basket")
    teammate.git("push", "-q", "origin", "task/SHOP-SAVE")
    head = teammate.git("rev-parse", "HEAD")
    categories = ("building", "own_tests", "reviewing", "fixing_findings", "waiting_for_ci",
                  "waiting_in_line", "waiting_for_owner", "nothing_running")
    summary = {"round": 9, "until": "2026-10-01T00:00:00+00:00", "known": True, "seen": [],
               "working_seconds": None, "waiting_seconds": None, "unknown_seconds": None, "total_seconds": None,
               "time_breakdown": dict.fromkeys(categories), "intervals": [],
               "rounds": [{"first": 1, "last": 8, "round": None, "worker_round": None,
                           "line": "Rounds 1–8: reviewing; findings: 0 new, 0 repeated", "seconds": {},
                           "new_findings": 0, "repeat_findings": 0},
                          {"round": 9, "worker_round": 9, "line": "Round 9: review clean", "seconds": {},
                           "new_findings": 0, "repeat_findings": 0}]}
    start, end = "2026-10-01T00:00:00+00:00", "2026-10-01T00:02:00+00:00"
    events = [{"id": "phase", "event": "work phase", "phase": "reviewing", "round": 10, "at": start},
              {"id": "review-start", "event": "run start", "kind": "review", "round": 10, "at": start},
              {"id": "review-end", "event": "run end", "run_id": "review-start", "kind": "review", "round": 10, "at": end},
              {"id": "review-result", "event": "review result", "round": 10, "review_round": 10,
               "at": end, "outcome": "clean", "findings": [{"priority": "P2", "file": "basket.py", "title": kept[0]["title"]}]}]
    record = {"ready": {"commit": head, "review": "clean"}, "summary": summary, "events": events,
              "timings": [{"step": "review", "round": 10, "start": start, "seconds": 120, "outcome": "clean"}]}
    github(SimpleNamespace(repo=client, gh=gh), [{"number": 7, "headRefName": "task/SHOP-SAVE",
        "headRefOid": head, "state": "OPEN", "title": "Save a basket", "isDraft": False,
        "body": "<!-- forge:begin -->\n<!-- forge:time-record " + json.dumps(record) + " -->\n<!-- forge:end -->"}])
    client.git("fetch", "-q", "origin")
    alpha = fix(client, "alpha")
    # A stopped close can name a command in its diagnostic reason. The drawer shows
    # the board's status, not this terminal advice.
    record_path = alpha / ".factory/fixes/alpha.json"
    state = json.loads(record_path.read_text("utf-8"))
    record_path.write_text(json.dumps({**state, "status": "fixing",
                                     "reason": "Run forge test --pytest main"}), encoding="utf-8")
    client.git("add", "-A", cwd=alpha)
    client.git("commit", "-qm", "Record a stopped close", cwd=alpha)
    with (client.path / ".git/forge/events.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps({"id": "question", "item": "SHOP/SAVE", "event": "worker question",
                              "at": end, "round": 10, "question": "Does forge test --pytest main cover this?"}) + "\n")
    with live(client, FORGE_BOARD_FETCH_WAIT="3600", FORGE_NOW=end) as url:
        rows = {row["id"]: row for parent in snapshot(url)["items"] for row in (parent, *parent["children"])}
        assert rows["SHOP"]["stage"] == "ready to merge", rows["SHOP"]
        assert rows["OLD"]["merged_at"] is None and rows["OLD"]["merged_by"] is None
        assert "forge test" in rows["alpha"]["waits_on"]
        assert len(rows["SHOP/SAVE"]["rounds"]) == 3, rows["SHOP/SAVE"]["rounds"]
        shown = subprocess.run([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                                "playwright==1.55.0", "--with", "axe-playwright-python==0.1.4", "python", "-c",
                                SCRIPT, url], capture_output=True, text=True, encoding="utf-8", timeout=300)
        assert shown.returncode == 0, shown.stdout + shown.stderr
