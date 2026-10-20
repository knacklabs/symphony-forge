"""`forge board`'s Releases and Insights pages in real Chrome: Releases shows the next release, past
releases from the repo's tags and the problems kept for later by file; Insights shows merged work per
week stacked by person in alphabetical order, and each person's open items, stories owned and
unranked share of the team. Their own words carry no command text, say unknown where Forge has no
record, work from the keyboard, and pass an axe check in light and dark. Only GitHub is a stub."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from conftest import REAL_UV
from test_board import DOC
from test_board_counts import github
from test_board_server import client, clone, get, live, pushed  # noqa: F401

STORY = "FORGE-BOARD-4"

KEPT = [{"outcome": "follow-up", "file": "src/basket.py", "line": 3, "title": "Basket total rounds down",
         "gain": 2, "work": 1, "harm": 1},
        {"outcome": "lived with", "file": "src/basket.py", "line": 9, "title": "Basket name is not trimmed",
         "gain": 1, "work": 1, "harm": 1},
        {"outcome": "follow-up", "file": "src/page.py", "line": 1, "title": "`forge next` names the wrong page --json",
         "gain": 1, "work": 1, "harm": 1}]

PRELUDE = r"""
import json, re, sys
from playwright.sync_api import expect, sync_playwright
url, expected = sys.argv[1], json.loads(sys.argv[2])
COMMANDS = re.compile(r"\bforge\s+[a-z]|`|(^|\s)--[a-z]", re.I)

def opened(browser, scheme, page_name):
    page = browser.new_page(viewport={'width': 1440, 'height': 900}, color_scheme=scheme)
    page.goto(url + '#' + page_name)
    expect(page.get_by_role('status')).to_have_text('Live', timeout=60000)
    expect(page.locator('main')).to_have_attribute('aria-busy', 'false')
    return page
"""

RELEASES_AND_INSIGHTS = PRELUDE + r"""
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        page = opened(browser, 'light', 'releases')
        upcoming = page.get_by_role('region', name='Next release')
        past = page.get_by_role('region', name='Past releases')
        kept = page.get_by_role('region', name='Known issues by file')
        if expected['releases'] is None:  # no release facts: unknown, never a guess
            expect(upcoming).to_contain_text('unknown')
            expect(past).to_contain_text('unknown')
        else:
            for title in expected['releases']['next']:
                expect(upcoming).to_contain_text(title)
            if expected['releases']['tags']:
                expect(past.get_by_role('row')).to_have_count(1 + len(expected['releases']['tags']))
                for tag in expected['releases']['tags']:
                    expect(past).to_contain_text(tag)
            else:
                expect(past).to_contain_text('No releases tagged yet')
        rows = kept.get_by_role('listitem')
        expect(rows).to_have_count(2)  # by file, the file with most kept problems first
        assert [' '.join(rows.nth(n).inner_text().split()) for n in range(2)] == ['src/basket.py 2', 'src/page.py 1']

        if expected['people'] is not None:
            page.get_by_role('link', name='Insights').click()
            weekly = page.get_by_role('region', name='Merged per week')
            legend = weekly.get_by_role('listitem')
            # Each person's merges through Forge, stacked in alphabetical order, and the team's around Forge.
            names = [p['name'] for p in expected['people']] + ['around Forge']
            expect(legend).to_have_count(len(names))
            assert [legend.nth(n).inner_text().strip() for n in range(legend.count())] == names
            for week, total in expected['weeks']:
                expect(weekly.get_by_role('img', name=re.compile(rf'^Week of {week}: {total}\b'))).to_have_count(1)
            people = page.get_by_role('region', name='People')
            cells = people.locator('tbody tr')
            expect(cells).to_have_count(len(expected['people']))
            shown = [[' '.join(c.split()) for c in cells.nth(n).locator('th, td').all_inner_texts()]
                     for n in range(cells.count())]
            assert shown == [[f"{p['name']} @{p['login']}", str(p['open']), str(p['owned']), p['share']]
                             for p in expected['people']], shown
            assert not re.search(r'\b(rank|ranked|top|best|worst)\b', page.locator('main').inner_text(), re.I)
        page.close()
    finally:
        browser.close()
"""

WORDS_KEYS_AND_CONTRAST = PRELUDE + r"""
from axe_playwright_python.sync_playwright import Axe
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        for scheme in ('light', 'dark'):
            for name in ('releases', 'insights'):
                page = opened(browser, scheme, name)
                expect(page.locator('main section').first).to_be_visible()
                text = page.locator('main').inner_text()
                assert not COMMANDS.search(text), (name, text)
                assert 'unknown' in text.lower() or name == 'insights', (name, text)
                found = Axe().run(page).response['violations']
                assert not found, (scheme, name, [(v['id'], v['nodes'][0]['target']) for v in found])
                page.close()
        # The keyboard reaches every control on both pages with a visible focus, and Enter on a page tab opens it.
        page = opened(browser, 'light', 'releases')
        reached = []
        for _ in range(12):
            page.keyboard.press('Tab')
            label = page.evaluate('document.activeElement.textContent.trim()')
            assert page.evaluate("getComputedStyle(document.activeElement).outlineStyle") != 'none', label
            reached.append(label)
            if label == 'Insights':
                break
        assert reached[-1] == 'Insights', reached
        # Past the header, each file's kept problems open with Enter and close with Escape, in plain words.
        while not page.evaluate("document.activeElement.textContent.trim().startsWith('src/page.py')"):
            page.keyboard.press('Tab')
            assert page.evaluate("getComputedStyle(document.activeElement).outlineStyle") != 'none'
            assert len(reached) < 30, reached
            reached.append(page.evaluate('document.activeElement.textContent.trim()'))
        kept = page.get_by_role('region', name='Known issues by file')
        page.keyboard.press('Enter')
        expect(kept.get_by_text("Forge's next step names the wrong page")).to_be_visible()
        assert not COMMANDS.search(page.locator('main').inner_text())
        page.keyboard.press('Escape')
        expect(kept.get_by_text("Forge's next step names the wrong page")).to_be_hidden()
        assert page.evaluate("document.activeElement.tagName") == 'SUMMARY'
        page.get_by_role('link', name='Insights').focus()
        page.keyboard.press('Enter')
        expect(page.get_by_role('region', name='Merged per week')).to_be_visible()
        # A page whose facts cannot be read says so in plain words and keeps the header working.
        page.route('**/board.json?*page=releases*', lambda route: route.fulfill(
            status=500, content_type='application/json',
            body=json.dumps({'error': 'The board could not read the work. The terminal that runs it shows why.'})))
        page.get_by_role('link', name='Releases').click()
        problem = page.locator('main .problem')
        expect(problem).to_contain_text('could not read the work')
        assert not COMMANDS.search(problem.inner_text())
        page.close()
    finally:
        browser.close()
"""


def browse(script, url, expected):
    shown = subprocess.run([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with", "playwright==1.55.0",
                            "--with", "axe-playwright-python==0.1.8", "python", "-c", script, url, json.dumps(expected)],
                           capture_output=True, text=True, encoding="utf-8", timeout=300)
    assert shown.returncode == 0, shown.stdout + shown.stderr


def landed(client, tmp_path, monkeypatch, tags=(), merged_days_ago=9):
    """A story ana owns, and a fix that landed with three kept problems `merged_days_ago` days ago,
    after the given tags; GitHub saw ana merge that fix and ben merge a change around Forge."""
    teammate = clone(client, tmp_path)
    for tag in tags:
        teammate.git("tag", "-a", tag, "-m", f"Release {tag}")
        teammate.git("push", "-q", "origin", tag)
    at = datetime.now(timezone.utc) - timedelta(days=merged_days_ago)
    with monkeypatch.context() as dated:
        dated.setenv("GIT_AUTHOR_DATE", at.isoformat())
        dated.setenv("GIT_COMMITTER_DATE", at.isoformat())
        pushed(teammate, "Plan a basket and fix the readers", {
            "plans/SHOP.md": DOC.replace("## What changes", "Owner: ana\n\n## What changes"),
            "plans/roadmap.json": json.dumps({"items": [{"key": "SHOP"}]}),
            # The kept problems' files are on the default branch; the board leaves out deleted files.
            "src/basket.py": "total = 0\n", "src/page.py": "page = 1\n",
            ".factory/fixes/old.json": json.dumps({"kind": "fix", "branch": "fix/old", "why": "Readers see old",
                                                   "done_when": "Readers see it", "status": "merged", "known": KEPT})})
    client.git("fetch", "-q", "--tags", "origin")
    client.git("merge", "-q", "--ff-only", "origin/main")

    def pr(number, branch, who):
        return {"number": number, "headRefName": branch, "state": "MERGED", "title": "A change", "body": "",
                "isDraft": False, "mergedAt": at.isoformat(), "mergedBy": {"login": who["login"]}, "author": who,
                "url": f"https://github.com/acme/shop/pull/{number}"}

    github(SimpleNamespace(repo=client, gh=client.gh), [pr(1, "fix/old", {"login": "ana", "name": "Ana Silva"}),
                                                       pr(2, "hotfix", {"login": "ben", "name": "ben Ode"})])
    return at


@pytest.fixture
def team(client, gh, tmp_path, monkeypatch):
    client.gh = gh
    return client


def test_14_releases_show_kept_problems_by_file_and_insights_show_unranked_shares(team, tmp_path, monkeypatch):
    at = landed(team, tmp_path, monkeypatch)
    with live(team) as url:
        view = json.loads(get(url, "/board.json?page=releases")[2])
        weeks = view["team"]["trends"]["weeks"]
        week = max(w for w in weeks if w <= at.date().isoformat())
        day = datetime.fromisoformat(week)
        browse(RELEASES_AND_INSIGHTS, url, {
            # Release facts come from the releases part of the previous story; until then they are unknown.
            "releases": None if "releases" not in view else {"next": ["Readers see old"], "tags": []},
            "weeks": [[f"{day.day} {day:%b}", 2]],
            # Alphabetical ignoring case; three open parts and one story are ana's; each merged one of two.
            "people": [{"name": "Ana Silva", "login": "ana", "open": 3, "owned": 1, "share": "50%"},
                       {"name": "ben Ode", "login": "ben", "open": 0, "owned": 0, "share": "50%"}]})


def test_15_a_week_github_could_not_count_leaves_its_counts_and_the_shares_unknown(team, tmp_path, monkeypatch):
    at = landed(team, tmp_path, monkeypatch)
    capped = at - timedelta(weeks=1)  # a week of 1,000 merges, more than one search returns
    many = [{"number": 100 + n, "headRefName": f"bulk-{n}", "state": "MERGED", "title": "A change", "body": "",
             "isDraft": False, "mergedAt": capped.isoformat(), "mergedBy": {"login": "cara"},
             "author": {"login": "cara", "name": "Cara Lee"}, "url": f"https://github.com/acme/shop/pull/{100 + n}"}
            for n in range(1000)]
    shown = json.loads(team.gh.responses.read_text("utf-8"))[-1]["stdout"]
    github(SimpleNamespace(repo=team, gh=team.gh), json.loads(shown) + many)
    with live(team) as url:
        view = json.loads(get(url, "/board.json?page=releases")[2])
        week = max(w for w in view["team"]["trends"]["weeks"] if w <= capped.date().isoformat())
        day = datetime.fromisoformat(week)
        browse(RELEASES_AND_INSIGHTS, url, {
            "releases": None if "releases" not in view else {"next": ["Readers see old"], "tags": []},
            "weeks": [[f"{day.day} {day:%b}", "unknown"]],
            "people": [{"name": "Ana Silva", "login": "ana", "open": 3, "owned": 1, "share": "unknown"},
                       {"name": "ben Ode", "login": "ben", "open": 0, "owned": 0, "share": "unknown"}]})


def test_16_the_next_release_carries_unreleased_work_since_the_last_tag(team, tmp_path, monkeypatch):
    landed(team, tmp_path, monkeypatch, tags=("v1.0.0",), merged_days_ago=56)
    with live(team) as url:
        view = json.loads(get(url, "/board.json?page=releases")[2])
        if "releases" not in view:
            pytest.skip("The board has no release facts until the previous story's releases part lands")
        browse(RELEASES_AND_INSIGHTS, url, {
            "releases": {"next": ["Readers see old"], "tags": ["v1.0.0"]}, "people": None})


def test_17_releases_and_insights_words_keyboard_and_contrast(team, tmp_path, monkeypatch):
    landed(team, tmp_path, monkeypatch)
    with live(team) as url:
        browse(WORDS_KEYS_AND_CONTRAST, url, {})
