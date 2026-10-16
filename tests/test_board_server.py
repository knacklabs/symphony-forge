"""`forge board` serves a live page on this computer only: a server on 127.0.0.1 that answers only
with its run's token, serves a fresh snapshot after any change and the same one when nothing
changed, rebuilds only the rows that changed, tells the page through its events stream, and shows
a teammate's pushed work after its next fetch. The real command and HTTP are all the tests use;
the page itself is driven in real Chrome."""
from __future__ import annotations

import http.client
import json
import os
import queue
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from urllib.parse import urlsplit

import pytest

from conftest import REAL_UV, Repo
from test_board import DOC
from test_board_dependency_timelines import _client
from test_story import worktree


@pytest.fixture(params=["new", "adopted-v1.2.2"])
def client(repo, gh, tmp_path, request):
    _client(repo, gh, tmp_path, request.param)
    gh.respond("pr", "list", stdout="[]")
    gh.respond("api", "graphql", stdout=json.dumps({"data": {"repository": {"pullRequests": {"nodes": []}}}}))
    return repo


@contextmanager
def live(repo, **env):
    """Run `forge board` until the test ends, and give its page address."""
    process = subprocess.Popen([sys.executable, str(repo.bin / "forge"), "board"], cwd=repo.path,
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", env={**os.environ, **env})
    lines: queue.Queue[str | None] = queue.Queue()
    threading.Thread(target=lambda: [*map(lines.put, process.stdout), lines.put(None)], daemon=True).start()
    try:
        while (line := lines.get(timeout=120)) is not None:
            if found := re.search(r"http://127\.0\.0\.1:\d+/\?token=[\w-]+", line):
                break
        assert line is not None, process.stderr.read()
        yield found[0]
    finally:
        process.terminate()
        process.wait(timeout=30)
        process.stdout.close()
        process.stderr.close()



def get(url, path="/", token=True):
    """Status, headers and body of one request; token=False leaves it out, a string replaces it."""
    parts = urlsplit(url)
    secret = parts.query.removeprefix("token=")
    query = {True: f"token={secret}", False: ""}.get(token, f"token={token}")
    joined = "&" if "?" in path else "?"
    try:
        with urllib.request.urlopen(f"{parts.scheme}://{parts.netloc}{path}{joined}{query}", timeout=120) as answer:
            return answer.status, answer.headers, answer.read()
    except urllib.error.HTTPError as refused:
        return refused.code, refused.headers, refused.read()


def snapshot(url):
    status, _, body = get(url, "/board.json")
    assert status == 200, body
    return json.loads(body)


def fix(repo, slug):
    started = repo.forge("fix", "start", f"Readers see {slug}", "--done", "The board agrees", "--slug", slug, "--kind", "backend")
    assert started.returncode == 0, started.stderr
    return worktree(repo, f"fix/{slug}")


def commit(tree, name):
    (tree / name).write_text("changed\n", encoding="utf-8")
    subprocess.run(["git", "add", name], cwd=tree, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", f"Change {name}"], cwd=tree, check=True, capture_output=True)


def clone(repo, tmp_path):
    teammate = Repo(tmp_path / "teammate", repo.bin)
    repo.git("clone", "-q", repo.git("remote", "get-url", "origin"), str(teammate.path))
    return teammate


def pushed(teammate, message, files):
    """A teammate's change, landed on the default branch the way a merged pull request lands."""
    for rel, text in files.items():
        teammate.write(rel, text)
    teammate.git("add", "-A")
    teammate.git("commit", "-qm", message)
    teammate.git("push", "-q", "origin", "HEAD:main")


def test_the_board_answers_only_on_this_computer_and_only_with_its_token(client, tmp_path):
    pushed(clone(client, tmp_path), "Plan a basket", {"plans/SHOP.md": DOC})  # a plan the page can open
    client.git("fetch", "-q", "origin")
    with live(client) as url:
        address = urlsplit(url)
        assert address.hostname == "127.0.0.1"
        status, headers, page = get(url)
        assert status == 200 and b"app.js?token=" in page
        assert "default-src 'none'" in headers["Content-Security-Policy"]
        assert headers["Referrer-Policy"] == "no-referrer"
        status, _, plan = get(url, "/plan/SHOP")
        assert status == 200 and plan.decode("utf-8") == DOC
        for path in ("/", "/board.json", "/board.json?page=releases", "/app.js", "/tokens.css", "/events",
                     "/plan/SHOP"):
            for token in (False, "not-this-run"):
                status, _, body = get(url, path, token)
                assert status == 403 and b"forge" not in body.lower(), (path, token, body)
        # Another address of this computer is refused: the server listens on loopback only.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            try:
                probe.connect(("192.0.2.1", 9))  # no packet is sent; this only picks a route
                outside = probe.getsockname()[0]
            except OSError:
                outside = None
        if outside and not outside.startswith("127."):
            with pytest.raises(OSError):
                socket.create_connection((outside, address.port), timeout=5).close()


def test_the_board_rebuilds_only_what_changed(client):
    alpha, _ = fix(client, "alpha"), fix(client, "beta")
    with live(client) as url:
        first = snapshot(url)
        assert {"alpha", "beta"} <= set(first["snapshot"]["rows_rebuilt"])
        # Nothing changed: the same snapshot, with no rebuild.
        again = snapshot(url)
        assert again == first
        # One item changed: only its row is derived again.
        commit(alpha, "alpha.txt")
        changed = snapshot(url)
        assert changed["snapshot"]["version"] == first["snapshot"]["version"] + 1
        assert changed["snapshot"]["rows_rebuilt"] == ["alpha"]
        # A change between two requests appears in the second.
        fix(client, "gamma")
        assert "gamma" in {row["id"] for row in snapshot(url)["items"]}
        # The untrimmed pages and an item's history come from the same server.
        status, _, item = get(url, "/board.json?page=item&id=gamma")
        assert status == 200 and json.loads(item)["item"]["id"] == "gamma"
        status, _, missing = get(url, "/board.json?page=item&id=nothing-here")
        assert status == 404 and json.loads(missing)["error"] == "No item by that name is on the board."


def test_the_events_stream_says_changed_after_a_commit(client):
    alpha = fix(client, "alpha")
    with live(client) as url:
        address = urlsplit(url)
        stream = http.client.HTTPConnection(address.hostname, address.port, timeout=60)
        stream.request("GET", f"/events?{address.query}")
        answer = stream.getresponse()
        assert answer.status == 200 and answer.headers["Content-Type"] == "text/event-stream"
        assert answer.readline() == b"retry: 10000\n"
        commit(alpha, "alpha.txt")
        lines = [answer.readline() for _ in range(3)]
        stream.close()
        assert lines[0] == b"\n" and lines[1] == b"event: changed\n" and lines[2].startswith(b"data: "), lines


def test_a_teammates_pushed_assignment_shows_after_the_next_fetch(client, tmp_path):
    """The teammate gives the story to a developer with the plan's Owner line, as `forge assign`
    writes it. After the server's own fetch the story and its parts show the owner, and an
    unrelated change later keeps them: the story's rows come from the cache with their owner."""
    teammate = clone(client, tmp_path)
    pushed(teammate, "Plan a basket", {"plans/SHOP.md": DOC, ".factory/stories/SHOP/story.json": json.dumps(
        {"doc": "plans/SHOP.md", "title": "Shoppers can save a basket", "status": "approved"})})
    client.git("fetch", "-q", "origin")

    def story(url):
        return next(row for row in snapshot(url)["items"] if row["id"] == "SHOP")

    with live(client, FORGE_BOARD_FETCH_WAIT="1") as url:
        assert story(url)["owner"] is None and not story(url)["children"]
        pushed(teammate, "Give the basket to page-dev", {"plans/SHOP.md": DOC.replace(
            "## Tasks\n", "## Tasks\n\nOwner: page-dev\n", 1)})
        deadline = time.monotonic() + 60
        while (shown := story(url))["owner"] != "page-dev" and time.monotonic() < deadline:
            time.sleep(0.5)  # waiting for the server's own fetch, which the test cannot trigger
        assert shown["owner"] == "page-dev", shown
        assert {part["owner"] for part in shown["children"]} == {"page-dev"}, shown["children"]
        fix(client, "elsewhere")
        after = snapshot(url)
        assert "SHOP" not in after["snapshot"]["rows_rebuilt"] and "elsewhere" in after["snapshot"]["rows_rebuilt"]
        kept = next(row for row in after["items"] if row["id"] == "SHOP")
        assert kept["owner"] == "page-dev" and kept["children"] == shown["children"], kept


def test_the_page_shell_crosses_the_board_interfaces(client):
    """In real Chrome: the page shows the snapshot, navigates, opens and closes the drawer with the
    keyboard, opens an item's page, and its assign stub answers {ok, message}; nothing breaks the
    page's content security policy."""
    fix(client, "alpha")
    script = r"""
import json, sys
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
    try:
        for scheme in ('light', 'dark'):
            page = browser.new_page(viewport={'width': 1440, 'height': 900}, color_scheme=scheme)
            problems = []
            page.on('console', lambda m: problems.append(m.text) if m.type == 'error' else None)
            page.on('response', lambda r: problems.append(r.url) if r.status >= 400 else None)
            page.goto(sys.argv[1])
            page.wait_for_selector('#now-state[data-kind=""]', state='attached')
            seen = page.evaluate("new Promise(done => Board.onSnapshot(s => done(s.items.map(i => i.id))))")
            assert 'alpha' in seen, seen
            assert page.locator('#now-state').inner_text().strip(), 'The Now page says something'
            for name in ('releases', 'insights', 'now'):
                page.locator(f'.bar nav a[data-page="{name}"]').focus()
                page.keyboard.press('Enter')
                assert page.locator(f'#page-{name}').is_visible(), name
                assert page.locator(f'.bar nav a[data-page="{name}"]').get_attribute('aria-current') == 'page'
            page.evaluate("Board.select('alpha')")
            drawer = page.locator('#drawer')
            assert drawer.is_visible() and 'alpha' in drawer.inner_text().lower()
            assert page.evaluate("document.activeElement.id") == 'drawer-close'
            page.keyboard.press('Escape')
            assert not drawer.is_visible()
            page.evaluate("Board.openItem('alpha')")
            assert page.locator('#page-item').is_visible() and 'alpha' in page.locator('#item-title').inner_text().lower()
            answer = page.evaluate("Board.api.assign('SHOP', 'page-dev')")
            assert set(answer) == {'ok', 'message'} and answer['ok'] is False and answer['message'], answer
            me = page.locator('.views button[data-view="me"]')
            me.focus()
            page.keyboard.press('Enter')
            assert me.get_attribute('aria-pressed') == 'true' and page.evaluate('Board.view') == 'me'
            assert page.evaluate("getComputedStyle(document.body).backgroundColor") == (
                'rgb(244, 245, 242)' if scheme == 'light' else 'rgb(20, 22, 24)')
            assert page.evaluate("document.documentElement.scrollHeight <= window.innerHeight")
            assert not problems, problems
            page.close()
    finally:
        browser.close()
"""
    with live(client) as url:
        shown = subprocess.run([REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with",
                                "playwright==1.55.0", "python", "-c", script, url],
                               capture_output=True, text=True, encoding="utf-8", timeout=180)
    assert shown.returncode == 0, shown.stdout + shown.stderr
