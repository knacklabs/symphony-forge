"""`forge board` serves a live page on this computer only: a server on 127.0.0.1 that answers only
with its run's token, serves a fresh snapshot after any change and the same one when nothing
changed, rebuilds only the rows that changed, tells the page through its events stream, and shows
a teammate's pushed work after its next fetch. The real command and HTTP are all the tests use."""
from __future__ import annotations

import http.client
import json
import os
import queue
import re
import socket
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from urllib.parse import urlsplit

import pytest

from conftest import Repo
from test_board import DOC
from test_board_dependency_timelines import _client
from test_story import worktree

STORY = "FORGE-BOARD-4"


@pytest.fixture(params=["new", "adopted-v1.2.2"])
def client(repo, gh, tmp_path, request):
    _client(repo, gh, tmp_path, request.param)
    gh.respond("pr", "list", stdout="[]")
    gh.respond("api", "graphql", stdout=json.dumps({"data": {"repository": {"pullRequests": {"nodes": []}}}}))
    return repo


@contextmanager
def live(repo, **env):
    """Run `forge board` until the test ends, and give its page address. A request waits for its
    rebuild unless the test sets a shorter wait, so every answer is fresh on a slow test machine."""
    process = subprocess.Popen([sys.executable, str(repo.bin / "forge"), "board"], cwd=repo.path,
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8",
                               env={**os.environ, "FORGE_BOARD_REBUILD_WAIT": "120", **env})
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


def test_1_the_board_answers_only_on_this_computer_and_only_with_its_token(client, tmp_path):
    pushed(clone(client, tmp_path), "Plan a basket", {"plans/SHOP.md": DOC})  # a plan the page can open
    client.git("fetch", "-q", "origin")
    with live(client) as url:
        address = urlsplit(url)
        assert address.hostname == "127.0.0.1"
        status, headers, page = get(url)
        assert status == 200 and f"app.js?{address.query}".encode() in page  # the shell loads its script with the token
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


def test_2_the_board_rebuilds_only_what_changed(client, tmp_path):
    teammate = clone(client, tmp_path)
    alpha, _ = fix(client, "alpha"), fix(client, "beta")
    with live(client) as url:
        first = snapshot(url)
        assert {"alpha", "beta"} <= set(first["snapshot"]["rows_rebuilt"])
        # Nothing changed: the same snapshot, with no rebuild.
        again = snapshot(url)
        assert again == first
        # A test run's per-test results are not board input: writing them rebuilds nothing.
        (client.path / ".git/forge/test-results-alpha.txt").write_text("passed tests/test_a.py::test_a\n",
                                                                       encoding="utf-8")
        assert snapshot(url) == first
        # One item changed: only its row is derived again.
        commit(alpha, "alpha.txt")
        changed = snapshot(url)
        assert changed["snapshot"]["version"] == first["snapshot"]["version"] + 1
        assert changed["snapshot"]["rows_rebuilt"] == ["alpha"]
        # An unrelated merge on the default branch is new, but no item's own inputs changed.
        pushed(teammate, "An unrelated change lands", {"notes.txt": "unrelated\n"})
        client.git("fetch", "-q", "origin")
        merged = snapshot(url)
        assert merged["snapshot"]["version"] == changed["snapshot"]["version"] + 1
        assert merged["snapshot"]["rows_rebuilt"] == [], merged["snapshot"]
        # A change between two requests appears in the second.
        fix(client, "gamma")
        assert "gamma" in {row["id"] for row in snapshot(url)["items"]}
        # The untrimmed pages and an item's history come from the same server.
        status, _, item = get(url, "/board.json?page=item&id=gamma")
        assert status == 200 and json.loads(item)["item"]["id"] == "gamma"
        status, _, missing = get(url, "/board.json?page=item&id=nothing-here")
        assert status == 404 and json.loads(missing)["error"] == "No item by that name is on the board."


def test_3_the_events_stream_says_changed_after_a_commit(client):
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


def test_4_a_teammates_pushed_assignment_shows_after_the_next_fetch(client, tmp_path):
    """The teammate gives the story to a developer with the plan's Owner line, as `forge assign`
    writes it. After the server's own fetch the story and its parts show the owner, and an
    unrelated change later keeps them: the story's rows come from the cache with their owner."""
    teammate = clone(client, tmp_path)
    pushed(teammate, "Plan a basket", {"plans/SHOP.md": DOC, ".factory/stories/SHOP/story.json": json.dumps(
        {"doc": "plans/SHOP.md", "title": "Shoppers can save a basket", "status": "approved"})})
    client.git("fetch", "-q", "origin")
    elsewhere = fix(client, "elsewhere")

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
        commit(elsewhere, "elsewhere.txt")
        after = snapshot(url)
        assert "SHOP" not in after["snapshot"]["rows_rebuilt"]
        kept = next(row for row in after["items"] if row["id"] == "SHOP")
        assert kept["owner"] == "page-dev" and kept["children"] == shown["children"], kept


@pytest.mark.platform
def test_5_uncommitted_edits_in_a_worktree_show_on_the_next_request(client, tmp_path):
    """A worker edits an open story's plan and a fix's record without committing: the next
    request shows both, and only those items are derived again: an unedited fix keeps its row."""
    shop, alpha, _ = tmp_path / "shop", fix(client, "alpha"), fix(client, "beta")
    client.git("worktree", "add", "-q", "-b", "story/SHOP", str(shop))
    (shop / "plans").mkdir(exist_ok=True)
    (shop / "plans/SHOP.md").write_text(DOC, encoding="utf-8")
    (shop / ".factory/stories/SHOP").mkdir(parents=True)
    (shop / ".factory/stories/SHOP/story.json").write_text(json.dumps(
        {"doc": "plans/SHOP.md", "title": "Shoppers can save a basket", "status": "approved"}), encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=shop, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "Plan a basket"], cwd=shop, check=True, capture_output=True)
    with live(client) as url:
        first = snapshot(url)
        assert next(row for row in first["items"] if row["id"] == "SHOP")["owner"] is None
        assert "beta" in first["snapshot"]["rows_rebuilt"]
        (shop / "plans/SHOP.md").write_text(DOC.replace("## Tasks\n", "## Tasks\n\nOwner: page-dev\n", 1),
                                            encoding="utf-8")
        record = alpha / ".factory/fixes/alpha.json"
        record.write_text(json.dumps({**json.loads(record.read_text("utf-8")), "why": "Readers see the new title"}),
                          encoding="utf-8")
        edited = snapshot(url)
        rows = {row["id"]: row for row in edited["items"]}
        assert rows["SHOP"]["owner"] == "page-dev" and rows["alpha"]["title"] == "Readers see the new title", rows
        # The owner also brings the story's unstarted parts onto the board; the unedited fix stays.
        rebuilt = {row for row in edited["snapshot"]["rows_rebuilt"] if not row.startswith("SHOP/")}
        assert rebuilt == {"SHOP", "alpha"} and "beta" in rows, edited["snapshot"]


def test_6_a_restarted_board_shows_the_last_snapshot_at_once_and_rebuilds_warm(client):
    alpha, _ = fix(client, "alpha"), fix(client, "beta")
    with live(client) as url:
        snapshot(url)
        commit(alpha, "alpha.txt")
        last = snapshot(url)
    with live(client) as url:
        # Nothing moved while it was stopped: the saved snapshot, as it was, with no rebuild.
        assert snapshot(url) == last
        commit(alpha, "again.txt")
        changed = snapshot(url)
        assert changed["snapshot"]["version"] == last["snapshot"]["version"] + 1
        assert changed["snapshot"]["rows_rebuilt"] == ["alpha"], changed["snapshot"]


def test_7_a_slow_rebuild_never_holds_a_request(client):
    """Past the wait, a request gets the last snapshot marked as updating; the events stream says
    "changed" when the rebuild is done, and the next request has the change."""
    alpha = fix(client, "alpha")
    with live(client, FORGE_BOARD_REBUILD_WAIT="0") as url:
        first = snapshot(url)
        assert "updating" not in first["snapshot"]
        address = urlsplit(url)
        stream = http.client.HTTPConnection(address.hostname, address.port, timeout=60)
        stream.request("GET", f"/events?{address.query}")
        answer = stream.getresponse()
        assert answer.readline() == b"retry: 10000\n"
        commit(alpha, "alpha.txt")
        held = snapshot(url)
        assert held["snapshot"] == {**first["snapshot"], "updating": True}, held["snapshot"]
        lines = [answer.readline() for _ in range(3)]
        stream.close()
        assert lines[1] == b"event: changed\n", lines
        fresh = snapshot(url)
        assert fresh["snapshot"]["version"] == first["snapshot"]["version"] + 1
        assert fresh["snapshot"]["rows_rebuilt"] == ["alpha"] and "updating" not in fresh["snapshot"]


def test_8_board_requests_stay_fast(client):
    """Real requests, timed: an unchanged board answers under 100 ms, and a request after a
    one-item change answers within the half-second rebuild wait, under 1 s. Medians of a few
    requests keep a loaded test machine from deciding the result."""
    alpha = fix(client, "alpha")
    with live(client, FORGE_BOARD_REBUILD_WAIT="0.5") as url:
        snapshot(url)

        def timed():
            started = time.perf_counter()
            status, _, _ = get(url, "/board.json")
            assert status == 200
            return time.perf_counter() - started

        unchanged = statistics.median(timed() for _ in range(5))
        assert unchanged < 0.1, unchanged
        changed = []
        for n in range(3):
            commit(alpha, f"alpha-{n}.txt")
            changed.append(timed())
        assert statistics.median(changed) < 1.0, changed
