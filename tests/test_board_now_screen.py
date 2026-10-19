"""The board's first screen in real Chrome on `forge board`'s live page: what needs you, the items in
flight by stage with a count where a stage is too long, the stories with their parts and owners, and
four figures, in one laptop window; the Team and Me views; and its own words, keyboard and themes.
Only GitHub is faked, at the stub `gh`; the records are written the way Forge writes them."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone

import board_fixture
from conftest import REAL_UV, Repo
from test_board_server import client, clone, fix, live, pushed, snapshot  # noqa: F401

STORY = "FORGE-BOARD-4"

# The stages as the plan places Forge's states: started parts and fixes by their stage, and parts
# on a plan that nobody started by their plan status.
STAGE = {"unstarted": "Planned", "started": "Planned", "Not started": "Planned", "Waiting": "Planned",
         "Can start now": "Planned", "working": "Building", "fixing": "Building", "checks failed": "Building",
         "reviewing": "Review", "waiting for checks": "Review", "hotspot": "Review", "ready": "Ready",
         "merged": "Merged", "done": "Merged"}

BROWSER = r"""
import json, re, sys
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect, sync_playwright
url, mode, expected = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
BOARD = "(await import(new URL('app.js' + location.search, location.href))).Board"

SEEN = '''() => {
  const seen = [], range = document.createRange();
  const measure = document.createElement('canvas').getContext('2d');
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    let right = innerWidth, bottom = innerHeight;
    for (let at = node.parentElement; at && at !== document.body; at = at.parentElement) {
      const style = getComputedStyle(at);
      if (style.overflow === 'visible') continue;
      const box = at.getBoundingClientRect();
      let edge = box.right - parseFloat(style.borderRightWidth);
      // Text under the painted ellipsis is hidden, even when its range fits
      // inside the element. Its width follows the platform's actual font.
      if (style.textOverflow === 'ellipsis' && at.scrollWidth > at.clientWidth) {
        measure.font = style.font;
        edge -= parseFloat(style.paddingRight) + measure.measureText('…').width;
      }
      right = Math.min(right, edge);
      bottom = Math.min(bottom, box.bottom);
    }
    for (const word of node.textContent.matchAll(/\\S+/g)) {
      if (!/[A-Za-z]/.test(word[0]) || /^[A-Z][A-Z0-9-]*-[0-9]+$/.test(word[0])) continue;
      range.setStart(node, word.index);
      range.setEnd(node, word.index + word[0].length);
      const box = range.getBoundingClientRect();
      if (!box.width || box.bottom > innerHeight) continue;
      if (box.right > right + 1 || box.bottom > bottom + 1) continue;
      seen.push(word[0]);
    }
  }
  return seen;
}'''

SPILLS = '''() => [...document.querySelectorAll('main button')].flatMap(card => {
  const box = card.getBoundingClientRect();
  return [...card.querySelectorAll('*')].filter(part => {
    const at = part.getBoundingClientRect();
    return at.width && (at.left < box.left - 1 || at.right > box.right + 1 || at.bottom > box.bottom + 1);
  }).map(part => card.textContent + ': ' + part.textContent);
})'''

def opened(page, url, scheme):
    page.goto(url)
    expect(page.get_by_role('status')).to_have_text('Live', timeout=60000)
    expect(page.get_by_role('region', name='In flight')).to_be_visible()
    return page

def tab_to(page, focus, limit=120):
    for _ in range(limit):
        page.keyboard.press('Tab')
        if page.evaluate('document.activeElement.dataset.focus') == focus:
            return
    raise AssertionError(f'Tab never reached {focus}')

def accessible(page):
    found = Axe().run(page, options={'runOnly': ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']}).response['violations']
    assert not found, [(v['id'], [n['target'] for n in v['nodes']][:3]) for v in found]

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        page = opened(browser.new_page(viewport={'width': 1440, 'height': 900}, color_scheme='light'), url, 'light')
        if mode == 'client':
            # One laptop window, no scrolling, and about 120 words a reader sees: not numbers, not story
            # keys, and not the hidden end of a title cut to one line.
            assert page.evaluate('document.documentElement.scrollHeight <= innerHeight'), 'the page scrolls'
            words = page.evaluate(SEEN)
            assert 100 <= len(words) <= 130, (len(words), ' '.join(words))
            # Every card keeps its title, key and tag inside its own box, and Merged counts one set:
            # the merged items of the last 7 days, shown and in its "and N more".
            spills = page.evaluate(SPILLS)
            assert not spills, spills
            merged = page.get_by_role('region', name='Merged', exact=True)
            shown = merged.get_by_role('listitem').count()
            rest = merged.get_by_role('button', name=re.compile('^and [0-9]+ more$'))
            hidden = int(rest.inner_text().split()[1]) if rest.count() else 0
            assert merged.get_by_role('heading').inner_text().split()[-1] == str(shown + hidden) == \
                page.get_by_role('region', name='Figures').inner_text().split()[0], (shown, hidden)
            text = page.locator('body').inner_text()
            # The board's own words carry no command text, and an unknown fact says unknown.
            assert not re.search(r'\bforge [a-z]|--[a-z]|`', text), text  # a command, never the Forge name
            assert 'unknown median item' in ' '.join(page.get_by_role('region', name='Figures').inner_text().split())
            for name, count in expected['stages'].items():
                region = page.get_by_role('region', name=name, exact=True)
                if count > 4:
                    expect(region.get_by_role('button', name=f'and {count - 4} more')).to_be_visible()
            expect(page.get_by_role('region', name='Stories').get_by_role(
                'button', name=f"and {expected['stories'] - 5} more")).to_be_visible()
            expect(page.get_by_role('region', name='Planned', exact=True).get_by_text('can start').first).to_be_visible()
            # The keyboard opens a long stage in full, reaches its last item, and Escape closes it.
            tab_to(page, 'more:building')
            page.keyboard.press('Enter')
            full = page.get_by_role('dialog', name=f"Building, all {expected['stages']['Building']}")
            expect(full).to_be_visible()
            tab_to(page, 'list:' + expected['last_building'], expected['stages']['Building'] + 5)
            assert page.evaluate('document.activeElement.getBoundingClientRect().bottom <= innerHeight')
            page.keyboard.press('Escape')
            expect(full).to_be_hidden()
            assert page.evaluate('document.activeElement.dataset.focus') == 'more:building'
            # Enter on a card opens its detail beside the cards.
            page.evaluate("async () => { const Board = " + BOARD + "; Board.openDrawer = id => { window.drawer = id; }; }")
            page.keyboard.press('Shift+Tab')
            page.keyboard.press('Enter')
            assert page.evaluate('window.drawer'), 'a card did not open'
            accessible(page)
            dark = opened(browser.new_page(viewport={'width': 1440, 'height': 900}, color_scheme='dark'), url, 'dark')
            assert dark.evaluate('document.documentElement.scrollHeight <= innerHeight'), 'the dark page scrolls'
            accessible(dark)
        else:
            figures = page.get_by_role('region', name='Figures')
            for line in expected['figures']:
                expect(figures).to_contain_text(line)
            expect(page.get_by_role('region', name='Building', exact=True).get_by_text('checks failed')).to_be_visible()
            flight = page.get_by_role('region', name='In flight')
            page.get_by_role('button', name='Fixes', exact=True).click()
            expect(flight).to_contain_text('Readers see theirs')
            page.get_by_role('button', name='Me', exact=True).click()
            expect(page.get_by_role('region', name='Needs you')).to_contain_text('@asha')
            expect(flight).to_contain_text('Readers see mine')
            expect(flight).not_to_contain_text('Readers see theirs')
            accessible(page)
    finally:
        browser.close()
"""


def look(url, mode, expected):
    shown = subprocess.run([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with", "playwright==1.55.0",
                            "--with", "axe-playwright-python==0.1.4", "python", "-c", BROWSER, url, mode,
                            json.dumps(expected)], capture_output=True, text=True, encoding="utf-8", timeout=300)
    assert shown.returncode == 0, shown.stdout + shown.stderr


def test_12_the_first_screen_fits_a_laptop_window_and_keeps_every_item_reachable(repo, gh, tmp_path):
    """The client-sized repo: 44 stories, 10 open fixes and six weeks of merges, plus one approved story
    with a long key whose first part can start, so a long key and a tag share one card."""
    (tmp_path / "shop").mkdir()
    shop = Repo(board_fixture.build(tmp_path / "shop", repo.forge("--version").stdout.split()[-1]), repo.bin)
    long = "SHOP-DELIVERY-SLOTS-12"
    plan = shop.path.joinpath("plans/SHOP-1.md").read_text(encoding="utf-8").replace("shop-1", long.lower())
    shop.write(f"plans/{long}.md", plan.replace("Shoppers can save a basket", "Couriers book a delivery slot", 1))
    shop.write(f".factory/stories/{long}/story.json", json.dumps({
        "doc": f"plans/{long}.md", "title": "Couriers book a delivery slot", "status": "approved",
        "approval": {"at": datetime.now(timezone.utc).isoformat()}}))
    roadmap = json.loads(shop.path.joinpath("plans/roadmap.json").read_text(encoding="utf-8"))
    roadmap["items"].insert(0, {"key": long, "title": "Couriers book a delivery slot"})  # first in Planned
    shop.write("plans/roadmap.json", json.dumps(roadmap, indent=2))
    shop.git("add", "-A")
    shop.git("commit", "-qm", "Plan delivery slots")
    shop.git("push", "-q", "origin", "main")
    gh.respond("pr", "list", stdout="[]")
    gh.respond("api", "graphql", stdout=json.dumps({"data": {"repository": {"pullRequests": {"nodes": []}}}}))
    with live(shop) as url:
        board = snapshot(url)
        rows = [row for item in board["items"] for row in (item["children"] if item["kind"] == "story" else [item])]
        known = {row["id"] for row in rows}
        unstarted = [part for plan in board["dependency_maps"] if plan["id"] != "fixes" and plan["stage"] != "done"
                     for part in plan["parts"] if part["id"] not in known and STAGE.get(part["status"]) == "Planned"]
        stages = {name: [row for row in rows + unstarted if STAGE[row.get("stage") or row["status"]] == name]
                  for name in ("Planned", "Building")}
        assert len(stages["Planned"]) > 6 and len(stages["Building"]) > 6, stages
        stories = [plan for plan in board["dependency_maps"] if plan["id"] != "fixes"
                   and plan["stage"] not in ("done", "needs a spec")]
        look(url, "client", {"stages": {name: len(found) for name, found in stages.items()},
                             "last_building": stages["Building"][-1]["id"], "stories": len(stories)})


def merged_fixes(repo, tmp_path, times):
    """Fixes merged an hour ago, each (hours long, seconds of it waiting for a person), written as a
    merged fix's record on the default branch and the events Forge logs while it waits and finishes."""
    end = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=1)
    events, records = [], {}
    for n, (took, waited) in enumerate(times, 1):
        records[f".factory/fixes/done-{n}.json"] = json.dumps({
            "kind": "fix", "branch": f"fix/done-{n}", "status": "merged", "why": f"Readers see total {n}",
            "done_when": "It shows", "steps": [{"step": "start", "at": (end - timedelta(hours=took)).isoformat()}]})
        events += [{"id": f"wait-{n}", "item": f"done-{n}", "event": "owner wait start", "reason": "merge",
                    "at": (end - timedelta(seconds=waited)).isoformat()},
                   {"id": f"waited-{n}", "item": f"done-{n}", "event": "owner wait end", "wait_id": f"wait-{n}",
                    "at": end.isoformat()},
                   {"id": f"end-{n}", "item": f"done-{n}", "event": "item finished", "at": end.isoformat()}]
    pushed(clone(repo, tmp_path), "Merge three fixes", records)
    repo.git("fetch", "-q", "origin")
    with (repo.path / ".git/forge/events.jsonl").open("a", encoding="utf-8") as log:
        log.writelines(json.dumps(event) + "\n" for event in events)


def test_13_the_figures_and_the_me_view_follow_forges_records(client, gh, tmp_path):
    """Three fixes merged this week took 1, 2 and 9 hours and waited 10, 30 and 60 minutes for a person:
    a median of 2 h and 6000 of 43200 seconds waiting. One open fix's checks fail. The viewer, asha,
    opened one of the two open fixes, so Me shows only that one."""
    merged_fixes(client, tmp_path, [(1, 600), (2, 1800), (9, 3600)])
    fix(client, "mine")
    fix(client, "theirs")

    def opened(slug, login, outcome):
        head = client.git("rev-parse", f"fix/{slug}")
        return {"number": len(slug), "headRefName": f"fix/{slug}", "headRefOid": head, "state": "OPEN",
                "title": f"Readers see {slug}", "body": "", "isDraft": False, "author": {"login": login},
                "url": f"https://github.com/acme/shop/pull/{len(slug)}", "commits": {"nodes": [{"commit": {
                    "oid": head, "statusCheckRollup": {"contexts": {"pageInfo": {"hasNextPage": False}, "nodes": [
                        {"name": "tests", "status": "COMPLETED", "conclusion": outcome}]}}}}]}}

    gh.respond("api", "graphql", stdout=json.dumps({"data": {"repository": {"pullRequests": {"nodes": [
        opened("mine", "asha", "SUCCESS"), opened("theirs", "ben", "FAILURE")]}}}}))
    gh.respond("api", "user", stdout="asha\n")
    with live(client) as url:
        # The earlier-adopted repo also merged its upgrade fix this week, with no recorded time.
        board = snapshot(url)
        merged = sum(board["team"]["counts"]["finished_last_7_days"].values())
        timed = [row["id"] for row in board["items"] if row["stage"] == "merged" and row["total_seconds"] is not None]
        assert merged >= 3 and sorted(timed) == ["done-1", "done-2", "done-3"], (merged, timed)
        look(url, "figures", {"figures": [f"{merged} merged, 7 days", "2 h median item", "13.9% waiting on people",
                                          "1 red checks"]})
