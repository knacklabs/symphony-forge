"""The board page has a pinned section bar to Overview, Roadmap, Stories and Fixes; each section
folds, long ones start folded, and each story shows its key small beside its title. Board output
and the page in a real browser are all the test reads."""
import json
import re
import subprocess

from conftest import REAL_UV
from test_board_dependency_timelines import _configured
from test_story import new_story

STORY = "FORGE-BOARD-2"
ORDER = ["needs you", "blocked", "in progress", "planned", "no plan yet", "done"]
KEYS = tuple(f"SHELF-{n}" for n in range(1, 26))


def pinned_bar_and_folding_sections(repo, gh, tmp_path, history):
    """Run from criterion 12's one test in tests/test_board_how_it_went.py."""
    # 25 roadmap stories with no title yet, so only their keys tell them apart; one has a plan
    # draft, and one fix is open.
    _configured(repo, gh, tmp_path, history, KEYS)
    new_story(repo, "SHELF-3", "Shoppers can keep a shelf")
    fixed = repo.forge("fix", "start", "Readme greets new readers", "--done", "Readers see a greeting",
                       "--slug", "readme-greets")
    assert fixed.returncode == 0, fixed.stderr
    data = json.loads(repo.forge("board", "--json").stdout)
    out = tmp_path / "sections.html"
    made = repo.forge("board", "--out", str(out))
    assert made.returncode == 0, made.stderr
    page = out.read_text("utf-8")

    # The bar's four links each lead to a section that folds.
    bar = re.search(r'<nav class="bar"[^>]*>(.*?)</nav>', page, re.S)[1]
    links = re.findall(r'<a href="#([a-z-]+)">', bar)
    assert links == ["overview", "roadmap", "stories", "fixes"]
    for name in links:
        assert re.search(rf'<section id="{name}"[^>]*><details class="fold"', page), name
    stories = re.search(r'<section id="stories".*?</section>', page, re.S)[0]
    fixes = re.search(r'<section id="fixes".*?</section>', page, re.S)[0]
    # More than 20 stories: Stories starts folded; the short Fixes section starts open.
    assert '<details class="fold">' in stories and '<details class="fold" open>' in fixes
    # Overview and Roadmap always start open.
    for name in ("overview", "roadmap"):
        assert re.search(rf'<section id="{name}"[^>]*><details class="fold" open>', page), name
    # Stories sorted by state, with no group headings, each title followed by its key.
    assert "<h3" not in stories
    groups = re.findall(r'<div class="row" data-group="([^"]+)">', stories)
    assert len(groups) == 25 and groups == sorted(groups, key=ORDER.index)
    shown = re.findall(r'<span class="title">(.*?)</span> <span class="key">(.*?)</span>', stories)
    expected = sorted((row["title"], row["id"]) for row in data["items"] if row["kind"] == "story")
    assert sorted(shown) == expected and {key for _, key in shown} == set(KEYS)
    assert '<span class="key">' not in fixes
    _browser(out, {"stories": expected,
                   "fixes": sorted(row["title"] for row in data["items"] if row["kind"] == "fix")})


def _browser(page, expected):
    """In real Chrome at 1440 by 900 and 390 by 844, light and dark: the bar stays pinned while
    scrolling, each link lands on its section, each section folds shut and open again, with every
    section folded the page is under three screens tall, nothing scrolls sideways, and the visible
    story titles with their keys and the fix titles are the board JSON's."""
    script = """
import json
import sys
from playwright.sync_api import sync_playwright
expected = json.loads(sys.argv[2])
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        for width, height in ((1440, 900), (390, 844)):
            for scheme in ('light', 'dark'):
                page = browser.new_page(viewport={'width': width, 'height': height}, color_scheme=scheme)
                page.goto(sys.argv[1])
                bar = page.locator('nav.bar')
                assert bar.evaluate('n => getComputedStyle(n).position') == 'sticky'
                page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                assert abs(bar.bounding_box()['y']) < 1 and bar.is_visible(), 'The bar stays pinned'
                tall = bar.bounding_box()['height']
                for name in ('overview', 'roadmap', 'stories', 'fixes'):
                    bar.locator(f'a[href="#{name}"]').click()
                    page.wait_for_timeout(100)
                    top = page.locator(f'#{name} > details.fold > summary').bounding_box()['y']
                    assert tall - 1 <= top <= tall + 80 or page.evaluate(
                        'window.scrollY + window.innerHeight >= document.body.scrollHeight - 1'), (width, name, top, tall)
                for name in ('overview', 'roadmap', 'stories', 'fixes'):
                    fold = page.locator(f'#{name} > details.fold')
                    was = fold.evaluate('d => d.open')
                    fold.locator('> summary').click()
                    assert fold.evaluate('d => d.open') != was, ('A section folds', name)
                    fold.locator('> summary').click()
                    assert fold.evaluate('d => d.open') == was, ('A section unfolds', name)
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), width
                # What the page shows is the board JSON's: each story's title and key, each fix.
                page.evaluate("document.querySelectorAll('details.fold, details.done').forEach(d => d.open = true)")
                stories = page.locator('#stories .row > details > summary .named')
                seen = sorted([' '.join(stories.nth(n).locator('.title').inner_text().split()),
                               stories.nth(n).locator('.key').inner_text().strip()]
                              for n in range(stories.count()) if stories.nth(n).is_visible())
                assert seen == expected['stories'], seen
                fixes = page.locator('#fixes .row > details > summary .title')
                assert sorted(t.strip() for t in fixes.all_inner_texts()) == expected['fixes']
                key = stories.first.locator('.key')
                small = key.evaluate('k => parseFloat(getComputedStyle(k).fontSize)')
                assert small < stories.first.locator('.title').evaluate('t => parseFloat(getComputedStyle(t).fontSize)')
                page.evaluate("document.querySelectorAll('details.fold').forEach(d => d.open = false)")
                folded = page.evaluate('document.documentElement.scrollHeight')
                assert folded < 3 * height, ('Folded, the page is under three screens', folded)
                page.close()
    finally:
        browser.close()
"""
    shown = subprocess.run([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                            "playwright==1.55.0", "python", "-c", script, page.resolve().as_uri(),
                            json.dumps(expected)], capture_output=True, text=True, encoding="utf-8", timeout=180)
    assert shown.returncode == 0, shown.stdout + shown.stderr
