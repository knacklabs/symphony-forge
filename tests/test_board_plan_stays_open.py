"""A board refresh leaves the reader's place alone. An open plan survives changed snapshots until the
reader closes it. A refresh replaces only the part of a screen that changed, also when something else on
the screen changed: a plan, the Releases page and the first screen keep their scroll, selection, open
sections and elements. A story's full page keeps its older parts, a failed run's row opens the newest
run, and the four changed screens pass the shipped rendered check.

Test audit: replacing native details loses reading state. Existing keyboard tests
restore focused links and miss reading without focus inside the fold. This uses
the real command, server and browser, with no new production test seam. Test 7 changes the board's own
answer at the browser's network edge, because the board reads GitHub once in ten minutes; GitHub is
faked at the stub gh for the first answer.
"""
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from conftest import REAL_UV, ROOT
from test_board import DOC
from test_board_counts import github
from test_board_item_page import PLAN
from test_board_item_keyboard_refresh import stop_tree
from test_failed_full_run_row_opens_run import FORGE_RUNS, TITLE, URL
from test_render_check import installed, prepare, run  # noqa: F401  (installed is a fixture)
from test_uistandards_canvas import _browser
from test_board_releases_known_issues_fit import FILES, KEPT
from test_board_server import client, clone, live, pushed  # noqa: F401

STORY = "FIX-BOARD-FOLD-STAYS-OPEN"
pytestmark = pytest.mark.platform

SCRIPT = r"""
import re, subprocess, sys
from pathlib import Path
from playwright.sync_api import expect, sync_playwright
url, teammate, client = sys.argv[1:]
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.goto(url + '#item/SHOP')
        page.get_by_role('tab', name='Plan', exact=True).click()
        fold = page.locator('article.plan details')
        expect(fold).not_to_have_attribute('open', '')
        for owner, opened in [('reader-one', True), ('reader-two', False)]:
            fold.locator('summary').click()
            page.get_by_role('tab', name='Plan', exact=True).focus()
            path = Path(teammate) / 'plans' / 'SHOP.md'
            path.write_text(re.sub(r'Owner: [^\n]+', 'Owner: ' + owner,
                                  path.read_text(encoding='utf-8')), encoding='utf-8')
            for cwd, args in [(teammate, ['add', '-A']), (teammate, ['commit', '-qm', 'Change owner']),
                              (teammate, ['push', '-q', 'origin', 'HEAD:main']), (client, ['fetch', '-q', 'origin'])]:
                subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True)
            expect(page.get_by_text('Owner ' + owner, exact=True)).to_be_visible(timeout=60000)
            expect(page.locator('article.plan')).to_contain_text('Owner: ' + owner)  # the plan's own words changed
            expect(page.get_by_role('link', name='the guide', include_hidden=True)).to_have_count(1)
            if opened:
                expect(fold).to_have_attribute('open', '')
            else:
                expect(fold).not_to_have_attribute('open', '')
    finally:
        browser.close()
"""


@pytest.mark.timeout(240)
def test_1_open_builders_section_stays_open_until_person_closes_it(client, tmp_path):
    teammate = clone(client, tmp_path)
    pushed(teammate, "Plan a basket", {"plans/SHOP.md": PLAN, ".factory/stories/SHOP/story.json":
           json.dumps({"doc": "plans/SHOP.md", "title": "Shoppers can save a basket", "status": "approved"})})
    client.git("fetch", "-q", "origin")
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        shown = subprocess.Popen([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                                "playwright==1.55.0", "python", "-c", SCRIPT, url,
                                str(teammate.path), str(client.path)], stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                 start_new_session=os.name != "nt")
        try:
            out, err = shown.communicate(timeout=180)
        finally:
            if shown.poll() is None:
                stop_tree(shown)
                shown.communicate(timeout=30)
        assert shown.returncode == 0, out + err


# The refresh tests share one browser harness. A refresh is a teammate's commit that the board reads. It either
# changes no file the board shows or lands a fix beside what the reader is doing; the page must keep
# everything the reader is doing either way.
PRELUDE = r"""
import json, re, subprocess, sys
from pathlib import Path
from playwright.sync_api import expect, sync_playwright
url, teammate, client = sys.argv[1:4]
step = 0

def fix(kind, status):
    # A fix record that a teammate lands: a merged one changes the Releases page, a working one the first screen.
    n = step + 1
    return {f'.factory/fixes/{kind}-{n}.json': json.dumps({'kind': 'fix', 'branch': f'fix/{kind}-{n}',
            'why': f'Parts load faster {n}', 'done_when': 'Parts are fast', 'status': status})}

def git(cwd, *args):
    subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True, encoding='utf-8')

def watch(page):
    # Counts the board's snapshots and finished reads, and notes any loading line that shows.
    page.evaluate('''async () => {
      const { Board } = await import(new URL('app.js' + location.search, location.href));
      window.__version = 0; window.__reads = []; window.__loading = [];
      Board.onSnapshot((snapshot) => { window.__version = snapshot.snapshot.version; });
      new PerformanceObserver((list) => list.getEntries().forEach((e) => window.__reads.push(e.name))).observe({ type: 'resource' });
      new MutationObserver(() => {
        for (const one of document.querySelectorAll('.quiet, .note')) {
          if (/^Reading /.test(one.textContent)) window.__loading.push(one.textContent);
        }
      }).observe(document.body, { childList: true, subtree: true, characterData: true });
    }''')

def refresh(page, reads, files=None, branch=None):
    # Lands one commit (on main, or on a new branch of its own), then waits until the page has taken the new
    # snapshot and drawn each answer it asked for.
    global step
    step += 1
    before, seen = page.evaluate('window.__version'), page.evaluate('window.__reads.length')
    if branch:
        git(teammate, 'switch', '-qc', branch + str(step))
    for name, text in (files or {'notes.txt': 'note ' + str(step) + chr(10)}).items():
        Path(teammate, name).parent.mkdir(parents=True, exist_ok=True)
        Path(teammate, name).write_text(text, encoding='utf-8')
    for args in (['add', '-A'], ['commit', '-qm', 'Change ' + str(step)], ['push', '-q', 'origin', 'HEAD' + (':main' if not branch else '')]):
        git(teammate, *args)
    if branch:
        git(teammate, 'switch', '-q', 'main')
    git(client, 'fetch', '-q', 'origin')
    page.wait_for_function('(n) => window.__version > n', arg=before, timeout=60000)
    for name in reads:
        page.wait_for_function('([n, name]) => window.__reads.slice(n).some((u) => u.includes(name))', arg=[seen, name], timeout=60000)
    page.evaluate('new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))')

def stays(page, same, scrolls, open_sections, words=None):
    # The same elements, the same scroll, the open sections still open, the selection still selected.
    assert page.evaluate('(keys) => keys.every((key) => window[key] && window[key].isConnected)', same), 'an element was replaced'
    for selector, top in scrolls.items():
        now = page.evaluate('(s) => Math.round(s === "window" ? scrollY : document.querySelector(s).scrollTop)', selector)
        assert now == top, (selector, top, now)
    for selector in open_sections:
        expect(page.locator(selector)).to_have_attribute('open', '')
    if words is not None:
        assert page.evaluate('getSelection().toString()') == words, 'the selection changed'
    assert page.evaluate('window.__loading') == [], 'a loading line showed over the page'
"""


def shown(script, url, teammate, client, *more):
    # Its own process group, so a stop also ends uv's Python and the browser it started.
    process = subprocess.Popen([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                                "playwright==1.55.0", "python", "-c", PRELUDE + script, url,
                                str(teammate.path), str(client.path), *more], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, encoding="utf-8",
                               start_new_session=os.name != "nt")
    try:
        out, err = process.communicate(timeout=300)
    finally:
        if process.poll() is None:
            stop_tree(process)
            process.communicate(timeout=30)
    assert process.returncode == 0, out + err


def story_json(title):
    return json.dumps({"doc": "plans/SHOP.md", "title": title, "status": "approved"})


def shop(client, gh, tmp_path, plan):
    """A story with one part under way, as a teammate planned and started it."""
    teammate = clone(client, tmp_path)
    pushed(teammate, "Plan a basket", {"plans/SHOP.md": plan,
                                       ".factory/stories/SHOP/story.json": story_json("Shoppers can save a basket")})
    teammate.git("switch", "-qc", "task/SHOP-SAVE")
    teammate.write(".factory/stories/SHOP/tasks/SAVE.json", json.dumps({
        "status": "waiting for checks", "branch": "task/SHOP-SAVE"}))
    teammate.git("add", "-A")
    teammate.git("commit", "-qm", "Save a basket")
    teammate.git("push", "-q", "origin", "task/SHOP-SAVE")
    github(SimpleNamespace(repo=client, gh=gh), [{"number": 7, "headRefName": "task/SHOP-SAVE",
        "headRefOid": teammate.git("rev-parse", "HEAD"), "state": "OPEN", "title": "Save a basket",
        "isDraft": False, "url": "https://github.com/shop/basket/pull/7", "body": ""}])
    teammate.git("switch", "-q", "main")
    client.git("fetch", "-q", "origin")
    return teammate


# A plan long enough to read far down, with a builders section that folds.
LONG = PLAN.replace("Hostile:", "\n\n".join(f"Builder note {n}. " + "It says what to build. " * 20 for n in range(1, 61))
                    + "\n\nHostile:", 1)

PLAN_PAGE = r"""
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.goto(url + '#item/SHOP')
        expect(page.get_by_role('status')).to_have_text('Live', timeout=60000)
        page.get_by_role('tab', name='Plan', exact=True).click()
        fold = page.locator('article.plan details')
        fold.locator('summary').click()
        expect(fold).to_have_attribute('open', '')
        watch(page)
        # Far down inside the builders section, with one paragraph of it selected.
        words = page.evaluate('''() => {
          const note = document.querySelectorAll('article.plan details p')[40];
          note.scrollIntoView({ block: 'start' });
          getSelection().selectAllChildren(note);
          window.__plan = document.querySelector('article.plan');
          window.__panel = document.querySelector('[role=tabpanel]');
          window.__fold = document.querySelector('article.plan details');
          return getSelection().toString();
        }''')
        top = page.evaluate('Math.round(scrollY)')
        assert top > 2000 and words.startswith('Builder note'), (top, words)
        same, folds = ['__plan', '__panel', '__fold'], ['article.plan details']
        for _ in range(3):
            refresh(page, ['plan/SHOP'])
            stays(page, same, {'window': top}, folds, words)
        # A real change: the plan names a new owner, in a block other than the selected one. The plan is read
        # again and shows the new words, but the plan, its tab, the open section, the scroll and the selected
        # words stay where the reader left them.
        plan = Path(teammate, 'plans', 'SHOP.md')
        refresh(page, ['plan/SHOP'], {'plans/SHOP.md': re.sub('Owner: [^' + chr(10) + ']+', 'Owner: reader-one', plan.read_text(encoding='utf-8'))})
        expect(page.locator('article.plan')).to_contain_text('Owner: reader-one')
        stays(page, ['__plan', '__panel', '__fold'], {'window': top}, folds, words)
    finally:
        browser.close()
"""


@pytest.mark.timeout(480)
def test_2_a_plan_keeps_its_scroll_selection_and_open_section_through_refreshes(client, gh, tmp_path):
    teammate = shop(client, gh, tmp_path, LONG)
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        shown(PLAN_PAGE, url, teammate, client)


OPENS = r"""
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        asked = []
        page.on('request', lambda request: asked.append(request.url))
        page.goto(url)
        expect(page.get_by_role('status')).to_have_text('Live', timeout=60000)
        watch(page)
        # From the first screen: a card opens the drawer, and its history link opens the full page.
        page.get_by_role('button', name=re.compile('^Save a basket')).first.click()
        page.get_by_role('link', name='Full history').click()
        expect(page.get_by_role('heading', level=1, name='Save a basket')).to_be_visible()
        assert not [one for one in asked if 'page=item' in one], 'the page asked the server for an item it already held'
        assert page.evaluate('window.__loading') == [], 'a loading line showed'
    finally:
        browser.close()
"""


@pytest.mark.timeout(300)
def test_3_the_full_item_page_opens_from_the_item_the_page_holds(client, gh, tmp_path):
    teammate = shop(client, gh, tmp_path, PLAN)
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        shown(OPENS, url, teammate, client)


def moving_machine(repo):
    """Every read of the machine's load and memory gives a new number, as a busy laptop does. The test launcher
    freezes them, so this changes the board command's launcher, as machine_cores does, with no flag in the program."""
    shim = repo.bin / "forge"
    shim.write_text(shim.read_text("utf-8").replace("from forge.cli import main", (
        "import itertools\nreading = itertools.count(1)\nos.getloadavg = lambda: (next(reading) / 100, 0.0, 0.0)\n"
        "machine.memory = lambda: dict(total_bytes=16_000_000_000, available_bytes=8_000_000_000 - next(reading))\n"
        "from forge.cli import main"), 1), "utf-8")


RELEASES = r"""
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.goto(url + '#releases')
        expect(page.get_by_role('status')).to_have_text('Live', timeout=60000)
        kept = page.get_by_role('region', name='Known issues by file')
        expect(kept).to_be_visible()
        watch(page)
        kept.get_by_role('button', name=re.compile('^and \\d+ more')).click()
        full = page.get_by_role('dialog', name=re.compile('^Known issues by file, all'))
        expect(full).to_be_visible()
        # Far down the list of files, with one file open.
        page.evaluate('document.querySelector("section.known.list").scrollTop = 600')
        full.locator('summary').nth(14).click()
        selector = 'section.known.list li:nth-child(15) details'
        expect(page.locator(selector)).to_have_attribute('open', '')
        top = page.evaluate('Math.round(document.querySelector("section.known.list").scrollTop)')
        assert top > 0, top
        page.evaluate('''() => {
          window.__list = document.querySelector('section.known.list');
          window.__file = document.querySelector('section.known.list li:nth-child(15) details');
        }''')
        # The first refresh changes nothing the page shows (the answer still differs: the machine's readings move
        # and other work is unfinished). The next two land a merged fix, which changes the page beside the open file.
        for visible in (False, True, True):
            before = page.locator('.big').text_content()
            refresh(page, ['page=releases'], fix('merged', 'merged') if visible else None)
            if visible:
                expect(page.locator('.big')).not_to_have_text(before)
            stays(page, ['__list', '__file'], {'section.known.list': top}, [selector])
    finally:
        browser.close()
"""


@pytest.mark.timeout(300)
def test_4_the_releases_page_keeps_its_open_file_and_scroll_through_refreshes(client, tmp_path):
    teammate = clone(client, tmp_path)
    pushed(teammate, "Add the parts and their kept problems", {
        **{file: "x = 1\n" for file in FILES},
        ".factory/fixes/old.json": json.dumps({"kind": "fix", "branch": "fix/old", "why": "Parts are slow",
                                               "done_when": "Parts are fast", "status": "merged", "known": KEPT}),
        ".factory/fixes/open.json": json.dumps({"kind": "fix", "branch": "fix/open", "why": "Parts load slowly",
                                                "done_when": "Parts load fast", "status": "working"})})
    client.git("fetch", "-q", "origin")
    client.git("merge", "-q", "--ff-only", "origin/main")
    moving_machine(client)
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        shown(RELEASES, url, teammate, client)


# A story with thirty parts nobody started, so Planned is a long list on the first screen.
MANY = DOC.replace("## Tasks\n", "## Tasks\n\nOwner: page-dev\n", 1)
MANY = MANY[:MANY.index("| SAVE |")] + "\n".join(
    f"| T{n:02} | Part {n} | Delivers {n} | 1 | `src/t{n}.py` | `tests/test_t{n}.py` | none | no |"
    for n in range(1, 31)) + "\n" + MANY[MANY.index("\nNew moving parts"):]

FIRST_SCREEN = r"""
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.goto(url)
        expect(page.get_by_role('status')).to_have_text('Live', timeout=60000)
        watch(page)
        page.get_by_role('region', name='Planned').get_by_role('button', name=re.compile('^and \\d+ more')).click()
        full = page.get_by_role('dialog', name=re.compile('^Planned, all'))
        expect(full).to_be_visible()
        page.evaluate('document.querySelector(".now .list ul").scrollTop = 500')
        top = page.evaluate('Math.round(document.querySelector(".now .list ul").scrollTop)')
        assert top > 0, top
        page.evaluate('window.__now = document.querySelector(".now"); window.__list = document.querySelector(".now .list ul")')
        building = page.locator('section.stage', has_text='Building').locator('.count')
        # One refresh that changes nothing, then two that add a card and change a count beside the open list.
        for visible in (False, True, True):
            before = building.text_content()
            refresh(page, [], fix('work', 'working') if visible else None, 'fix/work-' if visible else None)
            if visible:
                expect(building).not_to_have_text(before)
            stays(page, ['__now', '__list'], {'.now .list ul': top}, [])
    finally:
        browser.close()
"""


@pytest.mark.timeout(300)
def test_5_the_first_screen_keeps_the_scroll_of_its_long_list_through_refreshes(client, tmp_path):
    teammate = clone(client, tmp_path)
    pushed(teammate, "Plan thirty parts", {"plans/SHOP.md": MANY, ".factory/stories/SHOP/story.json":
                                           story_json("Shoppers can save a basket")})
    client.git("fetch", "-q", "origin")
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        shown(FIRST_SCREEN, url, teammate, client)


# A story that is still under way, with one part merged ten days ago: the first screen's board leaves that
# part out, and the story's full page must still list it.
OLDER_PLAN = DOC.replace("| SHOW |", "| OLD | Remember old baskets | Old baskets stay | 1 | `src/old.py` | `tests/test_old.py` | none | no |\n| SHOW |", 1)

OLDER = r"""
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        old = page.get_by_role('button', name='Remember old baskets')
        page.goto(url)
        expect(page.get_by_role('status')).to_have_text('Live', timeout=60000)
        # From the first screen the page opens from the story it holds, then adds the older part.
        page.get_by_role('button', name=re.compile('^Shoppers can save a basket')).first.click()
        page.get_by_role('link', name='Full history').click()
        expect(page.get_by_role('heading', level=1, name='Shoppers can save a basket')).to_be_visible()
        expect(old).to_be_visible(timeout=60000)
        watch(page)
        refresh(page, [])
        expect(old).to_be_visible()  # a new snapshot leaves the older part listed
        # Opened by its address, the page has no story yet, reads the whole story and keeps it through a refresh.
        page.goto(url + '#item/SHOP')
        page.reload()
        expect(old).to_be_visible(timeout=60000)
        watch(page)
        refresh(page, [])
        expect(old).to_be_visible()
    finally:
        browser.close()
"""


@pytest.mark.timeout(300)
def test_6_a_storys_full_page_keeps_the_parts_merged_over_a_week_ago(client, gh, tmp_path, monkeypatch):
    teammate = shop(client, gh, tmp_path, OLDER_PLAN)
    monkeypatch.setenv("GIT_COMMITTER_DATE", (datetime.now(timezone.utc) - timedelta(days=10)).isoformat())
    pushed(teammate, "Merge the old part", {".factory/stories/SHOP/tasks/OLD.json": json.dumps({
        "status": "merged", "branch": "task/SHOP-OLD"})})
    monkeypatch.delenv("GIT_COMMITTER_DATE")
    client.git("fetch", "-q", "origin")
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        shown(OLDER, url, teammate, client)


# The full test run fails again while its first failure is on the screen: the same workflow, branch, words and
# state, and a new run to open.
AGAIN = "https://github.com/acme/shop/actions/runs/42"

FAILED_AGAIN = r"""
again = sys.argv[4]
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        context.route('https://github.com/**', lambda route: route.fulfill(
            status=200, content_type='text/html', body='<title>The run</title>'))
        newest = []

        def snapshot(route):
            # The board's own answer for the first screen, with the address of the newest failed run once there is one.
            answer = route.fetch()
            body = answer.json()
            for entry in body['team']['needs_you']:
                if entry['kind'] == 'run' and newest:
                    entry['url'] = newest[0]
            route.fulfill(response=answer, json=body)
        context.route(lambda address: '/board.json' in address and 'page=' not in address, snapshot)
        page = context.new_page()
        page.goto(url)
        expect(page.get_by_role('status')).to_have_text('Live', timeout=60000)
        row = page.get_by_role('region', name='Needs you').get_by_role('button', name='Fix Full test run ' + sys.argv[5])
        expect(row).to_be_visible()
        watch(page)
        newest.append(again)
        refresh(page, [])
        with context.expect_page() as opened:
            row.click()
        opened.value.wait_for_load_state()
        assert opened.value.url == again, opened.value.url
    finally:
        browser.close()
"""


@pytest.mark.timeout(300)
def test_7_a_failed_run_row_opens_the_newest_failed_run_after_a_refresh(client, gh, tmp_path):
    busy = [{"id": 1000 + n, "workflow_id": 9, "name": "backup", "event": "schedule", "conclusion": "success",
             "head_branch": "main", "path": ".github/workflows/backup.yml",
             "created_at": f"2025-01-0{1 + n // 24}T{n % 24:02d}:30:00Z"} for n in range(100)]
    failed = {"id": 41, "workflow_id": 1, "name": "forge", "event": "schedule", "conclusion": "failure",
              "run_attempt": 1, "head_branch": "main", "path": ".github/workflows/forge.yml",
              "created_at": "2026-01-01T03:00:00Z", "html_url": URL}
    gh.respond("api", "repos/{owner}/{repo}/actions/runs", "--method", "GET", stdout=json.dumps({"workflow_runs": busy}))
    gh.respond(*FORGE_RUNS, "event=schedule", stdout=json.dumps({"workflow_runs": [failed]}))
    gh.respond(*FORGE_RUNS, "event=workflow_dispatch", stdout=json.dumps({"workflow_runs": []}))
    gh.respond("run", "view", "41", stdout="full suite\tRun tests\t2030-01-01T03:40:00Z FAILED tests/test_a.py::test_one - boom")
    teammate = clone(client, tmp_path)
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        shown(FAILED_AGAIN, url, teammate, client, AGAIN, TITLE)


# The shipped rendered check opens each screen this fix changed, in light and dark, on the board's own data.
SCREENS = [("now", ""), ("item", "#item/SHOP"), ("releases", "#releases"), ("insights", "#insights")]
# A card title on the first screen ends in an ellipsis by design (one line, cut). Whole titles are another fix.
WAIVE = {"now": {"cut-text": "Card titles end in an ellipsis on one line; showing whole titles is a separate fix"}}


@pytest.mark.timeout(480)
def test_8_the_changed_screens_pass_the_rendered_check(client, gh, tmp_path, installed, monkeypatch):
    shop(client, gh, tmp_path, PLAN)
    with live(client, FORGE_BOARD_FETCH_WAIT="3600") as url:
        address = urlsplit(url)
        command = prepare(installed, ROOT / ".forge/design", [
            {"name": name, "path": f"/?{address.query}{where}", "waive": WAIVE.get(name, {})} for name, where in SCREENS])
        monkeypatch.setenv("BASE_URL", f"{address.scheme}://{address.netloc}")
        monkeypatch.setenv("CHROME_BIN", _browser())
        done = run(command)
        assert done.returncode == 0, done.stdout + done.stderr
