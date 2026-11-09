"""Close waits out temporary review rate limits without spending its failure allowance.

Test audit: two real closes must finish after repeated provider throttling.
The old loop spends its failure allowance on usage-limit messages. The earlier
single-close test missed overlap and wait ordering. The fake clock blocks on a
socket handshake, so one trace proves waits precede retries. Only third-party
answers and standard-library sleep are faked, with no production test seam.
"""
import json
import os
import socket
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from test_close import CLEAN, FAILED, env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "review-retries-rate-limit"


@pytest.mark.platform
@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_1_close_waits_and_retries_rate_limits_before_counting_failures(env, adopted):
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    client(env, adopted)
    env.commit(env.repo.path, "forge.toml", config, "Use the test checks")
    env.repo.git("push", "-q", "origin", "main")
    first, first_tree = env.start_fix()
    second, second_tree = env.start("second-greeting", "fix/second-greeting",
        ".factory/fixes/second-greeting.json",
        {"kind": "fix", "why": "Readers need a greeting", "done_when": "Readers see a greeting"},
        {"other.py": "print('welcome')\n"})
    errors = ["You've hit your usage limit", "usage_limit_reached", "429",
              "rate limit", "Too Many Requests"]
    for item in (first, second):
        (env.tmp / f"{item}.json").write_text(json.dumps([
            FAILED, *({"exit": 3, "report": None, "say": error} for error in errors), CLEAN]),
            "utf-8")
    expected = [["attempt"], ["attempt"]]
    for delay in (30, 60, 120, 120, 120):
        expected.extend([["wait", delay], ["attempt"]])
    traces = {first: [], second: []}
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(2)
        server.settimeout(20)
        exchange = f'''
import json, os, socket
def exchange(event):
    with socket.create_connection({server.getsockname()!r}, timeout=20) as connection:
        connection.sendall(json.dumps([os.environ["RETRY_ITEM"], event]).encode() + b"\\n")
        assert connection.recv(1) == b"x"
'''
        shim = env.repo.bin / "forge"
        shim.write_text(shim.read_text("utf-8").replace("from forge.cli import main", exchange + f'''
import time
os.environ["RETRY_ITEM"] = sys.argv[2]
os.environ["AUTOREVIEW_STUB"] = {json.dumps(env.tmp.as_posix())} + "/" + sys.argv[2] + ".json"
real_sleep = time.sleep
def backoff(seconds):
    if seconds in (30, 60, 120):
        exchange(["wait", seconds])
    else:
        real_sleep(seconds)
time.sleep = backoff
from forge.cli import main
'''), "utf-8")
        helper = Path(os.environ["AUTOREVIEW"])
        helper.write_text(helper.read_text("utf-8").replace("args = sys.argv[1:]",
            exchange + '\nexchange(["attempt"])\nargs = sys.argv[1:]'), "utf-8")
        with ThreadPoolExecutor(max_workers=2) as pool:
            closes = [pool.submit(env.repo.forge, "close", item, cwd=tree)
                      for item, tree in ((first, first_tree), (second, second_tree))]
            pending = []
            try:
                for index in range(2 * len(expected)):
                    connection, _ = server.accept()
                    pending.append(connection)
                    connection.settimeout(20)
                    with connection.makefile("rb") as message:
                        item, event = json.loads(message.readline())
                    traces[item].append(event)
                    # Neither first attempt can return until both closes reach the service.
                    if index == 0:
                        continue
                    for waiting in pending:
                        waiting.sendall(b"x")
                        waiting.close()
                    pending.clear()
            except TimeoutError:
                pass  # Report command failures and incomplete traces below.
            finally:
                for waiting in pending:
                    waiting.close()
            results = [close.result() for close in closes]
    for closed in results:
        assert closed.returncode == 0, closed.stdout + closed.stderr
        assert "Review service rate limit. Waiting" in closed.stderr
    assert traces == {first: expected, second: expected}
