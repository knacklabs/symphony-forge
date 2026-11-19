"""Audit: budget concurrent waits before exhaustion, at the command boundary.

Reset recovery tests cannot detect excessive admission. Only GitHub and elapsed
time are fake; commands, processes, locks and worktrees stay real. No new seam.
"""
import json
import subprocess
import sys
import time

import pytest

from conftest import machine_cores
from test_close import env  # noqa: F401
from test_merge_command import _ready, _merge_at_github
from test_queue_land_all import client, _fix  # noqa: F401

STORY = "check-waits-by-quota"


@pytest.mark.parametrize("command", ["close", "merge", "land"])
def test_1_check_waits_pause_for_quota_and_share_minute_reads(env, fake_clock, command):
    if command in ("merge", "land"):
        item, where = _ready(env)
        head = env.repo.git("rev-parse", "HEAD", cwd=where)
        env.gh.respond("pr", "view", stdout=json.dumps({
            "number": 7, "state": "OPEN", "baseRefName": "main", "headRefOid": head,
            "headRefName": "fix/tidy-readme", "title": "Tidy readme", "isDraft": False}))
        _merge_at_github(env)
        (env.tmp / "clock" / "elapsed").write_text("61", encoding="utf-8")
    else:
        item, where = env.start_fix()
    stub = env.repo.bin / "gh"
    first, rest = stub.read_text("utf-8").split("\n", 1)
    stub.write_text(first + "\n" + '''import json, pathlib, sys, time
if sys.argv[1:3] == ["api", "rate_limit"]:
    log = pathlib.Path(__file__).resolve().parent / "budget-reads"
    rows = log.read_text().splitlines() if log.exists() else []
    with log.open("a") as stream: stream.write(str(time.monotonic()) + "\\n")
    amount = 0 if len(rows) < 2 else 5000
    print(json.dumps({"resources": {name: {"remaining": amount, "reset": int(time.time()) + 3600}
                                    for name in ("core", "graphql")}}))
    sys.exit(0)
''' + rest, encoding="utf-8")
    done = env.repo.forge(command, item, cwd=where if command == "close" else env.repo.path)
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.count("Waiting for GitHub API quota before another check wait.") == 1
    reads = [float(row) for row in (env.repo.bin / "budget-reads").read_text().splitlines()]
    assert len(reads) == 3
    assert all(after - before >= 60 for before, after in zip(reads, reads[1:]))


@pytest.mark.parametrize("places", [1, 2])
@pytest.mark.timeout(240)
def test_2_land_caps_concurrent_waits_and_releases_places(client, monkeypatch, places):
    env = client
    machine_cores(env.repo, 8)
    for number in range(3):
        _fix(env, monkeypatch, f"change-{number}", number + 1, {f"file{number}.py": "VALUE = 1\n"})
    stub = env.repo.bin / "gh"
    stub.write_text(stub.read_text("utf-8").replace(
        'if args[:4] == ["api", "--paginate", "--jq", ".check_runs[]"]:',
        f'''if args[:2] == ["api", "rate_limit"]:
    answer(json.dumps({{"resources": {{name: {{"remaining": {places * 3000}, "reset": int(time.time()) + 3600}}
                                       for name in ("core", "graphql")}}}}))
if args[:4] == ["api", "--paginate", "--jq", ".check_runs[]"]:
    append_json(here / "budget-starts", args)
    import threading
    until = time.monotonic() + 45
    while not (here / "budget-release").exists() and time.monotonic() < until:
        threading.Event().wait(0.05)
if args[:4] == ["api", "--paginate", "--jq", ".check_runs[]"]:''', 1), encoding="utf-8")
    output, error = env.tmp / "land.out", env.tmp / "land.err"
    with output.open("wb") as stdout, error.open("wb") as stderr:
        process = subprocess.Popen([sys.executable, str(env.repo.bin / "forge"), "land", "--all"],
                                   cwd=env.repo.path, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
        rows = []
        try:
            deadline = time.monotonic() + 90
            while process.poll() is None and time.monotonic() < deadline:
                starts = env.repo.bin / "budget-starts"
                rows = starts.read_text().splitlines() if starts.exists() else []
                if len(rows) > places or (len(rows) == places and "Waiting for GitHub API quota" in output.read_text()):
                    break
                time.sleep(0.05)
            assert len(rows) == places, output.read_text() + error.read_text()
            assert "Waiting for GitHub API quota" in output.read_text()
        finally:
            (env.repo.bin / "budget-release").touch()
            try:
                process.wait(timeout=120)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
    assert process.returncode == 0, output.read_text() + error.read_text()
    assert "Merged (3):" in output.read_text()
    reads = [row["at"] for row in (json.loads(line) for line in
             (env.repo.bin / "gh-timed.jsonl").read_text().splitlines())
             if row["args"][:2] == ["api", "rate_limit"]]
    assert reads
    assert all(after - before >= 60 for before, after in zip(reads, reads[1:]))
