"""`forge board`'s live page: a server on 127.0.0.1 at a free port that only answers with this run's
token, and stops when the command ends.

A full derivation takes seconds, so the server never rebuilds blindly. Each request first checks
the inputs cheaply: git's refs, Forge's record and event files under the git folder, the lanes
file and each worktree's HEAD. When none changed it serves the last snapshot as it is; otherwise
it rebuilds, and only rows whose own inputs changed are derived again. `/events` tells the page
when a new snapshot exists. Every minute the server fetches from the remote and refreshes
GitHub's facts.
"""
from __future__ import annotations

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

APP = Path(__file__).with_name("board_app")
ASSET = re.compile(r"/([a-z][a-z-]*\.(?:js|css))")
PLAN = re.compile(r"/plan/([A-Z][A-Z0-9-]*)")
TYPES = {"js": "text/javascript; charset=utf-8", "css": "text/css; charset=utf-8"}
# Nothing on the page loads from or talks to another origin, and nothing inline runs.
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
# Files the derivation itself writes under Forge's folder; watching them would rebuild forever.
WRITTEN = re.compile(r"(-cache\.json|\.tmp|\.new|board\.html)$")
# ponytail: the tests' seam, like FORGE_CHECKS_WAIT
FETCH_WAIT = float(os.environ.get("FORGE_BOARD_FETCH_WAIT", "60"))
TICK = 1.0  # seconds between the events stream's input checks
DENIED = "This board link is not valid. Open the board again to get a new link."


class Snapshots:
    """The last Now snapshot and the untrimmed views, rebuilt only when their inputs change."""

    def __init__(self, top: Path):
        self.top = top
        self.common = Path(repo.git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=top))
        self.lock = threading.Lock()
        self.cache: dict[str, Any] = {"rows": {}, "rebuilt": []}
        self.inputs: tuple[str, str] | None = None
        self.version = 0
        self.body = b""
        self.pages: dict[str, Any] = {}  # the untrimmed derivation, for one refs fingerprint

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
        lanes = machine._repos_file().parent / "agent-runs.json"  # rewritten on every read, so by content
        try:
            rest.update(lanes.read_bytes())
        except OSError:
            rest.update(b"[]")  # the first read writes an empty line of runs
        return refs.hexdigest(), rest.hexdigest()

    def now(self, force: bool = False) -> tuple[int, bytes]:
        """The Now view, rebuilt first when an input changed since the last one."""
        seen = self.watched()
        if seen == self.inputs and not force:
            return self.version, self.body
        with self.lock:
            seen = self.watched()  # another request may have rebuilt while this one waited
            if seen != self.inputs or force:
                with repo.command_cache():
                    self.cache["rebuilt"] = []
                    view = board.machine_board(self.top, cache=self.cache)
                self.version += 1
                view["snapshot"] = {"version": self.version, "rows_rebuilt": self.cache["rebuilt"]}
                self.body, self.inputs = json.dumps(view).encode("utf-8"), seen
            return self.version, self.body

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
            # Not repo.run: its command cache belongs to whichever rebuild runs at the time.
            subprocess.run(["git", "fetch", "-q", "--prune", "--tags", "origin"], cwd=self.top,
                           stdin=subprocess.DEVNULL, capture_output=True)
            try:
                self.now(force=True)
            except Exception:  # the next request shows the error; this thread keeps fetching
                traceback.print_exc()


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
                shell = (APP / "shell.html").read_text(encoding="utf-8").replace("{{token}}", token)
                self.send(200, "text/html; charset=utf-8", shell.encode("utf-8"), **{"Content-Security-Policy": CSP})
            elif (asset := ASSET.fullmatch(path)) and (APP / asset[1]).is_file():
                self.send(200, TYPES[asset[1].rsplit(".", 1)[1]], (APP / asset[1]).read_bytes())
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
            sent, quiet = snapshots.now()[0], 0.0
            self.wfile.write(b"retry: 10000\n\n")
            self.wfile.flush()
            while True:
                time.sleep(TICK)
                version = snapshots.now()[0]
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
    snapshots.now()  # the page shows the first snapshot at once
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
