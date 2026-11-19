"""Audit: budget concurrent waits before exhaustion, at the command boundary.

Reset recovery tests cannot detect excessive admission. Only GitHub and elapsed
time are fake; commands, processes, locks and worktrees stay real. No new seam.
Unequal resources and a falling budget expose ignored pools and occupied holes.
"""
import json
import subprocess
import sys
import time

import pytest

from conftest import patient
from test_close import env  # noqa: F401
from test_merge_command import _ready, _merge_at_github
from test_queue_land_all import client, _fix  # noqa: F401

STORY = "check-waits-by-quota"
pytestmark = pytest.mark.platform


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


@pytest.mark.timeout(180)
@pytest.mark.parametrize(("initial_core", "initial_graphql", "reduced_core", "reduced_graphql"), [
    pytest.param(5760, 720, 5760, 240, id="graphql-limited"),
    pytest.param(8640, 480, 2880, 480, id="core-limited"),
])
def test_2_concurrent_closes_follow_both_quotas_when_the_budget_falls(
        client, monkeypatch, fake_clock, initial_core, initial_graphql, reduced_core, reduced_graphql):
    env = client
    places = [_fix(env, monkeypatch, f"change-{number}", number + 1,
                   {f"file{number}.py": "VALUE = 1\n"}) for number in range(3)]
    # The parent alone advances the shared poll clock. Subprocess deadlines
    # retain real time, including while a GitHub response is held.
    clock = env.tmp / "clock"
    (clock / "sitecustomize.py").write_text(
        'import subprocess, time\nfrom pathlib import Path\nfrom types import SimpleNamespace\n'
        'subprocess.time = SimpleNamespace(sleep=time.sleep)\nreal = time.monotonic\n'
        f'offset = Path({json.dumps((clock / "elapsed").as_posix())})\n'
        'time.monotonic = lambda: real() + float(offset.read_text("utf-8"))\n'
        'real_sleep = time.sleep\ntime.sleep = lambda seconds: real_sleep(0.1 if seconds == 15 else seconds)\n',
        encoding="utf-8")
    stub = env.repo.bin / "gh"
    intercept = '''import threading, time
if args[:2] == ["api", "rate_limit"]:
    core, graphql = reduced_values if (here / "budget-shrunk").exists() else initial_values
    append_json(here / "quota-reads", {"at": time.monotonic(), "core": core, "graphql": graphql})
    print(json.dumps({"resources": {
        "core": {"remaining": core, "reset": int(time.time()) + 3600},
        "graphql": {"remaining": graphql, "reset": int(time.time()) + 3600}}}))
    sys.exit(0)
if args[:4] == ["api", "--paginate", "--jq", ".check_runs[]"]:
    branch = subprocess.run(["git", "branch", "--show-current"], capture_output=True,
                            text=True).stdout.strip()
    append_json(here / "budget-starts", {"branch": branch})
    while not (here / "release-all").exists() and not (here / ("release-" + branch.replace("/", "-"))).exists():
        threading.Event().wait(0.05)
'''
    intercept = intercept.replace("reduced_values", repr((reduced_core, reduced_graphql)), 1)
    intercept = intercept.replace("initial_values", repr((initial_core, initial_graphql)), 1)
    stub.write_text(stub.read_text("utf-8").replace(
        "args = sys.argv[1:]\n", "args = sys.argv[1:]\n" + intercept, 1), encoding="utf-8")
    starts, quota = env.repo.bin / "budget-starts", env.repo.bin / "quota-reads"

    def rows(path):
        return [json.loads(line) for line in path.read_text("utf-8").splitlines()] if path.exists() else []

    def until(condition):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(0.05)
        pytest.fail("The command did not reach the expected GitHub response.")

    def advance(seconds):
        temp = clock / "next-elapsed"
        temp.write_text(str(seconds), encoding="utf-8")
        patient(lambda: temp.replace(clock / "elapsed"))

    processes, streams, outputs = [], [], []
    try:
        for number, where in enumerate(places):
            output, error = env.tmp / f"close-{number}.out", env.tmp / f"close-{number}.err"
            outputs.append((output, error))
            stdout, stderr = output.open("wb"), error.open("wb")
            streams.extend((stdout, stderr))
            processes.append(subprocess.Popen(
                [sys.executable, str(env.repo.bin / "forge"), "close", f"change-{number}"],
                cwd=where, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr))
            if number < 2:
                until(lambda: len(rows(starts)) == number + 1)
        until(lambda: "Waiting for GitHub API quota" in outputs[2][0].read_text("utf-8"))
        assert len(rows(starts)) == 2
        (env.repo.bin / "budget-shrunk").touch()
        advance(61)
        until(lambda: any(row["core"] == reduced_core and row["graphql"] == reduced_graphql
                          for row in rows(quota)))
        # The lower place is demonstrably free once its real close exits.
        (env.repo.bin / "release-fix-change-0").touch()
        processes[0].wait(timeout=30)
        assert processes[0].returncode == 0, outputs[0][1].read_text("utf-8")
        advance(122)
        # Only the third close can refresh now: the second is still inside gh.
        until(lambda: len(rows(starts)) > 2 or len(rows(quota)) >= 3)
        assert len(rows(starts)) == 2, "A new wait exceeded the reduced budget while the higher place stayed held."
        reads = rows(quota)
        assert len(reads) == 3
        assert all(after["at"] - before["at"] >= 60 for before, after in zip(reads, reads[1:]))
        (env.repo.bin / "release-fix-change-1").touch()
        until(lambda: len(rows(starts)) == 3)
    finally:
        (env.repo.bin / "release-all").touch()
        for process in processes:
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        for stream in streams:
            stream.close()
    for process, (output, error) in zip(processes, outputs):
        assert process.returncode == 0, output.read_text("utf-8") + error.read_text("utf-8")
        assert "Ready:" in output.read_text("utf-8")
