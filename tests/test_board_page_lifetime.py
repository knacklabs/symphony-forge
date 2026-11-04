"""The real board command works only for open event streams and stops after idle time.

Audit: the contract is process lifetime and background work at the HTTP boundary.
The regression is the unconditional fetch/rebuild loop and serve_forever. Existing
server tests terminate their processes themselves and cannot catch an idle leak.
Only the command's clock is advanced; no production test flag or Forge import is needed.
"""
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
from urllib.parse import urlsplit

import pytest

from conftest import patient
from test_board_server import client, get  # noqa: F401

STORY = "board-stops-with-no-page"


def test_1_no_page_pauses_work_and_stops_after_thirty_minutes(client, tmp_path):
    clock, work = tmp_path / "elapsed", tmp_path / "background"
    clock.write_text("0", encoding="utf-8")
    work.write_text("", encoding="utf-8")
    # Change only the clock at the executable boundary. Audit real fetches and
    # snapshot writes rather than replacing the work whose absence we assert.
    launcher = client.bin / "forge"
    source = launcher.read_text("utf-8")
    instrument = f'''
import time, pathlib
_real_clock = time.monotonic
_clock_file = pathlib.Path({json.dumps(clock.as_posix())})
time.monotonic = lambda: _real_clock() + float(_clock_file.read_text("utf-8"))
def _observe(event, args):
    fetch = event == "subprocess.Popen" and args[1][:2] == ["git", "fetch"]
    build = (event == "open" and isinstance(args[0], str)
             and args[0].endswith("board-snapshot.json.tmp") and args[1] == "w")
    if fetch or build:
        with open({json.dumps(work.as_posix())}, "a", encoding="utf-8") as log:
            log.write("fetch\\n" if fetch else "build\\n")
sys.addaudithook(_observe)
'''
    patient(lambda: launcher.write_text(source.replace("from forge.cli import main",
                                                      instrument + "from forge.cli import main"), "utf-8"))

    def advance(seconds):
        spare = clock.with_suffix(".tmp")
        patient(lambda: spare.write_text(str(seconds), encoding="utf-8"))
        patient(lambda: os.replace(spare, clock))

    process = subprocess.Popen([sys.executable, str(launcher), "board"], cwd=client.path,
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", env={**os.environ, "FORGE_BOARD_FETCH_WAIT": "0.2"})
    lines = queue.Queue()
    threading.Thread(target=lambda: [*map(lines.put, process.stdout), lines.put(None)], daemon=True).start()
    streams = []
    try:
        while (line := lines.get(timeout=60)) is not None:
            if found := re.search(r"http://127\.0\.0\.1:\d+/\?token=[\w-]+", line):
                url = found[0]
                break
        assert line is not None, process.stderr.read()
        # No page ever opened: even initial derivation waits for a reader.
        advance(1790)
        with pytest.raises(subprocess.TimeoutExpired):
            process.wait(timeout=2)
        assert work.read_text("utf-8") == "", "A board with no page did background work"
        address = urlsplit(url)

        def open_page():
            connection = socket.create_connection((address.hostname, address.port), timeout=30)
            connection.sendall(f"GET /events?{address.query} HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n".encode())
            response = http.client.HTTPResponse(connection)
            streams.append((connection, response))
            response.begin()
            assert response.status == 200
            assert response.readline() == b"retry: 10000\n"
            return connection, response

        first, first_response = open_page()
        second, response = open_page()
        first.shutdown(socket.SHUT_RDWR)
        first_response.close()
        first.close()
        advance(4000)
        # One page is still open. A real snapshot and fetch prove that it keeps
        # the server working beyond the idle deadline, even after another closes.
        assert get(url, "/board.json")[0] == 200
        deadline = time.monotonic() + 30
        while "fetch" not in work.read_text("utf-8") and time.monotonic() < deadline:
            assert response.readline(), "The remaining page lost its server"
        assert "fetch" in work.read_text("utf-8")
        assert "build" in work.read_text("utf-8")
        second.shutdown(socket.SHUT_RDWR)
        response.close()
        second.close()
        # Let the server observe the socket close, then move within the idle window.
        with pytest.raises(subprocess.TimeoutExpired):
            process.wait(timeout=2)
        before = work.read_text("utf-8")
        advance(5790)
        with pytest.raises(subprocess.TimeoutExpired):
            process.wait(timeout=2)
        assert work.read_text("utf-8") == before, "The closed pages left background work active"
        advance(5810)
        assert process.wait(timeout=10) == 0
        output = []
        while (line := lines.get(timeout=10)) is not None:
            output.append(line)
        assert "The board stopped because no page was open for 30 minutes." in "".join(output)
    finally:
        for connection, response in streams:
            response.close()
            connection.close()
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=30)
        process.stdout.close()
        process.stderr.close()
