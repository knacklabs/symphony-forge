"""`forge board`'s live page: a server on 127.0.0.1 at a free port that answers only with this run's
token and stops with the command. A request serves the last snapshot while the cheaply checked
inputs are unchanged; otherwise one background thread rebuilds only the changed rows, a request
waits at most REBUILD_WAIT and then gets the last snapshot marked as updating, and `/events` says
"changed" when a new one exists. The last snapshot and its rows are saved, so a restart is instant.
"""
from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from forge import board, machine, repo, story

PLAN = re.compile(r"/plan/([A-Z][A-Z0-9-]*)")
# Nothing on the page loads from or talks to another origin, and nothing inline runs.
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
# Files the derivation itself writes under Forge's folder; watching them would rebuild forever.
WRITTEN = re.compile(r"(-cache\.json|prs-week-[\d-]+\.json|viewer-login\.json|known-issues\.json|board-snapshot\.json|"
                     r"\.guard|\.tmp|\.new)$")
# ponytail: the tests' seams, like FORGE_CHECKS_WAIT
FETCH_WAIT = float(os.environ.get("FORGE_BOARD_FETCH_WAIT", "60"))
# How long a request waits for a rebuild before it gets the last snapshot marked as updating.
REBUILD_WAIT = float(os.environ.get("FORGE_BOARD_REBUILD_WAIT", "0.5"))
TICK = 1.0  # seconds between the events stream's input checks
# ponytail: a placeholder page until the page shell part replaces it
PLACEHOLDER = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Forge board</title></head><body>'
               '<h1>Forge board</h1><p>The board is live. Its data is at <a href="board.json?token={token}">board.json</a>.')
DENIED = "This board link is not valid. Open the board again to get a new link."


class Snapshots:
    """The last Now snapshot and the untrimmed views, rebuilt only when their inputs change."""

    def __init__(self, top: Path):
        self.top = top
        self.common = Path(repo.git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=top))
        self.saved = self.common / "forge" / "board-snapshot.json"
        self.lock = threading.Lock()  # one derivation at a time: they share the row cache
        self.done = threading.Condition()
        self.wanted = threading.Event()
        self.forced, self.cache = False, {"rows": {}, "rebuilt": []}
        self.inputs: tuple[str, str] | None = None
        # When the newest finished rebuild began, and what stopped it, if anything.
        self.finished, self.failed = 0.0, None
        self.version, self.body, self.updating = 0, b"", b""  # updating: the same snapshot, marked so
        self.pages: dict[str, Any] = {}  # the untrimmed derivation, for one refs fingerprint
        try:  # the last run's snapshot and rows, so a restart shows the board at once and rebuilds warm
            saved = json.loads(self.saved.read_text(encoding="utf-8"))
            if saved["forge"] == board.__version__:
                self.cache["rows"], self.inputs = saved["rows"], tuple(saved["inputs"])
                self.publish(saved["view"])
        except (OSError, ValueError, KeyError, TypeError):
            pass  # no saved board, or one from another Forge: the first request waits for a build

    def watched(self) -> tuple[str, str]:
        """Two digests: git's refs and worktree HEADs, then everything else the board reads."""
        refs, rest = hashlib.sha1(), hashlib.sha1()
        files = [(refs, self.common / "packed-refs"), (refs, self.common / "HEAD")]
        files += [(refs, head) for head in (self.common / "worktrees").glob("*/HEAD")]
        for digest, base in ((refs, self.common / "refs"), (rest, self.common / "forge")):
            for folder, _, names in os.walk(base):
                files += [(digest, Path(folder, name)) for name in names if not WRITTEN.search(name)]
        for digest, path in sorted(files, key=lambda pair: str(pair[1])):
            try:
                found = path.stat()
            except OSError:  # removed while we looked: the next check sees it gone
                continue
            digest.update(f"{path}\0{found.st_mtime_ns}\0{found.st_size}\n".encode())
        rest.update(json.dumps(self.local_files()).encode())
        lanes = machine._repos_file().parent / "agent-runs.json"  # rewritten on every read, so by content
        rest.update(lanes.read_bytes() if lanes.is_file() else b"[]")  # the first read writes "[]"
        return refs.hexdigest(), rest.hexdigest()

    def local_files(self) -> list[tuple[str, str, int, int]]:
        """The files the board reads from each checkout's disk, uncommitted edits included, with their
        times and sizes: settings, the roadmap, and each Forge branch's own records and plan. Checkouts
        come from git's files, without a git process."""
        # ponytail: a Forge branch's edits to other items' records are not watched (tens of thousands of
        # files on a big repo); watch them too if a worker ever edits another item's record.
        found = []
        for tree, head in [(self.common.parent, self.common / "HEAD"),
                           *((None, head) for head in (self.common / "worktrees").glob("*/HEAD"))]:
            try:  # gitdir names the checkout's .git file, absolute or relative to this folder
                tree = tree or (head.parent / head.with_name("gitdir").read_text(encoding="utf-8").strip()).parent
                branch = head.read_text(encoding="utf-8").strip().removeprefix("ref: refs/heads/")
            except OSError:  # removed while we looked: the next check sees it gone
                continue
            kind, _, name = branch.partition("/")
            paths = [tree / "forge.toml", tree / "plans/roadmap.json"]
            if kind == "fix":
                paths.append(tree / f".factory/fixes/{name}.json")
            elif kind == "story":
                paths += [*(tree / f".factory/stories/{name}").rglob("*.json"), tree / f"plans/{name}.md",
                          tree / f"plans/{name}.read.md"]
            elif kind == "task":
                paths += [path for path in (tree / ".factory/stories").glob("*/tasks/*.json")
                          if f"{path.parent.parent.name}-{path.stem}" == name]
            elif kind == "forge":  # migrate's branch rewrites every record
                paths += (tree / ".factory").rglob("*.json")
            for path in paths:
                with contextlib.suppress(OSError):  # removed while we looked: the next check sees it gone
                    found.append((branch, path.relative_to(tree).as_posix(), (seen := path.stat()).st_mtime_ns,
                                  seen.st_size))
        return found

    def now(self) -> tuple[int, bytes]:
        """The Now view. When an input changed, a request waits up to REBUILD_WAIT for a rebuild
        that read inputs at least as new as it saw; past that it gets the last snapshot marked as
        updating, and the events stream says "changed" once the rebuild is done."""
        asked = time.monotonic()
        if self.watched() == self.inputs:
            return self.version, self.body
        self.wanted.set()
        with self.done:
            fresh = self.done.wait_for(lambda: self.finished >= asked, timeout=None if not self.body else REBUILD_WAIT)
            if fresh and self.failed is not None:
                raise self.failed
            return self.version, self.body if fresh else self.updating

    def changed(self) -> int:
        """The newest snapshot's version, asking for a rebuild when an input changed; never waits."""
        if self.watched() != self.inputs:
            self.wanted.set()
        return self.version

    def publish(self, view: dict[str, Any]) -> None:
        self.version = view["snapshot"]["version"]
        self.body = json.dumps(view).encode("utf-8")
        self.updating = json.dumps({**view, "snapshot": {**view["snapshot"], "updating": True}}).encode("utf-8")

    def keep_building(self) -> None:
        """Rebuilds whenever a request saw changed inputs or the minute's fetch asked for one."""
        while True:
            self.wanted.wait()
            self.wanted.clear()
            started, seen, failed = time.monotonic(), self.watched(), None
            try:
                if self.forced or seen != self.inputs:
                    self.forced = False
                    self.build(seen)
            except Exception as error:  # the waiting request shows it; this thread keeps building
                traceback.print_exc()
                failed = error
            with self.done:
                self.finished, self.failed = started, failed
                self.done.notify_all()

    def build(self, seen: tuple[str, str]) -> None:
        with self.lock:
            with repo.command_cache():
                self.cache.update(rebuilt=[], local=self.local_files())
                view = board.machine_board(self.top, cache=self.cache)
            view["snapshot"] = {"version": self.version + 1, "rows_rebuilt": self.cache["rebuilt"]}
            rows = json.dumps({"forge": board.__version__, "inputs": seen, "rows": self.cache["rows"], "view": view})
        with self.done:
            self.publish(view)
            self.inputs = seen
        with contextlib.suppress(OSError):  # a failed write only costs the next start its head start
            spare = self.saved.with_name(self.saved.name + ".tmp")
            spare.write_text(rows, encoding="utf-8")
            os.replace(spare, self.saved)

    def untrimmed(self) -> dict[str, Any]:
        """Every item, finished ones included, cached until a ref changes."""
        refs = self.watched()[0]
        with self.lock:
            if self.pages.get("refs") != refs:
                with repo.command_cache():
                    self.pages = {"refs": refs, "view": board.machine_board(self.top, trim=False, cache=self.cache)}
            return self.pages["view"]

    def plan(self, key: str) -> str:
        with self.lock, repo.command_cache():
            return story._plan(self.top, key)

    def keep_fetching(self) -> None:
        """At most once a minute: the remote's refs, then GitHub's facts with them."""
        while True:
            time.sleep(FETCH_WAIT)
            # Not repo.run: its command cache belongs to the rebuild running now.
            subprocess.run(["git", "fetch", "-q", "--prune", "--tags", "origin"], cwd=self.top,
                           stdin=subprocess.DEVNULL, capture_output=True)
            self.forced = True
            self.wanted.set()


def handler(snapshots: Snapshots, token: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:
            pass  # request lines carry the token; the terminal never shows them

        def send(self, status: int, kind: str, body: bytes, **headers: str) -> None:
            self.send_response(status)
            for name, value in {"Content-Type": kind, "Content-Length": str(len(body)),
                                "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                                # The token is in the address; a followed link must never carry it.
                                "Referrer-Policy": "no-referrer", **headers}.items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def say(self, status: int, message: str) -> None:
            self.send(status, "application/json", json.dumps({"error": message}).encode("utf-8"))

        def do_GET(self) -> None:
            url = urlsplit(self.path)
            query = parse_qs(url.query)
            if not hmac.compare_digest(query.get("token", [""])[0].encode(), token.encode()):
                self.send(403, "text/plain; charset=utf-8", DENIED.encode("utf-8"))
                return
            try:
                self.route(url.path, query)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the page closed or reloaded
            except repo.Refused as refusal:
                self.say(500, str(refusal).splitlines()[0])
            except Exception:
                traceback.print_exc()
                self.say(500, "The board could not read the work. The terminal that runs it shows why.")

        def route(self, path: str, query: dict[str, list[str]]) -> None:
            if path == "/":
                page = PLACEHOLDER.format(token=token).encode("utf-8")
                self.send(200, "text/html; charset=utf-8", page, **{"Content-Security-Policy": CSP})
            elif path == "/board.json":
                self.board(query.get("page", ["now"])[0], query.get("id", [""])[0])
            elif plan := PLAN.fullmatch(path):
                text = snapshots.plan(plan[1])
                if not text:
                    self.say(404, "This story has no plan yet.")
                else:
                    self.send(200, "text/plain; charset=utf-8", text.encode("utf-8"))
            elif path == "/events":
                self.events()
            else:
                self.say(404, "The board has no page here.")

        def board(self, page: str, item: str) -> None:
            if page == "now":
                self.send(200, "application/json", snapshots.now()[1])
            elif page in ("releases", "insights"):
                self.send(200, "application/json", json.dumps(snapshots.untrimmed()).encode("utf-8"))
            elif page == "item":
                rows = [row for parent in snapshots.untrimmed()["items"] for row in (parent, *parent["children"])]
                found = next((row for row in rows if row["id"] == item), None)
                if found is None:
                    self.say(404, "No item by that name is on the board.")
                else:
                    self.send(200, "application/json", json.dumps({"item": found}).encode("utf-8"))
            else:
                self.say(404, "The board has no page by that name.")

        def events(self) -> None:
            """Says "changed" each time a new snapshot exists; the page then reads /board.json."""
            self.send_response(200)
            for name, value in (("Content-Type", "text/event-stream"), ("Cache-Control", "no-store"),
                                ("X-Content-Type-Options", "nosniff")):
                self.send_header(name, value)
            self.end_headers()
            sent, quiet = snapshots.changed(), 0.0
            self.wfile.write(b"retry: 10000\n\n")
            self.wfile.flush()
            while True:
                time.sleep(TICK)
                version = snapshots.changed()
                quiet += TICK
                if version != sent:
                    self.wfile.write(f"event: changed\ndata: {version}\n\n".encode())
                    sent, quiet = version, 0.0
                elif quiet >= 15:  # a comment line, so a closed page ends this thread
                    self.wfile.write(b": still here\n\n")
                    quiet = 0.0
                self.wfile.flush()

    return Handler


def serve(top: Path) -> int:
    print("Reading the work for the board…", flush=True)
    snapshots = Snapshots(top)
    threading.Thread(target=snapshots.keep_building, daemon=True).start()
    if not snapshots.body:
        snapshots.now()  # no saved board yet: the page waits for this first build, once
    snapshots.changed()  # a saved board starts its rebuild now when the work moved since
    token = secrets.token_urlsafe(24)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler(snapshots, token))
    server.daemon_threads = True
    url = f"http://127.0.0.1:{server.server_address[1]}/?token={token}"
    print(f"The board is live at {url}\nIt stays live until you press Ctrl-C.", flush=True)
    threading.Thread(target=snapshots.keep_fetching, daemon=True).start()
    if sys.stdout.isatty():  # ponytail: open it for a person at a terminal; never in a pipe or a test
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    print("The board has stopped.")
    return 0
