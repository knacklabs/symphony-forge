"""Quota recovery at the command boundary.

Audit: the command must resume after the reset, including refused writes.
Transport tests stop on 403 and cannot catch this regression. Only GitHub and
the existing child clock are fake; no production test seam is required.
"""
import json

import pytest

from test_close import env  # noqa: F401
from test_merge_command import _ready, _merge_at_github

STORY = "rate-limit-waits"


@pytest.mark.parametrize("command,header", [("close", True), ("close", False),
                                           ("merge", False), ("land", True)])
def test_1_commands_wait_for_github_reset_and_continue(env, fake_clock, command, header):
    if command == "close":
        item, where = env.start_fix()
        prefix = ["pr", "edit"]
    else:
        item, where = _ready(env)
        head = env.repo.git("rev-parse", "HEAD", cwd=where)
        env.gh.respond("pr", "view", stdout=json.dumps({
            "number": 7, "state": "OPEN", "baseRefName": "main", "headRefOid": head,
            "headRefName": "fix/tidy-readme", "title": "Tidy readme", "isDraft": False}))
        _merge_at_github(env)
        prefix = ["pr", "view"]
    stub = env.repo.bin / "gh"
    source = stub.read_text("utf-8")
    code = f'''import json, pathlib, sys, time
here = pathlib.Path(__file__).resolve().parent
args = sys.argv[1:]
marker = here / "quota-attempt"
if args[:2] == {prefix!r}:
    with (here / "quota-times").open("a", encoding="utf-8") as log:
        log.write(str(time.monotonic()) + "\\n")
    if not marker.exists():
        marker.write_text(str(int(time.time()) + 600), encoding="utf-8")
        print({("GraphQL: API rate limit exceeded" if command == "merge" else "HTTP 403: API rate limit exceeded")!r}, file=sys.stderr)
        if {header!r}:
            print("x-ratelimit-reset: " + marker.read_text("utf-8"), file=sys.stderr)
        sys.exit(1)
if args[:2] == ["api", "rate_limit"]:
    reset = int(marker.read_text("utf-8"))
    core = reset + {1000 if command == 'merge' else 0}
    graphql = reset + {0 if command == 'merge' else 1000}
    print(json.dumps(dict(resources=dict(core=dict(remaining=0, reset=core),
                                        graphql=dict(remaining=0, reset=graphql)))))
    sys.exit(0)
'''
    first, rest = source.split("\n", 1)
    stub.write_text(first + "\n" + code + rest, "utf-8")
    done = env.repo.forge(command, item, cwd=where if command == "close" else env.repo.path)
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stderr.count("GitHub rate limit reached. Wait until ") == 1
    attempts = [float(line) for line in (env.repo.bin / "quota-times").read_text("utf-8").splitlines()]
    assert len(attempts) >= 2
    assert 602 <= attempts[1] - attempts[0] < 610
    if command == "close":
        assert env.gh_calls("pr", "ready")
    else:
        assert env.repo.git("show", "origin/main:app.py") == "print('hello')"
