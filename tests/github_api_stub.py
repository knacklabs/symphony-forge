"""A small local GitHub API edge for command-level tests."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class GitHubApiStub:
    def __init__(self) -> None:
        self._answers: dict[tuple[str, str], list[tuple[int, Any]]] = {}
        self.requests: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self._answer()

            def do_POST(self) -> None:
                self._answer()

            def _answer(self) -> None:
                size = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(size) if size else b""
                try:
                    body = json.loads(raw) if raw else None
                except ValueError:
                    body = raw.decode("utf-8", errors="replace")
                key = (self.command, self.path)
                with owner._lock:
                    owner.requests.append({
                        "method": self.command,
                        "path": self.path,
                        "authorization": self.headers.get("Authorization"),
                        "body": body,
                    })
                    answers = owner._answers.get(key, [(404, {"message": "Not Found"})])
                    status, data = answers.pop(0) if len(answers) > 1 else answers[0]
                payload = json.dumps(data).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, _format: str, *args: Any) -> None:
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def respond(self, method: str, path: str, data: Any, status: int = 200) -> None:
        with self._lock:
            self._answers.setdefault((method.upper(), path), []).append((status, data))

    def __enter__(self) -> GitHubApiStub:
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
