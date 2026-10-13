"""The board page below the first screen: one key line, every story and fix in one order, done
work folded away, all from the same derivation as `forge board --json`."""
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from html import escape

import pytest

import conftest
from conftest import REAL_UV
from test_board_counts import ONE_PART, board, clock, configure, github, read_story
from test_close import blocked, env, finding  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_story import READER
from test_board import DOC, seen
from test_board_dependency_timelines import _configured, _land_fixture
from test_story import claude_plan, hook, new_story, ready, worktree

STORY = "FORGE-BOARD-2"
ORDER = ["needs you", "blocked", "in progress", "planned", "no plan yet", "done"]


def _rows(page):
    """(group, title, state, times) for each row, in page order."""
    found = []
    for chunk in page.split('<div class="row" ')[1:]:
        group = re.search(r'data-group="([^"]+)"', chunk)[1]
        title = re.search(r'<span class="title">(.*?)</span>', chunk)[1]
        state = re.search(r'<span class="state">(.*?)</span>', chunk)[1]
        times = re.search(r'<p class="times">(.*?)</p>', chunk)[1]
        found.append((group, title, state, times))
    return found


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_8_below_the_fold(repo, gh, tmp_path, claude_payload, monkeypatch, history):
    _configured(repo, gh, tmp_path, history, ("SHOP", "PLAN", "IDEA", "WAIT"))
    now = datetime.now(timezone.utc).replace(microsecond=0)
    monkeypatch.setenv("FORGE_NOW", now.isoformat())

    # A fix merged ten days ago: older than the JSON's seven days, still on the page.
    monkeypatch.setenv("GIT_COMMITTER_DATE", (now - timedelta(days=10)).isoformat())
    old = repo.forge("fix", "start", "Greet returning shoppers", "--done", "Shoppers see a greeting",
                     "--slug", "greet-shoppers")
    assert old.returncode == 0, old.stderr
    tree = worktree(repo, "fix/greet-shoppers")
    (tree / "greeting.txt").write_text("Welcome back\n", "utf-8")
    repo.git("add", "-A", cwd=tree)
    repo.git("commit", "-qm", "Greet returning shoppers", cwd=tree)
    monkeypatch.delenv("GIT_COMMITTER_DATE")
    repo.git("merge", "-q", "--ff-only", "fix/greet-shoppers")
    _land_fixture(repo)

    # A fix nobody has touched for two days: blocked or slow.
    earlier = (now - timedelta(days=2)).isoformat()
    monkeypatch.setenv("FORGE_NOW", earlier)
    monkeypatch.setenv("GIT_COMMITTER_DATE", earlier)
    stale = repo.forge("fix", "start", "Tidy the help page", "--done", "The help page is tidy", "--slug", "tidy-help")
    assert stale.returncode == 0, stale.stderr
    monkeypatch.delenv("GIT_COMMITTER_DATE")
    monkeypatch.setenv("FORGE_NOW", now.isoformat())

    # A plan read and waiting for its approval: it needs a person.
    waiting = new_story(repo, "WAIT", "Wait for a decision")
    (waiting / "plans/WAIT.md").write_text(DOC.replace("# Shoppers can save a basket", "# Wait for a decision", 1)
                                           .replace("come back to it later", "pick it up on another day"), "utf-8")
    read = repo.forge("read", "WAIT")
    assert read.returncode == 0, read.stderr

    # Building (a part started), planning, no plan yet, and an open fix.
    shop = ready(repo, "SHOP", DOC)
    assert hook(repo, claude_plan(claude_payload, DOC, cwd=shop)).returncode == 0
    started = repo.forge("task", "start", "SHOP/SAVE")
    assert started.returncode == 0, started.stderr
    new_story(repo, "PLAN", "Plan the next improvement")
    fixed = repo.forge("fix", "start", "Readme greets new readers", "--done", "Readers see a greeting",
                       "--slug", "readme-greets")
    assert fixed.returncode == 0, fixed.stderr

    machine = repo.forge("board", "--json")
    assert machine.returncode == 0, machine.stderr
    data = json.loads(machine.stdout)
    out = tmp_path / "board.html"
    made = repo.forge("board", "--out", str(out))
    assert made.returncode == 0, made.stderr
    page = out.read_text("utf-8")
    rows = _rows(page)
    by_title = {title: (group, state, times) for group, title, state, times in rows}

    # Every story and fix, sorted needs you, blocked, in progress, planned, no plan yet, done.
    groups = [group for group, *_ in rows]
    assert groups == sorted(groups, key=ORDER.index), groups
    assert by_title["Shoppers can save a basket"][0] == "in progress"
    assert by_title["Readme greets new readers"][0] == "in progress"
    assert by_title["Plan the next improvement"][0] == "planned"
    assert by_title["A story with no title yet"][0] == "no plan yet"
    assert by_title["Greet returning shoppers"][0] == "done"

    # Every top-level item the JSON lists under Needs you or Blocked or slow sits in that group;
    # Needs you wins when an item is in both. Both lists stay null until their part lands.
    top = {row["id"]: row for row in data["items"]}
    needs = {entry["id"] for entry in data["team"]["needs_you"] or []}
    for entry in [*(data["team"]["needs_you"] or []), *(data["team"]["blocked"] or [])]:
        if entry["id"] in top:
            expected = "needs you" if entry["id"] in needs else "blocked"
            assert by_title[top[entry["id"]]["title"]][0] == expected, entry
    if data["team"]["needs_you"] is not None:
        assert "WAIT" in needs
    if data["team"]["blocked"] is not None:
        assert "tidy-help" in {entry["id"] for entry in data["team"]["blocked"]}

    # Done rows sit inside one closed fold, including the fix finished ten days ago, which the
    # trimmed JSON leaves out.
    folds = re.findall(r'<details class="done">(.*?)</details>\s*</section>', page, re.S)
    assert len(folds) == 1 and 'data-group="done"' in folds[0]
    assert "Greet returning shoppers" in folds[0]
    assert all(row[0] == "done" for row in _rows(folds[0]))
    assert "Greet returning shoppers" not in machine.stdout

    # Each row's state and time split are the JSON's, through the same plain wording.
    from_json = [row for parent in data["items"] for row in [parent, *parent["children"]]]
    for row in data["items"]:
        group, state, times = by_title[row["title"]]
        assert state == row["state"].capitalize(), (row["title"], state, row["state"])
        assert times == _times(row)
    # A part row shows its own JSON state and time split too.
    part = next(child for child in from_json if child["title"] == "Save a basket")
    shown = re.search(r'<span class="title">Save a basket</span><span class="kind">Part</span>'
                      r'<span class="state">(.*?)</span>.*?<p class="times">(.*?)</p>', page, re.S)
    assert shown[1] == part["state"].capitalize()
    assert shown[2] == _times(part)

    # One key line names the graph's shapes and the words part, fix and plan.
    key = re.sub(r"<[^>]+>", "", re.search(r'<p class="key"[^>]*>(.*?)</p>', page, re.S)[1])
    assert all(word in key for word in ("done", "running", "waiting", "can start", "not started",
                                        "part:", "fix:", "plan:")), key
    assert re.search(r"\.key \{[^}]*white-space: nowrap", page), "The key stays on one line"
    text = seen(out)
    assert "How the factory is doing:" in text
    _browser(out)


def _browser(page):
    """In real Chrome at 1440 and 390 wide: no sideways scroll, one column when narrow, the done
    fold opens and closes, and a row opens in place."""
    script = """
import sys
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        for width, columns in ((1440, 5), (390, 2)):
            page = browser.new_page(viewport={'width': width, 'height': 900})
            page.goto(sys.argv[1])
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), width
            row = page.locator('.row > details > summary').first
            shown = row.evaluate("s => getComputedStyle(s).gridTemplateColumns.split(' ').length")
            assert shown == columns, (width, shown)
            fold = page.locator('details.done')
            fold.locator('> summary').click()
            assert fold.evaluate('d => d.open'), 'The done fold opens'
            fold.locator('> summary').click()
            assert not fold.evaluate('d => d.open'), 'The done fold closes'
            row.click()
            assert page.locator('.row > details').first.evaluate('d => d.open'), 'A row opens'
            assert page.locator('.row > details .more').first.is_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), width
            page.close()
    finally:
        browser.close()
"""
    shown = subprocess.run([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                            "playwright==1.55.0", "python", "-c", script, page.resolve().as_uri()],
                           capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert shown.returncode == 0, shown.stdout + shown.stderr


def _times(row):
    seconds = [row[f"{kind}_seconds"] for kind in ("working", "waiting", "unknown")]
    return ("No time recorded yet" if seconds == [None] * 3 else
            "Working {} · waiting {} · unknown {}".format(*map(_plain, seconds)))


def _plain(seconds):
    """The page's wording for a time, as time_records.plain gives it (tests never import forge)."""
    if seconds is None:
        return "unknown"
    value = max(0, round(seconds))
    if value < 60:
        return f"{value} second" + ("s" if value != 1 else "")
    minutes = round(value / 60)
    if minutes < 60:
        return f"{minutes} minute" + ("s" if minutes != 1 else "")
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours} hour" + ("s" if hours != 1 else "") + (
            f" {minutes} minute" + ("s" if minutes != 1 else "") if minutes else "")
    days = round(value / 86400)
    return f"{days} day" + ("s" if days != 1 else "")


def _plain_text(html):
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def _list(section, name):
    """(rows shown, the "and N more" count, rows folded behind it) for one first-screen list."""
    block = re.search(rf'<div class="lanes" id="{name}">(.*?)<!-- end {name} -->', section, re.S)[1]
    shown, _, rest = block.partition('<details class="rest">')
    more = re.search(r"<summary>and (\d+) more</summary>", rest)
    titles = lambda html: re.findall(r'<span class="name"[^>]*>(.*?)</span>', html)  # noqa: E731
    return titles(shown), int(more[1]) if more else 0, titles(rest)


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "earlier-adoption"])
def test_7_first_screen(env, monkeypatch, previous):
    client(env, previous)
    conftest._install(env.repo.bin, "claude", READER.format(python=sys.executable))
    configure(env, "human")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    clock(monkeypatch, now)
    # Seven plans waiting for their approval: seven waits on a person.
    for n in range(7):
        read_story(env.repo, f"WAIT-{n + 1}", ONE_PART)
    # Two fixes nobody touched for two days: blocked or slow.
    earlier = (now - timedelta(days=2)).isoformat()
    monkeypatch.setenv("GIT_COMMITTER_DATE", earlier)
    clock(monkeypatch, now - timedelta(days=2))
    for n in range(2):
        started = env.repo.forge("fix", "start", f"Tidy help page {n + 1}", "--done", "It is tidy", "--slug", f"tidy-{n}")
        assert started.returncode == 0, started.stderr
    monkeypatch.delenv("GIT_COMMITTER_DATE")
    clock(monkeypatch, now)
    # Six fixes in progress; one has a blocked review round.
    for n in range(6):
        started = env.repo.forge("fix", "start", f"Speed up page {n + 1}", "--done", "It is fast", "--slug", f"speed-{n}")
        assert started.returncode == 0, started.stderr
    tree = worktree(env.repo, "fix/speed-0")
    env.commit(tree, "speed.txt", "fast\n", "Speed up the page")
    env.reviews(blocked(finding("P1", "The page still loads every row")))
    env.repo.forge("close", "speed-0", cwd=tree)
    github(env, [])
    clock(monkeypatch, now + timedelta(minutes=2))

    data = board(env.repo)
    team = data["team"]
    out = env.tmp / "first.html"
    made = env.repo.forge("board", "--out", str(out))
    assert made.returncode == 0, made.stderr
    page = out.read_text("utf-8")
    section = re.search(r'<section id="first-screen".*?</section>', page, re.S)[0]
    text = _plain_text(section)

    # The sentence and the labelled totals, equal to team.counts.
    assert escape(team["sentence"]) in section
    labels = {"finished_last_7_days": "Finished in the last 7 days"}
    for kind, counts in team["counts"].items():
        line = labels.get(kind, kind.capitalize()) + " — " + "; ".join(
            f"{name.capitalize()}: {count}" for name, count in counts.items())
        assert line in text, line

    # At most five rows each, the rest behind "and N more", which opens them in place.
    needs = {row["id"] for row in team["needs_you"] or []}
    stuck = {row["id"] for row in team["blocked"] or []}
    building = [row["title"] for row in data["items"] if row["id"] not in needs | stuck
                and row["state"] in ("building", "in progress", "ready to merge")]
    assert len(building) == (6 if team["blocked"] is not None else 8)
    for name, rows in (("in-progress", building),
                       ("needs-you", [row["title"] for row in team["needs_you"] or []]),
                       ("blocked", [row["title"] for row in team["blocked"] or []])):
        shown, more, rest = _list(section, name)
        assert len(shown) == min(5, len(rows)) and more == max(0, len(rows) - 5) == len(rest), name
        assert sorted(shown + rest) == sorted(escape(title) for title in rows), name
    if team["needs_you"] is not None:
        assert len(team["needs_you"]) == 7 and "and 2 more" in text
    if team["blocked"] is not None:
        assert len(team["blocked"]) == 2 and _list(section, "blocked")[1] == 0
    if team["needs_you"] is None:
        assert "Not worked out by this release" in text

    # Go-live in words, and a row's detail holds its round lines and who started it.
    assert "Not enough history to estimate go-live" in text
    row = next(r for r in data["items"] if r["id"] == "speed-0")
    assert row["rounds"], "The blocked close recorded a round"
    detail = re.search(r'<details class="lane">.*?' + re.escape(escape(row["title"])) + r".*?</details>", section, re.S)[0]
    for line in row["rounds"]:
        assert escape(line["line"]) in detail
    assert "Started by" in detail
    _first_screen_browser(out)


def _first_screen_browser(page):
    """In real Chrome: at 1440 by 900 the first screen ends above the fold; nothing scrolls
    sideways at 1440 or 390; "and N more" and a row's detail open in place and close again;
    Tab reaches every row with a visible focus ring."""
    script = """
import sys
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        for width, height in ((1440, 900), (390, 844)):
            for scheme in ('light', 'dark'):
                page = browser.new_page(viewport={'width': width, 'height': height}, color_scheme=scheme)
                page.goto(sys.argv[1])
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), width
                if width == 1440:
                    bottom = page.evaluate("document.getElementById('first-screen').getBoundingClientRect().bottom")
                    assert bottom <= height, ('The first screen fits', bottom)
                rest = page.locator('#first-screen details.rest').first
                rest.locator('> summary').click()
                assert rest.evaluate('d => d.open'), 'and N more opens'
                rest.locator('> summary').click()
                assert not rest.evaluate('d => d.open'), 'and N more closes'
                lane = page.locator('#first-screen details.lane').first
                lane.locator('> summary').click()
                assert lane.evaluate('d => d.open') and lane.locator('.more').is_visible(), 'A row opens'
                lane.locator('> summary').click()
                assert not lane.evaluate('d => d.open'), 'A row closes'
                rows = page.locator('#first-screen details.lane:visible > summary').count()
                page.mouse.click(1, 1)
                reached = 0
                for _ in range(rows + 10):
                    page.keyboard.press('Tab')
                    focus = page.evaluate('''() => {
                        const el = document.activeElement;
                        if (!el.matches('#first-screen details.lane > summary')) return null;
                        const style = getComputedStyle(el);
                        return style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) >= 2;
                    }''')
                    if focus is not None:
                        assert focus, 'A focused row shows a ring'
                        reached += 1
                assert reached == rows, (reached, rows)
                page.close()
    finally:
        browser.close()
"""
    shown = subprocess.run([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                            "playwright==1.55.0", "python", "-c", script, page.resolve().as_uri()],
                           capture_output=True, text=True, encoding="utf-8", timeout=180)
    assert shown.returncode == 0, shown.stdout + shown.stderr
