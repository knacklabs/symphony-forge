"""Quota recovery at the command boundary.

Audit: the command must resume after the reset, including refused writes.
Transport tests stop on 403 and cannot catch this regression. Only GitHub and
the existing child clock are fake; no production test seam is required.
"""
import json
from datetime import datetime, timezone

import pytest

from test_close import env  # noqa: F401
from test_merge_command import _ready, _merge_at_github
from test_board_server import live, snapshot

STORY = "rate-limit-waits"


def limit(env, prefix, kind):
    error = {
        "rest": "API rate limit exceeded for 192.0.2.1. (HTTP 403)",
        "graphql": "API rate limit already exceeded for user ID 1.",
        "secondary": "You have exceeded a secondary rate limit. Please wait a few minutes before you try again. (HTTP 429)",
        "secondary-403": "HTTP 403: You have exceeded a secondary rate limit",
        "quota-failed": "API rate limit exceeded for 192.0.2.1. (HTTP 403)",
        "branch": 'no pull requests found for branch "fix/rate-limit-waits"',
    }[kind]
    stub = env.repo.bin / "gh"
    first, rest = stub.read_text("utf-8").split("\n", 1)
    code = f'''import json, pathlib, sys, time
here = pathlib.Path(__file__).resolve().parent
args = sys.argv[1:]
marker = here / "quota-attempt"
if args[:{len(prefix)}] == {prefix!r}:
    with (here / "quota-times").open("a", encoding="utf-8") as log:
        log.write(str(time.monotonic()) + "\\n")
    if not marker.exists():
        marker.write_text(str(int(time.time()) + 600), encoding="utf-8")
        print({error!r}, file=sys.stderr)
        sys.exit(1)
if args[:2] == ["api", "rate_limit"]:
    if {kind == 'quota-failed'!r}:
        print("HTTP 403: You have exceeded a secondary rate limit.", file=sys.stderr)
        sys.exit(1)
    # After the refused request succeeds, model the restored quota too. The
    # admission gate now reads this endpoint again after recovery.
    attempts = here / "quota-times"
    if attempts.exists() and len(attempts.read_text("utf-8").splitlines()) >= 2:
        print(json.dumps(dict(resources={{name: dict(remaining=5000, reset=int(time.time()) + 3600)
                                          for name in ("core", "graphql")}})))
        sys.exit(0)
    reset = int(marker.read_text("utf-8"))
    core = reset + {1000 if prefix == ['api', 'graphql'] else 0}
    graphql = reset + {0 if prefix == ['api', 'graphql'] else 1000}
    print(json.dumps(dict(resources=dict(core=dict(remaining={10 if kind in ('secondary', 'secondary-403') else 0}, reset=core),
                                        graphql=dict(remaining=0, reset=graphql)))))
    sys.exit(0)
'''
    stub.write_text(first + "\n" + code + rest, "utf-8")


@pytest.mark.parametrize("command,kind", [("close", "rest"),
                                         ("merge", "rest"), ("land", "rest"),
                                         ("land", "graphql"), ("close", "secondary"),
                                         ("merge", "secondary-403"),
                                         ("close", "quota-failed")])
def test_1_commands_wait_for_github_reset_and_continue(env, fake_clock, command, kind):
    if kind == "graphql":
        item, where = "", env.repo.path
        prefix = ["api", "graphql"]
        env.gh.respond(*prefix, stdout=json.dumps({"data": {"repository": {"pullRequests": {"nodes": []}}}}))
    elif command == "close":
        item, where = env.start_fix()
        prefix = (["api", "--paginate", "--jq", ".check_runs[]"]
                  if kind == "rest" else ["pr", "edit"])
    else:
        item, where = _ready(env)
        head = env.repo.git("rev-parse", "HEAD", cwd=where)
        env.gh.respond("pr", "view", stdout=json.dumps({
            "number": 7, "state": "OPEN", "baseRefName": "main", "headRefOid": head,
            "headRefName": "fix/tidy-readme", "title": "Tidy readme", "isDraft": False}))
        _merge_at_github(env)
        if command == "merge":
            # Keep the fresh core-reset proof. Land also runs close, whose
            # admission lookup supplies its cached-failure case below.
            (env.tmp / "clock" / "elapsed").write_text("61", encoding="utf-8")
        prefix = ["pr", "view"]
    limit(env, prefix, kind)
    done = env.repo.forge(command, "--all" if kind == "graphql" else item,
                          cwd=where if command == "close" else env.repo.path)
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stderr.count("GitHub rate limit reached. Wait until ") == 1
    attempts = [float(line) for line in (env.repo.bin / "quota-times").read_text("utf-8").splitlines()]
    assert len(attempts) >= 2
    # Close's admission lookup (also inside land) precedes the stub's exhaustion. It
    # fails (there is no reset marker yet), and its one-minute cache also serves
    # recovery. The old contract made another immediate quota request here.
    cached_failure = command in ("close", "land") and kind == "rest"
    pause = 60 if cached_failure or kind in ("quota-failed", "secondary", "secondary-403") else 603
    assert pause - 1 <= attempts[1] - attempts[0] < pause + 7
    if not cached_failure and kind not in ("secondary", "secondary-403", "quota-failed"):
        reset = int((env.repo.bin / "quota-attempt").read_text("utf-8"))
        when = datetime.fromtimestamp(reset + 3, timezone.utc).strftime("%H:%M:%S UTC")
        assert f"GitHub rate limit reached. Wait until {when}, then continue.\n" in done.stderr
    if command == "close":
        assert env.gh_calls("pr", "ready")
    elif kind != "graphql":
        assert env.repo.git("show", "origin/main:app.py") == "print('hello')"
    else:
        assert "Needs you (0)" in done.stdout


@pytest.mark.parametrize("command", ["board", "next", "server"])
def test_2_views_keep_local_data_without_a_rate_limit_wait(env, command):
    item, _ = env.start_fix()
    limit(env, ["pr", "list", "--state", "open"], "rest")
    # Keep the server's periodic sleeps real; record and advance only the quota wait.
    shim = env.repo.bin / "forge"
    sleep_log = env.repo.bin / "quota-sleep"
    shim.write_text(shim.read_text("utf-8").replace("from forge.cli import main", f'''
import time
from pathlib import Path
real_sleep = time.sleep
def sleep(seconds):
    if seconds >= 599:
        Path({json.dumps(sleep_log.as_posix())}).write_text(str(seconds), encoding="utf-8")
    else:
        real_sleep(seconds)
time.sleep = sleep
from forge.cli import main
'''), "utf-8")
    if command == "server":
        with live(env.repo) as url:
            assert item in json.dumps(snapshot(url))
    else:
        done = env.repo.forge(*(["board", "--json"] if command == "board" else ["next"]))
        assert done.returncode == 0, done.stdout + done.stderr
        assert item in done.stdout
        assert "GitHub rate limit reached" not in done.stderr
    assert (env.repo.bin / "quota-attempt").exists()
    assert not sleep_log.exists()


def test_3_a_branch_name_is_not_a_rate_limit_error(env, fake_clock):
    env.commit(env.repo.path, "forge.toml", (env.repo.path / "forge.toml").read_text("utf-8")
               + 'merge = "agent"\n')
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start("rate-limit-waits", "fix/rate-limit-waits", ".factory/fixes/rate-limit-waits.json",
                        {"kind": "fix", "why": "Wait for GitHub", "done_when": "Commands resume"},
                        {"app.py": "print('hello')\n"})
    limit(env, ["pr", "view"], "branch")
    done = env.repo.forge("merge", item)
    assert done.returncode == 1, done.stdout + done.stderr
    assert "GitHub rate limit reached" not in done.stderr
    assert len((env.repo.bin / "quota-times").read_text("utf-8").splitlines()) == 1
